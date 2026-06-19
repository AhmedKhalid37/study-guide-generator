#!/usr/bin/env python3
"""Tests for Slice 176A focused table-structure extraction attempt.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, paths,
URLs, images, PDFs, DOCX files, ZIPs, or runtime artifacts. All fixture ids,
labels, values, and canaries are synthetic and public-safe.

They prove:
  * the artifact is closed-vocabulary only;
  * the attempt is limited to exactly the two focused target records;
  * no raw OCR / source / table text and no private paths / filenames / hashes /
    byte counts are emitted;
  * answer-string-derived inputs are rejected;
  * hand-authored target maps are rejected;
  * fixture-derived inputs are rejected;
  * ocr_prose_only never counts as machine-consumable;
  * structured_rows parsed from extraction can create a source-input record only
    when the required fields are present and the method matches the target family;
  * the real current state (no args) keeps both targets honestly blocked.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_focused_table_structure_attempt import (  # noqa: E402
    build_focused_table_structure_attempt,
    FOCUSED_TARGETS,
    KIND,
    VERSION,
    TARGET_FAMILIES,
    REGION_SOURCES,
    TABLE_STRUCTURE_STATUSES,
    SOURCE_INPUT_RECORD_STATUSES,
    SOURCE_INPUT_ORIGINS,
    BLOCKED_BY_TOKENS,
    WARNING_ORDER,
)

FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    status = "ok" if cond else "FAIL"
    print(f"[{status}] {name}")
    if not cond:
        FAILURES.append(name)


# ── Closed-vocabulary value scan ─────────────────────────────────────────────

_ALLOWED_STRINGS = (
    set(FOCUSED_TARGETS)
    | set(TARGET_FAMILIES)
    | set(REGION_SOURCES)
    | set(TABLE_STRUCTURE_STATUSES)
    | set(SOURCE_INPUT_RECORD_STATUSES)
    | set(SOURCE_INPUT_ORIGINS)
    | set(BLOCKED_BY_TOKENS)
    | set(WARNING_ORDER)
    | {KIND, "ensemble"}
)

# A string is suspicious if it looks like a path, file, hash, data uri, or prose.
_LEAK_PATTERN = re.compile(
    r"(/home/|/mnt/|\.pdf|\.docx|\.zip|\.png|data:|base64|sha256|[a-f0-9]{16,})"
)


def _walk_strings(node: Any):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                yield key
            yield from _walk_strings(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk_strings(item)


def assert_closed_vocab(name: str, artifact: dict[str, Any]) -> None:
    bad: list[str] = []
    for text in _walk_strings(artifact):
        if text in _ALLOWED_STRINGS:
            continue
        if _LEAK_PATTERN.search(text):
            bad.append(text)
        elif len(text) > 64 or " " in text:
            # Any long or whitespace-bearing free text would be prose/leakage.
            bad.append(text)
    check(f"{name}: closed-vocabulary only", not bad)


def assert_no_leak_keys(name: str, artifact: dict[str, Any]) -> None:
    leaked: list[str] = []
    for text in _walk_strings(artifact):
        if _LEAK_PATTERN.search(text):
            leaked.append(text)
    check(f"{name}: no path/filename/hash/byte leak", not leaked)


# ── Tests ────────────────────────────────────────────────────────────────────


def test_real_current_state_blocked() -> None:
    art = build_focused_table_structure_attempt()
    check("real: kind", art["kind"] == KIND)
    check("real: version", art["version"] == VERSION)
    check("real: status blocked", art["status"] == "blocked")
    check("real: exactly two targets", art["targets_considered"] == 2)
    check("real: exactly two records", len(art["records"]) == 2)
    ids = {r["target_id"] for r in art["records"]}
    check("real: target ids are the two focused", ids == set(FOCUSED_TARGETS))
    for r in art["records"]:
        check(f"real: {r['target_id']} not created", r["source_input_record_status"] == "not_created")
        check(f"real: {r['target_id']} not consumable", r["machine_consumable_for_recompute"] is False)
        check(f"real: {r['target_id']} blocked table_structure_missing", r["blocked_by"] == "table_structure_missing")
    s = art["summary"]
    check("real: 0 created", s["source_input_records_created_count"] == 0)
    check("real: 0 machine-consumable", s["machine_consumable_count"] == 0)
    check("real: 0 hand-authored", s["hand_authored_target_map_count"] == 0)
    check("real: 0 fixture-derived", s["fixture_derived_count"] == 0)
    check("real: 0 answer-string", s["answer_string_derived_count"] == 0)
    assert_closed_vocab("real", art)
    assert_no_leak_keys("real", art)


def test_limited_to_two_targets() -> None:
    # An extra/unknown target id in the input map must be ignored entirely.
    art = build_focused_table_structure_attempt(
        source_input_candidates_by_target={
            "some_other_target_99": {
                "origin": "parsed_from_extraction_output",
                "table_structure_status": "structured_rows",
                "method": "proximity",
                "inputs": {"shared_terminal_count": 1, "tree_count": 2},
            }
        }
    )
    check("limit: still exactly two records", len(art["records"]) == 2)
    ids = {r["target_id"] for r in art["records"]}
    check("limit: ids unchanged", ids == set(FOCUSED_TARGETS))
    check("limit: nothing created from stray target", art["summary"]["source_input_records_created_count"] == 0)


def test_structured_rows_creates_record() -> None:
    art = build_focused_table_structure_attempt(
        region_signals_by_target={
            "proximity_4_3": {"region_identified": True, "region_source": "existing_table_stack"}
        },
        source_input_candidates_by_target={
            "proximity_4_3": {
                "origin": "parsed_from_extraction_output",
                "table_structure_status": "structured_rows",
                "method": "proximity",
                "inputs": {"shared_terminal_count": 3, "tree_count": 4},
            }
        },
    )
    rec = next(r for r in art["records"] if r["target_id"] == "proximity_4_3")
    check("created: record created", rec["source_input_record_status"] == "created")
    check("created: machine consumable", rec["machine_consumable_for_recompute"] is True)
    check("created: origin parsed", rec["source_input_origin"] == "parsed_from_extraction_output")
    check("created: blocked none", rec["blocked_by"] == "none")
    check("created: region surfaced", rec["region_identified"] is True)
    check("created: status completed", art["status"] == "completed")
    check("created: summary created==1", art["summary"]["source_input_records_created_count"] == 1)
    assert_closed_vocab("created", art)


def test_missing_required_fields_not_created() -> None:
    # structured_rows but inputs absent → cannot create a record.
    art = build_focused_table_structure_attempt(
        source_input_candidates_by_target={
            "proximity_4_3": {
                "origin": "parsed_from_extraction_output",
                "table_structure_status": "structured_rows",
                "method": "proximity",
                # inputs missing
            }
        }
    )
    rec = next(r for r in art["records"] if r["target_id"] == "proximity_4_3")
    check("missing-fields: not created", rec["source_input_record_status"] == "not_created")
    check("missing-fields: not consumable", rec["machine_consumable_for_recompute"] is False)


def test_unsupported_target_family_rejected() -> None:
    # A method that does not match the target family must not create a record.
    art = build_focused_table_structure_attempt(
        source_input_candidates_by_target={
            "proximity_4_3": {
                "origin": "parsed_from_extraction_output",
                "table_structure_status": "structured_rows",
                "method": "weighted_average",  # wrong family for proximity_4_3
                "inputs": {"weighted_sum": 1, "weight_sum": 2},
            }
        }
    )
    rec = next(r for r in art["records"] if r["target_id"] == "proximity_4_3")
    check("family: not created", rec["source_input_record_status"] == "not_created")
    check("family: blocked unsupported_target_family", rec["blocked_by"] == "unsupported_target_family")


def test_hand_authored_rejected() -> None:
    art = build_focused_table_structure_attempt(
        source_input_candidates_by_target={
            "proximity_4_3": {
                "origin": "hand_authored_target_map",
                "table_structure_status": "structured_rows",
                "method": "proximity",
                "inputs": {"shared_terminal_count": 3, "tree_count": 4},
            }
        }
    )
    rec = next(r for r in art["records"] if r["target_id"] == "proximity_4_3")
    check("hand-authored: not created", rec["source_input_record_status"] == "not_created")
    check("hand-authored: not consumable", rec["machine_consumable_for_recompute"] is False)
    check("hand-authored: counted", art["summary"]["hand_authored_target_map_count"] == 1)
    check("hand-authored: warning present", "hand_authored_target_map_rejected" in rec["warnings"])


def test_fixture_derived_rejected() -> None:
    art = build_focused_table_structure_attempt(
        source_input_candidates_by_target={
            "weighted_weight_impute": {
                "origin": "fixture_derived",
                "table_structure_status": "structured_rows",
                "method": "weighted_average",
                "inputs": {"weighted_sum": 1, "weight_sum": 2},
            }
        }
    )
    rec = next(r for r in art["records"] if r["target_id"] == "weighted_weight_impute")
    check("fixture: not created", rec["source_input_record_status"] == "not_created")
    check("fixture: counted", art["summary"]["fixture_derived_count"] == 1)
    check("fixture: warning present", "fixture_derived_rejected" in rec["warnings"])


def test_answer_string_rejected() -> None:
    art = build_focused_table_structure_attempt(
        source_input_candidates_by_target={
            "proximity_4_3": {
                "origin": "answer_string_derived",
                "table_structure_status": "structured_rows",
                "method": "proximity",
                "inputs": {"shared_terminal_count": 3, "tree_count": 4},
            }
        }
    )
    rec = next(r for r in art["records"] if r["target_id"] == "proximity_4_3")
    check("answer-string: not created", rec["source_input_record_status"] == "not_created")
    check("answer-string: counted", art["summary"]["answer_string_derived_count"] == 1)
    check("answer-string: warning present", "answer_string_derived_rejected" in rec["warnings"])


def test_ocr_prose_only_not_consumable() -> None:
    art = build_focused_table_structure_attempt(
        source_input_candidates_by_target={
            "proximity_4_3": {
                "origin": "parsed_from_extraction_output",
                "table_structure_status": "ocr_prose_only",
                "method": "proximity",
                "inputs": {"shared_terminal_count": 3, "tree_count": 4},
            }
        }
    )
    rec = next(r for r in art["records"] if r["target_id"] == "proximity_4_3")
    check("prose: not created", rec["source_input_record_status"] == "not_created")
    check("prose: not consumable", rec["machine_consumable_for_recompute"] is False)
    check("prose: blocked ocr_prose_only", rec["blocked_by"] == "ocr_prose_only")
    check("prose: not counted as structured", art["summary"]["structured_rows_count"] == 0)
    check("prose: machine_consumable_count 0", art["summary"]["machine_consumable_count"] == 0)


def test_malformed_input_degrades() -> None:
    for bad in (123, "x", [1, 2], {"proximity_4_3": "not-a-dict"}):
        art = build_focused_table_structure_attempt(source_input_candidates_by_target=bad)
        check(f"degrade({type(bad).__name__}): two records", len(art["records"]) == 2)
        check(f"degrade({type(bad).__name__}): blocked", art["status"] == "blocked")
        assert_closed_vocab(f"degrade({type(bad).__name__})", art)


def test_json_serializable() -> None:
    art = build_focused_table_structure_attempt()
    text = json.dumps(art)
    check("json: round-trips", json.loads(text) == art)


def test_source_module_has_no_recompute_engine_dup() -> None:
    # Reuse, not rebuild: the focused module must not define its own recompute
    # arithmetic. It reuses SUPPORTED_METHODS from the verifier.
    src = (REPO / "pipeline" / "quality_safety_focused_table_structure_attempt.py").read_text()
    tree = ast.parse(src)
    defs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    dup = {d for d in defs if d.startswith("_recompute_")}
    check("reuse: no parallel recompute methods", not dup)
    check("reuse: imports SUPPORTED_METHODS", "SUPPORTED_METHODS" in src)


def main() -> int:
    test_real_current_state_blocked()
    test_limited_to_two_targets()
    test_structured_rows_creates_record()
    test_missing_required_fields_not_created()
    test_unsupported_target_family_rejected()
    test_hand_authored_rejected()
    test_fixture_derived_rejected()
    test_answer_string_rejected()
    test_ocr_prose_only_not_consumable()
    test_malformed_input_degrades()
    test_json_serializable()
    test_source_module_has_no_recompute_engine_dup()
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {FAILURES}")
        return 1
    print("All focused table-structure attempt checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
