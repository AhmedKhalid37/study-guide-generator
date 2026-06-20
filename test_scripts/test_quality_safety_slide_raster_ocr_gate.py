"""Slice 176F — slide-raster OCR verification gate (public-safe reproducibility test).

This file is the COMMITTED, public-safe half of the Slice 176F gate. The real gate
was produced once with real data via a gitignored, transient harness (never
committed); this file exercises the gate's *logic* on synthetic public-safe tokens
only, so the false-positive guard and the masked-recompute routing stay regression
tested without embedding any private OCR / source / table text, paths, filenames,
hashes, byte counts, or screenshots.

What it asserts (closed vocabulary only):
  1. A credible x-column-aligned class-count grid passes the 176E credibility guard
     and routes through the REAL `_recompute_weighted_gini` to a finite Gini in
     [0, 1] (masked: the printed answer is never supplied as an input).
  2. Coincidental scattered integers (no shared columns) FAIL the guard, so the
     masked recompute is NOT run — the 176E false-positive guard, re-proven here on
     the OCR-grid shape.
  3. A unit-interval decimal (a printed Gini *answer*) is refused as an input cell.
  4. The bulk-text quality bucketer maps OCR mean-confidence to clean / partial /
     failed deterministically.

Optional real-deck mode (skipped by default, never in normal runs): if the env var
SLIDE_OCR_GATE_DECK points at a deck and `tesseract` is on PATH, a separate operator
harness may import these helpers — this test never reads private decks itself.

No Chandra, no cloud OCR, no provider/model generation, no guide regeneration, no
Layer-2 judge, no repair. judge_ready=false; repair_ready=false.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.quality_safety_recompute_verifier import _recompute_weighted_gini


# --- gate logic (the same shape the transient real harness applied) ----------

def credibility_guard(int_cells, *, xtol: int = 40, ytol: int = 22):
    """176E column-alignment credibility guard, applied to OCR integer cells.

    int_cells: list of (x, y, value). A credible class-count grid needs >=2 shared
    x-columns (each with >=2 cells) AND >=2 multi-column rows. Magnitude-agnostic and
    answer-agnostic: it tests *structure*, never the value of any number.
    """
    cols: dict[int, list] = {}
    rows: dict[int, list] = {}
    for x, y, _value in int_cells:
        cols.setdefault(round(x / xtol), []).append(y)
        rows.setdefault(round(y / ytol), []).append(x)
    shared_cols = sum(1 for members in cols.values() if len(members) >= 2)
    multi_rows = sum(1 for members in rows.values() if len(members) >= 2)
    return (shared_cols >= 2 and multi_rows >= 2), shared_cols, multi_rows


def is_answer_decimal(token: str) -> bool:
    """A unit-interval decimal is a printed Gini *answer*, never an input cell."""
    try:
        value = float(token)
    except (TypeError, ValueError):
        return False
    return "." in token and 0.0 < value < 1.0


def masked_recompute_from_grid(int_cells):
    """Only run the REAL verifier if the credibility guard passes; else not_run."""
    ok, _sc, _mr = credibility_guard(int_cells)
    if not ok:
        return "not_run", None
    rows: dict[int, list] = {}
    for x, y, value in int_cells:
        rows.setdefault(round(y / 22), []).append((x, value))
    groups = []
    for _key, members in sorted(rows.items()):
        values = [v for _x, v in sorted(members) if 0 <= v < 10000]
        if 2 <= len(values) <= 4 and sum(values) > 0:
            groups.append({"class_counts": {f"c{i}": v for i, v in enumerate(values)}})
    if len(groups) < 2:
        return "not_run", None
    result = _recompute_weighted_gini({"groups": groups[:4]})
    if result is None:
        return "failed", None
    return ("passed" if 0.0 <= result <= 1.0 else "failed"), result


def bulk_text_bucket(mean_conf: float) -> str:
    if mean_conf >= 70:
        return "clean"
    if mean_conf >= 40:
        return "partial"
    return "failed"


# --- public-safe synthetic assertions ----------------------------------------

def _check(label, condition):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")
    return bool(condition)


def main() -> int:
    ok = True

    # (1) credible aligned 2x2 class-count grid -> guard passes -> finite gini.
    # Synthetic, invented small counts laid out as two x-aligned columns x two rows.
    credible = [
        (100, 200, 7), (300, 200, 3),
        (100, 240, 2), (300, 240, 8),
    ]
    passed, sc, mr = credibility_guard(credible)
    ok &= _check(f"credible grid passes guard (shared_cols={sc} multi_rows={mr})", passed)
    status, value = masked_recompute_from_grid(credible)
    ok &= _check("credible grid -> masked recompute passed", status == "passed")
    ok &= _check("recompute via REAL verifier returns finite gini in [0,1]",
                 value is not None and 0.0 <= value <= 1.0)

    # (2) coincidental scattered integers -> guard fails -> recompute NOT run.
    # This is the 176E false positive re-proven on the OCR-grid shape.
    coincidental = [(120, 200, 4), (520, 612, 9), (333, 410, 2)]
    passed2, sc2, mr2 = credibility_guard(coincidental)
    ok &= _check(f"coincidental ints FAIL guard (shared_cols={sc2} multi_rows={mr2})",
                 not passed2)
    status2, _ = masked_recompute_from_grid(coincidental)
    ok &= _check("coincidental ints -> masked recompute not_run (false-positive guard)",
                 status2 == "not_run")

    # (3) a printed unit-interval Gini decimal is refused as an input cell.
    ok &= _check("unit-interval decimal refused as input (answer, not input)",
                 is_answer_decimal("0.42") and not is_answer_decimal("7"))

    # (4) bulk-text quality bucketer is deterministic.
    ok &= _check("bulk_text_bucket: 82->clean", bulk_text_bucket(82) == "clean")
    ok &= _check("bulk_text_bucket: 55->partial", bulk_text_bucket(55) == "partial")
    ok &= _check("bulk_text_bucket: 20->failed", bulk_text_bucket(20) == "failed")

    print(f"slide_raster_ocr_gate_logic: {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
