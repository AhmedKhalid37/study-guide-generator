#!/usr/bin/env python3
"""Tests for Slice 176C one-table-family row/cell reconstructor.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, paths,
URLs, images, PDFs, DOCX files, ZIPs, or runtime artifacts. All positioned tokens,
ids, labels, values, and canaries are synthetic and public-safe.

They prove:
  * spatial row/cell reconstruction rebuilds a grid from positioned tokens (the
    Slice 176B missing piece);
  * the full chain works: reconstructed inputs recompute the family quantity
    through the REAL verifier with the answer **masked** from the parser;
  * anti-laundering — a proximity *matrix* (decimal answer cells) and a lone result
    value are refused as inputs (blocked_by=source_input_mapping);
  * unavailable region input, empty grids, and malformed tokens degrade to closed
    blocked records without raising;
  * the committed ``record`` is closed-vocabulary only (no floats / raw values);
  * the module reuses SUPPORTED_METHODS / the real verifier and has no parallel
    recompute engine and no forbidden imports.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline.quality_safety_one_table_family_row_cell_reconstructor import (  # noqa: E402
    KIND,
    reconstruct_one_table_family,
)
from pipeline.quality_safety_recompute_verifier import (  # noqa: E402
    SUPPORTED_METHODS,
    recompute_quality_safety_fact,
)

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"[ok] {name}")
    else:
        FAILURES.append(name)
        print(f"[FAIL] {name} :: {detail}")


def _row_tokens(cells: list[str], y: float, x0: float = 0.0, dx: float = 10.0) -> list[dict]:
    return [{"x": x0 + i * dx, "y": y, "text": c} for i, c in enumerate(cells)]


# ── 1. proximity success via per-tree 0/1 indicators ─────────────────────────


def test_proximity_indicators_success() -> None:
    # Header (tree labels) + a same_terminal_node 0/1 indicator row. 4 of 5 share
    # => 0.8. The answer string "0.8" appears NOWHERE in the tokens (masked).
    tokens = _row_tokens(["T1", "T2", "T3", "T4", "T5"], y=0.0)
    tokens += _row_tokens(["1", "1", "1", "1", "0"], y=12.0)
    for tok in tokens:
        check("proximity tokens are answer-masked", "0.8" not in tok["text"] and "0.80" not in tok["text"], tok["text"])
    out = reconstruct_one_table_family(
        source_label="synthsrc", target_id="proximity_4_3", target_family="proximity",
        positioned_tokens=tokens,
    )
    rec = out["record"]
    check("proximity: kind", out["kind"] == KIND, str(out["kind"]))
    check("proximity: parsed", rec["status"] == "parsed", str(rec["status"]))
    check("proximity: row_cell parsed", rec["row_cell_extraction_status"] == "parsed_from_extraction_output", str(rec))
    check("proximity: record created", rec["source_input_record_status"] == "created", str(rec))
    check("proximity: origin parsed", rec["source_input_origin"] == "parsed_from_extraction_output", str(rec))
    check("proximity: machine consumable", rec["machine_consumable_for_recompute"] is True, str(rec))
    check("proximity: masked recompute passed", rec["masked_recompute_status"] == "passed", str(rec))
    check("proximity: next_step wire", rec["next_step"] == "wire_parsed_rows_into_recompute", str(rec))
    ri = out["recompute_input"]
    check("proximity: recompute_input present", isinstance(ri, dict) and ri["method"] == "proximity", str(ri))
    check("proximity: inputs are indicators", ri["inputs"].get("same_terminal_node") == [1, 1, 1, 1, 0], str(ri))
    # Full masked proof through the REAL verifier: expected 0.8 supplied as the
    # claimed value, never seen by the parser.
    fact = {"id": "p", "type": "numeric", "value": 0.8, "provenance": "unverified",
            "computation": {"method": ri["method"], "inputs": ri["inputs"]}}
    res = recompute_quality_safety_fact(fact)
    check("proximity: verifier passes masked recompute", res.get("status") == "passed", str(res))


# ── 2. proximity anti-laundering: matrix answers are not inputs ───────────────


def test_proximity_matrix_rejected_as_answer() -> None:
    # A proximity matrix: row = [sample_idx, prox, prox, prox] (decimals in (0,1)).
    tokens = _row_tokens(["1", "0.90", "0.70", "0.50"], y=0.0)
    tokens += _row_tokens(["2", "0.70", "0.60", "0.40"], y=12.0)
    tokens += _row_tokens(["3", "0.50", "0.40", "0.30"], y=24.0)
    out = reconstruct_one_table_family(
        source_label="synthsrc", target_id="proximity_4_3", target_family="proximity",
        positioned_tokens=tokens,
    )
    rec = out["record"]
    check("matrix: not created", rec["source_input_record_status"] == "not_created", str(rec))
    check("matrix: not machine consumable", rec["machine_consumable_for_recompute"] is False, str(rec))
    check("matrix: blocked_by source_input_mapping", rec["blocked_by"] == "source_input_mapping", str(rec))
    check("matrix: answer_matrix warning", "answer_matrix_not_input" in rec["warnings"], str(rec))
    check("matrix: no recompute_input", out["recompute_input"] is None, str(out["recompute_input"]))
    check("matrix: answer_string flag false", rec["answer_string_derived"] is False, str(rec))


# ── 3. weighted_average success via two columns ──────────────────────────────


def test_weighted_average_success() -> None:
    # values column + weights column => (10*1+20*2+30*3)/(1+2+3) = 140/6 = 23.333…
    tokens = _row_tokens(["value", "weight"], y=0.0)
    tokens += _row_tokens(["10", "1"], y=12.0)
    tokens += _row_tokens(["20", "2"], y=24.0)
    tokens += _row_tokens(["30", "3"], y=36.0)
    for tok in tokens:
        check("wavg tokens answer-masked", "23.3" not in tok["text"], tok["text"])
    out = reconstruct_one_table_family(
        source_label="synthsrc", target_id="weighted_weight_impute", target_family="weighted_average",
        positioned_tokens=tokens,
    )
    rec = out["record"]
    check("wavg: parsed", rec["status"] == "parsed", str(rec))
    check("wavg: created", rec["source_input_record_status"] == "created", str(rec))
    check("wavg: masked recompute passed", rec["masked_recompute_status"] == "passed", str(rec))
    ri = out["recompute_input"]
    check("wavg: method", ri["method"] == "weighted_average", str(ri))
    check("wavg: values", ri["inputs"].get("values") == [10.0, 20.0, 30.0], str(ri))
    check("wavg: weights", ri["inputs"].get("weights") == [1.0, 2.0, 3.0], str(ri))
    fact = {"id": "w", "type": "numeric", "value": 140.0 / 6.0, "provenance": "unverified",
            "computation": {"method": ri["method"], "inputs": ri["inputs"]}}
    res = recompute_quality_safety_fact(fact)
    check("wavg: verifier passes masked recompute", res.get("status") == "passed", str(res))


# ── 4. weighted_average lone value rejected ──────────────────────────────────


def test_weighted_average_lone_value_rejected() -> None:
    tokens = _row_tokens(["result", "198"], y=0.0)
    out = reconstruct_one_table_family(
        source_label="synthsrc", target_id="weighted_weight_impute", target_family="weighted_average",
        positioned_tokens=tokens,
    )
    rec = out["record"]
    check("lone value: not created", rec["source_input_record_status"] == "not_created", str(rec))
    check("lone value: blocked source_input_mapping", rec["blocked_by"] == "source_input_mapping", str(rec))
    check("lone value: no recompute_input", out["recompute_input"] is None, str(out))


# ── 5. degrade paths ─────────────────────────────────────────────────────────


def test_region_unavailable() -> None:
    out = reconstruct_one_table_family(
        source_label="s", target_id="proximity_4_3", target_family="proximity", positioned_tokens=None,
    )
    rec = out["record"]
    check("no region: blocked", rec["status"] == "blocked", str(rec))
    check("no region: crop_unavailable", rec["blocked_by"] == "crop_unavailable", str(rec))
    check("no region: region_input warning", "region_input_unavailable" in rec["warnings"], str(rec))


def test_malformed_tokens_degrade() -> None:
    for junk in (123, "x", [1, 2, 3], [{"x": "a"}], [{"nope": 1}], {"a": 1}):
        out = reconstruct_one_table_family(
            source_label="s", target_id="proximity_4_3", target_family="proximity", positioned_tokens=junk,
        )
        check(f"degrade {type(junk).__name__}: blocked", out["record"]["status"] == "blocked", str(out["record"]))
        check(f"degrade {type(junk).__name__}: no recompute_input", out["recompute_input"] is None, str(out))


def test_unsupported_family() -> None:
    out = reconstruct_one_table_family(
        source_label="s", target_id="t", target_family="gini",
        positioned_tokens=_row_tokens(["1", "1"], y=0.0),
    )
    check("unsupported family: blocked", out["record"]["status"] == "blocked", str(out["record"]))
    check("unsupported family: unsupported_method", out["record"]["blocked_by"] == "unsupported_method", str(out["record"]))


# ── 6. closed-vocabulary / no-leak ───────────────────────────────────────────


def _assert_closed(rec: dict, ctx: str) -> None:
    allowed_int_keys = {"structured_rows_count", "structured_columns_count", "numeric_cells_count"}
    for key, val in rec.items():
        if key in allowed_int_keys:
            check(f"{ctx}: {key} int", isinstance(val, int) and not isinstance(val, bool), str(val))
        elif isinstance(val, bool):
            pass
        elif isinstance(val, str):
            pass
        elif isinstance(val, list):
            check(f"{ctx}: {key} list of str", all(isinstance(t, str) for t in val), str(val))
        else:
            check(f"{ctx}: {key} no float/raw value", False, f"{key}={val!r} ({type(val).__name__})")


def test_record_is_closed_vocabulary() -> None:
    tokens = _row_tokens(["T1", "T2", "T3", "T4", "T5"], y=0.0) + _row_tokens(["1", "1", "1", "1", "0"], y=12.0)
    out = reconstruct_one_table_family(
        source_label="synthsrc", target_id="proximity_4_3", target_family="proximity", positioned_tokens=tokens,
    )
    _assert_closed(out["record"], "closed")
    # No float anywhere in the committed record (recompute_input is a separate channel).
    blob = json.dumps(out["record"])
    check("record json has no decimal-point float", ".0" not in blob and not any(c == "." for c in blob), blob)


def test_json_serializable() -> None:
    tokens = _row_tokens(["1", "1"], y=0.0)
    out = reconstruct_one_table_family(
        source_label="s", target_id="proximity_4_3", target_family="proximity", positioned_tokens=tokens,
    )
    s = json.dumps(out)
    check("json round-trips", json.loads(s)["kind"] == KIND, s[:60])


# ── 7. reuse / no parallel engine / no forbidden imports ─────────────────────


def test_reuse_supported_methods() -> None:
    check("proximity in SUPPORTED_METHODS", "proximity" in SUPPORTED_METHODS, str(SUPPORTED_METHODS))
    check("weighted_average in SUPPORTED_METHODS", "weighted_average" in SUPPORTED_METHODS, str(SUPPORTED_METHODS))


def test_no_recompute_engine_dup_and_no_forbidden_imports() -> None:
    src_path = REPO / "pipeline" / "quality_safety_one_table_family_row_cell_reconstructor.py"
    tree = ast.parse(src_path.read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = {"fastapi", "requests", "httpx", "urllib", "fitz", "pymupdf", "subprocess",
                 "socket", "PIL", "pytesseract", "os", "pathlib"}
    leaked = forbidden & imported
    check("no forbidden imports", not leaked, str(leaked))
    # No private recompute arithmetic duplicated: the source must call the verifier,
    # not redefine method math.
    body = src_path.read_text()
    check("reuses real verifier", "recompute_quality_safety_fact" in body, "missing verifier reuse")
    check("no parallel _RECOMPUTE_METHODS", "_RECOMPUTE_METHODS" not in body, "duplicated engine")


def main() -> int:
    test_proximity_indicators_success()
    test_proximity_matrix_rejected_as_answer()
    test_weighted_average_success()
    test_weighted_average_lone_value_rejected()
    test_region_unavailable()
    test_malformed_tokens_degrade()
    test_unsupported_family()
    test_record_is_closed_vocabulary()
    test_json_serializable()
    test_reuse_supported_methods()
    test_no_recompute_engine_dup_and_no_forbidden_imports()
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {FAILURES}")
        return 1
    print("All one-table-family row/cell reconstructor checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
