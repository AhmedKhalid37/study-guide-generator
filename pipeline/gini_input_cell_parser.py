"""Gini input-cell parser over the private OCR artifact (Slice 176J).

Slice 176I ran the proven local structured OCR producer on real content-bearing
Ensemble slides and wrote a **private, gitignored** extracted-content artifact, then
marked ``numeric_recompute_readiness=needs_input_cell_parser`` — i.e. content was
extracted but **no numeric input cells were parsed and no masked recompute was run**.
This module is the **first numeric consumer** of that artifact: it attempts to parse
**raw Gini class-count input cells** for one selected target out of the private OCR
extraction, and — only if credible raw inputs are found — runs a **masked** recompute
(the printed Gini answer is never supplied to the parser).

What this module IS:
  * a minimal, answer-agnostic parser for **one** weighted-Gini target's raw
    class-count input cells from already-extracted layout tables;
  * a no-laundering gate that distinguishes raw class-count **inputs** from computed
    Gini **answers**, unrelated integers, and answer/output tables, and refuses to
    create a source-input record from anything but genuine column-aligned class-count
    rows;
  * an advisory **masked** recompute (answer hidden) over genuinely-parsed inputs.

What this module is **NOT** (do not grow it into any of these here):
  * an OCR engine, a broad table engine, guide-generation wiring, frontend/API
    integration, full ingestion rollout, a Layer-2 judge, repair, cloud OCR, or
    provider/model generation. ``judge_ready=false``; ``repair_ready=false``.

No-laundering / provenance rules (non-negotiable, mirror Slice 176E):
  * The weighted-Gini **value** is a decimal in (0,1) — the **answer**, never an
    input. A column of unit-interval decimals is refused as ``answer_output_only``.
  * A credible class-count table requires integers forming **>= 2 shared columns**
    across **>= 2 rows** (real per-node class counts) — a single integer column,
    coincidental scattered integers, or an answer/leaf-count column are rejected as
    false positives, never mapped to inputs.
  * The committed record carries only closed tokens / ints / bools — no guide /
    source / OCR / table / caption text, no copied formulas, no raw values / leaf
    counts, no paths, filenames, hashes, or byte counts. Real parsed integer values,
    when present, live only in the separate ``recompute_input`` channel the caller
    may feed to the verifier and **must never commit**.

The core API (:func:`parse_gini_input_cells`) is pure, offline, and consumes
already-extracted **layout tables** (lists of stripped cell strings) — it reads no
files and carries no private path. A thin env-driven :func:`main` reads the private
manifest written by Slice 176I (``PRIVATE_OCR_DIR`` only; never a committed path),
extracts the selected target's tables, and prints the **closed** summary.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.quality_safety_recompute_verifier import (  # noqa: E402
    SUPPORTED_METHODS,
    recompute_quality_safety_fact,
)
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402

ARTIFACT_NAME = "gini_input_cell_parser_private_ocr_artifact"
SOURCE_LABEL_DEFAULT = "ensemble"

# Only the weighted_gini family is in scope this slice (one target, simplest
# class-count mapping). Other families are reported as unsupported, not guessed.
SUPPORTED_FAMILIES = frozenset({"weighted_gini"})

# ── Closed vocabularies (this module owns what it emits) ─────────────────────
STATUSES = frozenset({"parsed", "blocked", "skipped"})
TARGET_FAMILIES = frozenset({"weighted_gini", "unknown"})
INPUT_CELL_CANDIDATE_STATUSES = frozenset(
    {"found", "partial", "not_found", "rejected_false_positive"}
)
INPUT_CELL_ORIGINS = frozenset({"private_ocr_artifact", "none"})
CANDIDATE_KINDS = frozenset(
    {"raw_class_count_inputs", "computed_gini_answer", "unrelated_integers", "ambiguous", "none"}
)
GUARD_STATUSES = frozenset({"passed", "failed", "not_applicable"})
SOURCE_INPUT_RECORD_STATUSES = frozenset({"created", "not_created"})
SOURCE_INPUT_ORIGINS = frozenset({"ocr_from_rendered_slide", "none"})
MASKED_RECOMPUTE_STATUSES = frozenset({"passed", "failed", "not_run", "not_supported"})
WARNINGS = frozenset(
    {
        "none",
        "answer_or_unrelated_values_not_inputs",
        "ambiguous_grid",
        "private_artifact_missing",
        "insufficient_class_count_structure",
        "parser_scope_too_narrow",
    }
)
BLOCKED_BY = frozenset(
    {
        "none",
        "private_artifact_missing",
        "input_cell_parser",
        "answer_output_only",
        "ambiguous_grid",
        "false_positive_guard",
        "unsupported_method",
    }
)
NEXT_STEPS = frozenset(
    {
        "wire_ocr_inputs_into_recompute",
        "improve_gini_input_cell_parser",
        "run_more_structured_ocr_pages",
        "use_private_extracted_content_for_guide_pilot",
        "pivot_to_visible_table_pilot",
    }
)

_INT_RE = re.compile(r"^\d+$")
_UNIT_DECIMAL_RE = re.compile(r"^0?\.\d+$")  # a Gini value lives in (0,1): the ANSWER

_MIN_CLASS_COLUMNS = 2  # >= 2 integer columns => candidate class counts per node
_MIN_CLASS_ROWS = 2  # >= 2 nodes/groups => a real per-node class-count table


# ── Public API ───────────────────────────────────────────────────────────────


def parse_gini_input_cells(
    *,
    source_label: str = SOURCE_LABEL_DEFAULT,
    selected_target_id: str,
    target_family: str = "weighted_gini",
    layout_tables: Any = None,
    private_artifact_available: bool = True,
    private_artifact_gitignored: bool = True,
    expected_answer_available: bool = False,
) -> dict[str, Any]:
    """Attempt to parse ONE weighted-Gini target's raw class-count input cells.

    ``layout_tables`` is a closed list of tables, each a list of rows, each a list of
    already-stripped cell strings (no markup, no positions) extracted from the private
    176I OCR artifact for the selected target. The parser classifies the cells,
    refuses Gini answer decimals / unrelated integers / answer-output tables, and —
    only when genuine column-aligned class-count rows are found and no expected answer
    is available — runs a masked recompute.

    Returns ``{"record": <closed>, "recompute_input": <values|None>}``. ``record`` is
    closed (no values); ``recompute_input`` is present only when a real
    machine-consumable record was created and **must never be committed**. Pure,
    total, offline; never raises.
    """
    try:
        return _attempt(
            source_label=source_label,
            selected_target_id=selected_target_id,
            target_family=target_family,
            layout_tables=layout_tables,
            private_artifact_available=private_artifact_available,
            private_artifact_gitignored=private_artifact_gitignored,
            expected_answer_available=expected_answer_available,
        )
    except Exception:
        return _envelope(
            _record(
                source_label=source_label,
                selected_target_id=selected_target_id,
                target_family="weighted_gini",
                status="blocked",
                private_artifact_available=bool(private_artifact_available),
                private_artifact_gitignored=bool(private_artifact_gitignored),
                input_cell_candidate_status="not_found",
                input_cell_candidate_origin="none",
                candidate_kind="ambiguous",
                class_label_coherence="not_applicable",
                column_alignment_status="not_applicable",
                answer_agnostic_guard_status="not_applicable",
                source_input_record_status="not_created",
                source_input_origin="none",
                machine_consumable_for_recompute=False,
                masked_recompute_status="not_run",
                false_positive_rejected=False,
                warning="ambiguous_grid",
                blocked_by="input_cell_parser",
                recommended_next_step="improve_gini_input_cell_parser",
            ),
            None,
        )


# ── Driver ───────────────────────────────────────────────────────────────────


def _attempt(
    *,
    source_label: Any,
    selected_target_id: Any,
    target_family: Any,
    layout_tables: Any,
    private_artifact_available: Any,
    private_artifact_gitignored: Any,
    expected_answer_available: Any,
) -> dict[str, Any]:
    source_label = (
        source_label if isinstance(source_label, str) and source_label else SOURCE_LABEL_DEFAULT
    )
    target_id = (
        selected_target_id
        if isinstance(selected_target_id, str) and selected_target_id
        else "unknown_target"
    )
    family = target_family if target_family in SUPPORTED_FAMILIES else "unknown"
    available = bool(private_artifact_available)
    gitignored = bool(private_artifact_gitignored)

    def blocked(**kw: Any) -> dict[str, Any]:
        base = dict(
            source_label=source_label,
            selected_target_id=target_id,
            target_family=family if family in TARGET_FAMILIES else "unknown",
            status="blocked",
            private_artifact_available=available,
            private_artifact_gitignored=gitignored,
            input_cell_candidate_origin="private_ocr_artifact" if available else "none",
            source_input_record_status="not_created",
            source_input_origin="none",
            machine_consumable_for_recompute=False,
            masked_recompute_status="not_run",
        )
        base.update(kw)
        return _envelope(_record(**base), None)

    # Artifact unavailable -> honest hard blocker (Part 1B).
    if not available:
        return blocked(
            input_cell_candidate_status="not_found",
            input_cell_candidate_origin="none",
            candidate_kind="none",
            class_label_coherence="not_applicable",
            column_alignment_status="not_applicable",
            answer_agnostic_guard_status="not_applicable",
            false_positive_rejected=False,
            warning="private_artifact_missing",
            blocked_by="private_artifact_missing",
            recommended_next_step="run_more_structured_ocr_pages",
        )

    # Unsupported family -> skipped, never guessed.
    if family not in SUPPORTED_FAMILIES:
        return _envelope(
            _record(
                source_label=source_label,
                selected_target_id=target_id,
                target_family="unknown",
                status="skipped",
                private_artifact_available=available,
                private_artifact_gitignored=gitignored,
                input_cell_candidate_status="not_found",
                input_cell_candidate_origin="private_ocr_artifact",
                candidate_kind="none",
                class_label_coherence="not_applicable",
                column_alignment_status="not_applicable",
                answer_agnostic_guard_status="not_applicable",
                source_input_record_status="not_created",
                source_input_origin="none",
                machine_consumable_for_recompute=False,
                masked_recompute_status="not_supported",
                false_positive_rejected=False,
                warning="parser_scope_too_narrow",
                blocked_by="unsupported_method",
                recommended_next_step="improve_gini_input_cell_parser",
            ),
            None,
        )

    grids = _normalize_tables(layout_tables)
    if not grids:
        return blocked(
            input_cell_candidate_status="not_found",
            candidate_kind="none",
            class_label_coherence="not_applicable",
            column_alignment_status="not_applicable",
            answer_agnostic_guard_status="not_applicable",
            false_positive_rejected=False,
            warning="ambiguous_grid",
            blocked_by="input_cell_parser",
            recommended_next_step="improve_gini_input_cell_parser",
        )

    # Inspect every table; keep the strongest signal across them.
    best = _classify_grids(grids)

    answer_agnostic = "passed" if best["answer_columns"] > 0 or best["unit_decimal_cells"] > 0 else "not_applicable"

    # 1) Genuine column-aligned class-count inputs -> the only path to a record.
    if best["candidate_kind"] == "raw_class_count_inputs":
        groups = best["groups"]
        coherence = "passed" if best["label_columns"] >= 1 else "failed"
        if expected_answer_available:
            # The parser must never see the answer; refuse to create a record.
            return blocked(
                input_cell_candidate_status="rejected_false_positive",
                candidate_kind="ambiguous",
                class_label_coherence=coherence,
                column_alignment_status="passed",
                answer_agnostic_guard_status="failed",
                false_positive_rejected=True,
                warning="answer_or_unrelated_values_not_inputs",
                blocked_by="false_positive_guard",
                recommended_next_step="improve_gini_input_cell_parser",
            )
        masked = _masked_recompute({"groups": groups})
        if masked != "passed":
            return blocked(
                input_cell_candidate_status="partial",
                candidate_kind="raw_class_count_inputs",
                class_label_coherence=coherence,
                column_alignment_status="passed",
                answer_agnostic_guard_status=answer_agnostic,
                false_positive_rejected=False,
                warning="insufficient_class_count_structure",
                blocked_by="input_cell_parser",
                recommended_next_step="improve_gini_input_cell_parser",
            )
        record = _record(
            source_label=source_label,
            selected_target_id=target_id,
            target_family="weighted_gini",
            status="parsed",
            private_artifact_available=available,
            private_artifact_gitignored=gitignored,
            input_cell_candidate_status="found",
            input_cell_candidate_origin="private_ocr_artifact",
            candidate_kind="raw_class_count_inputs",
            class_label_coherence=coherence,
            column_alignment_status="passed",
            answer_agnostic_guard_status="passed",
            source_input_record_status="created",
            source_input_origin="ocr_from_rendered_slide",
            machine_consumable_for_recompute=True,
            masked_recompute_status="passed",
            false_positive_rejected=False,
            warning="none",
            blocked_by="none",
            recommended_next_step="wire_ocr_inputs_into_recompute",
        )
        recompute_input = {
            "method": "weighted_gini",
            "inputs": {"groups": groups},
            "value_kind": "numeric",
            "confidence": "medium",
            "origin": "ocr_from_rendered_slide",
            "target_id": target_id,
            "source_label": source_label,
        }
        return _envelope(record, recompute_input)

    # 2) Answer/output table (Gini value column present, no class-count grid).
    if best["candidate_kind"] == "computed_gini_answer":
        return blocked(
            input_cell_candidate_status="rejected_false_positive",
            candidate_kind="computed_gini_answer",
            class_label_coherence="not_applicable",
            column_alignment_status="failed",
            answer_agnostic_guard_status="passed",
            false_positive_rejected=True,
            warning="answer_or_unrelated_values_not_inputs",
            blocked_by="answer_output_only",
            recommended_next_step="pivot_to_visible_table_pilot",
        )

    # 3) Integers present but not a credible class-count grid -> false positive.
    if best["candidate_kind"] == "unrelated_integers":
        return blocked(
            input_cell_candidate_status="rejected_false_positive",
            candidate_kind="unrelated_integers",
            class_label_coherence="failed",
            column_alignment_status="failed",
            answer_agnostic_guard_status=answer_agnostic,
            false_positive_rejected=True,
            warning="answer_or_unrelated_values_not_inputs",
            blocked_by="false_positive_guard",
            recommended_next_step="improve_gini_input_cell_parser",
        )

    # 4) Nothing usable.
    return blocked(
        input_cell_candidate_status="not_found",
        candidate_kind="none" if best["numeric_cells"] == 0 else "ambiguous",
        class_label_coherence="not_applicable",
        column_alignment_status="not_applicable" if best["numeric_cells"] == 0 else "failed",
        answer_agnostic_guard_status=answer_agnostic,
        false_positive_rejected=False,
        warning="ambiguous_grid",
        blocked_by="ambiguous_grid" if best["numeric_cells"] else "input_cell_parser",
        recommended_next_step="run_more_structured_ocr_pages",
    )


# ── Classification (closed/structural; no cell text leaves) ──────────────────


def _classify_grids(grids: list[list[list[str]]]) -> dict[str, Any]:
    """Pick the strongest signal across all tables for the selected target.

    A class-count grid (>= 2 integer columns x >= 2 rows) beats an answer-only table;
    an answer column (unit-interval decimals) beats scattered integers. Returns closed
    structural counts plus the parsed integer ``groups`` (kept private by the caller).
    """
    best = {
        "candidate_kind": "none",
        "groups": [],
        "answer_columns": 0,
        "unit_decimal_cells": 0,
        "label_columns": 0,
        "numeric_cells": 0,
        "rank": -1,
    }
    order = {"none": 0, "ambiguous": 1, "unrelated_integers": 2, "computed_gini_answer": 3, "raw_class_count_inputs": 4}
    for grid in grids:
        sig = _classify_one(grid)
        rank = order[sig["candidate_kind"]]
        if rank > best["rank"]:
            best = {**sig, "rank": rank}
    return best


def _classify_one(grid: list[list[str]]) -> dict[str, Any]:
    width = max((len(row) for row in grid), default=0)
    int_col_rows: dict[int, list[tuple[int, int]]] = {}  # col -> [(row_idx, value)]
    decimal_col_rows: dict[int, int] = {}  # col -> count of unit-interval decimals
    label_cols: set[int] = set()
    numeric_cells = 0
    unit_decimal_cells = 0
    for r, row in enumerate(grid):
        for c in range(width):
            cell = row[c].strip() if c < len(row) and isinstance(row[c], str) else ""
            if not cell:
                continue
            if _INT_RE.match(cell):
                int_col_rows.setdefault(c, []).append((r, int(cell)))
                numeric_cells += 1
            elif _UNIT_DECIMAL_RE.match(cell):
                decimal_col_rows[c] = decimal_col_rows.get(c, 0) + 1
                unit_decimal_cells += 1
                numeric_cells += 1
            elif not _is_number(cell):
                label_cols.add(c)

    # Integer columns shared by >= 2 rows are class-count candidates.
    shared_int_cols = sorted(c for c, cells in int_col_rows.items() if len(cells) >= 2)
    answer_columns = sum(1 for c, n in decimal_col_rows.items() if n >= 2)

    groups: list[dict[str, int]] = []
    if len(shared_int_cols) >= _MIN_CLASS_COLUMNS:
        # Build per-row groups restricted to the shared integer columns.
        by_row: dict[int, list[int]] = {}
        for c in shared_int_cols:
            for r, val in int_col_rows[c]:
                by_row.setdefault(r, []).append(val)
        for r in sorted(by_row):
            vals = by_row[r]
            if len(vals) >= _MIN_CLASS_COLUMNS and any(v > 0 for v in vals) and all(v >= 0 for v in vals):
                groups.append({f"c{i}": v for i, v in enumerate(vals)})

    if len(groups) >= _MIN_CLASS_ROWS:
        kind = "raw_class_count_inputs"
    elif answer_columns >= 1:
        kind = "computed_gini_answer"
    elif numeric_cells > 0:
        kind = "unrelated_integers" if int_col_rows else "ambiguous"
    else:
        kind = "none"

    return {
        "candidate_kind": kind,
        "groups": groups,
        "answer_columns": answer_columns,
        "unit_decimal_cells": unit_decimal_cells,
        "label_columns": len(label_cols),
        "numeric_cells": numeric_cells,
    }


def _normalize_tables(layout_tables: Any) -> list[list[list[str]]]:
    """Coerce input into a list of grids of stripped cell strings; total/pure."""
    if not isinstance(layout_tables, list):
        return []
    grids: list[list[list[str]]] = []
    for table in layout_tables:
        if not isinstance(table, list):
            continue
        rows: list[list[str]] = []
        for row in table:
            if not isinstance(row, list):
                continue
            rows.append([c if isinstance(c, str) else "" for c in row])
        if rows:
            grids.append(rows)
    return grids


# ── Masked recompute (reuse the real verifier, answer hidden) ────────────────


def _masked_recompute(inputs: dict[str, Any]) -> str:
    if "weighted_gini" not in SUPPORTED_METHODS:
        return "not_supported"
    fact = {
        "id": "masked_weighted_gini_from_ocr",
        "type": "numeric",
        "value": None,  # answer is masked: the parser never receives it
        "provenance": "unverified",
        "computation": {"method": "weighted_gini", "inputs": inputs},
    }
    result = recompute_quality_safety_fact(fact)
    recomputed = result.get("recomputed_value") if isinstance(result, dict) else None
    return "passed" if isinstance(recomputed, (int, float)) and not isinstance(recomputed, bool) else "failed"


# ── HTML table extraction (for the env-driven private runner only) ───────────


def extract_layout_tables_from_html(html: Any) -> list[list[list[str]]]:
    """Extract tables as grids of **tag-stripped** cell strings from layout HTML.

    Used only by :func:`main` against the private artifact; the stripped strings are
    processed in memory and never committed. Pure / total; returns ``[]`` on anything
    unexpected.
    """
    if not isinstance(html, str) or not html:
        return []
    grids: list[list[list[str]]] = []
    for table in re.findall(r"<table\b.*?</table>", html, flags=re.I | re.S):
        rows: list[list[str]] = []
        for tr in re.findall(r"<tr\b.*?</tr>", table, flags=re.I | re.S):
            cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", tr, flags=re.I | re.S)
            rows.append([_strip_tags(c) for c in cells])
        if rows:
            grids.append(rows)
    return grids


def _strip_tags(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment or "")).strip()


# ── Record assembly (closed vocabulary only) ─────────────────────────────────


def _record(
    *,
    source_label: str,
    selected_target_id: str,
    target_family: str,
    status: str,
    private_artifact_available: bool,
    private_artifact_gitignored: bool,
    input_cell_candidate_status: str,
    input_cell_candidate_origin: str,
    candidate_kind: str,
    class_label_coherence: str,
    column_alignment_status: str,
    answer_agnostic_guard_status: str,
    source_input_record_status: str,
    source_input_origin: str,
    machine_consumable_for_recompute: bool,
    masked_recompute_status: str,
    false_positive_rejected: bool,
    warning: str,
    blocked_by: str,
    recommended_next_step: str,
) -> dict[str, Any]:
    return {
        "artifact_name": ARTIFACT_NAME,
        "status": _tok(status, STATUSES, "blocked"),
        "source_label": _safe_label(source_label),
        "selected_target_id": _safe_label(selected_target_id, fallback="unknown_target", limit=64),
        "selected_target_family": _tok(target_family, TARGET_FAMILIES, "unknown"),
        "private_artifact_available": bool(private_artifact_available),
        "private_artifact_gitignored": bool(private_artifact_gitignored),
        "raw_ocr_committed": False,
        "raw_table_text_committed": False,
        "raw_values_committed": False,
        "input_cell_candidate_status": _tok(
            input_cell_candidate_status, INPUT_CELL_CANDIDATE_STATUSES, "not_found"
        ),
        "input_cell_candidate_origin": _tok(input_cell_candidate_origin, INPUT_CELL_ORIGINS, "none"),
        "candidate_kind": _tok(candidate_kind, CANDIDATE_KINDS, "none"),
        "class_label_coherence": _tok(class_label_coherence, GUARD_STATUSES, "not_applicable"),
        "column_alignment_status": _tok(column_alignment_status, GUARD_STATUSES, "not_applicable"),
        "answer_agnostic_guard_status": _tok(
            answer_agnostic_guard_status, GUARD_STATUSES, "not_applicable"
        ),
        "source_input_record_status": _tok(
            source_input_record_status, SOURCE_INPUT_RECORD_STATUSES, "not_created"
        ),
        "source_input_origin": _tok(source_input_origin, SOURCE_INPUT_ORIGINS, "none"),
        "machine_consumable_for_recompute": bool(machine_consumable_for_recompute),
        "masked_recompute_status": _tok(masked_recompute_status, MASKED_RECOMPUTE_STATUSES, "not_run"),
        "false_positive_rejected": bool(false_positive_rejected),
        "hand_authored_rows": False,
        "fixture_derived": False,
        "answer_string_derived": False,
        "warning": _tok(warning, WARNINGS, "none"),
        "blocked_by": _tok(blocked_by, BLOCKED_BY, "none"),
        "recommended_next_step": _tok(recommended_next_step, NEXT_STEPS, "improve_gini_input_cell_parser"),
    }


def _envelope(record: dict[str, Any], recompute_input: dict[str, Any] | None) -> dict[str, Any]:
    return {"record": record, "recompute_input": recompute_input}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False


def _tok(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def _safe_label(value: Any, *, fallback: str = "unknown", limit: int = 40) -> str:
    text = str(value or fallback)
    cleaned = re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")
    return (cleaned or fallback)[:limit]


# ── Env-driven private runner (no committed path; closed output only) ────────


def main() -> int:
    """Run the parser against the private 176I artifact; print the closed record.

    Env:
      PRIVATE_OCR_DIR   gitignored/temp dir holding 176I's manifest (required, private)
      SOURCE_LABEL      closed source label (default "ensemble")
      GINI_TARGET_ID    selected target id (default "gini_chest_pain")
      GINI_CATEGORY     manifest slide_category to read (default
                        "ensemble_gini_or_leaf_count")
    """
    private_dir = os.environ.get("PRIVATE_OCR_DIR")
    source_label = os.environ.get("SOURCE_LABEL", SOURCE_LABEL_DEFAULT)
    target_id = os.environ.get("GINI_TARGET_ID", "gini_chest_pain")
    category = os.environ.get("GINI_CATEGORY", "ensemble_gini_or_leaf_count")

    if not private_dir:
        result = parse_gini_input_cells(
            source_label=source_label,
            selected_target_id=target_id,
            target_family="weighted_gini",
            layout_tables=None,
            private_artifact_available=False,
            private_artifact_gitignored=False,
        )
        print(json.dumps(result["record"], indent=2))
        return 2

    gitignored = is_private_artifact_dir(private_dir)
    manifest_path = os.path.join(private_dir, "extracted_content_manifest.json")
    available = gitignored and os.path.isfile(manifest_path)

    layout_tables: list[list[list[str]]] = []
    if available:
        try:
            with open(manifest_path, encoding="utf-8") as fh:
                manifest = json.load(fh)
            for entry in manifest.get("entries", []):
                if isinstance(entry, dict) and entry.get("slide_category") == category:
                    layout_tables = extract_layout_tables_from_html(entry.get("raw_layout_html"))
                    break
        except Exception:
            available = False

    result = parse_gini_input_cells(
        source_label=source_label,
        selected_target_id=target_id,
        target_family="weighted_gini",
        layout_tables=layout_tables,
        private_artifact_available=available,
        private_artifact_gitignored=gitignored,
    )
    # Print ONLY the closed record. The recompute_input channel (real values) is
    # never printed or committed.
    print(json.dumps(result["record"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
