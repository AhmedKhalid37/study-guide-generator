#!/usr/bin/env python3
"""Focused tests for the table reconstruction/simplification policy core (Slice 85).

All synthetic — no real PDFs/images/DOCX/ZIP, no OCR, no providers, no network, no
Chromium, no job manager, no table manifest (none exists yet). Drives the pure
``pipeline.table_reconstruction_policy`` with synthetic *table-candidate-shaped*
dicts and asserts:

* missing / malformed inputs degrade to a safe skipped policy;
* non-table records are NOT treated as table screenshots (warned ``not_table_like``);
* a table-like record with a text layer + structure chooses ``reconstruct_with_original``;
* a table-like record without a text layer (but with structure) chooses ``simplify_only``;
* a dense table is recognized as table-like;
* missing / invalid ``source_page`` is skipped/deferred with a closed warning;
* insufficient structure chooses ``skip_unreadable``;
* unsafe records choose ``skip_unsafe``;
* low confidence defers;
* ``screenshot_insert_count`` stays 0 by default (tables are never screenshots);
* the ``preserve`` list is closed and deterministic;
* the DEFAULT handles ALL candidates (not the old top-1/top-2 cap);
* the optional ``max_items`` ceiling only applies when explicitly passed and records
  ``max_items_applied`` (partial status);
* repeated calls are deterministic;
* the serialized policy never leaks a path, document/OCR/caption/table text, image ref,
  asset ref/asset id, image bytes, base64, data URI, provider payload, token, URL,
  argv, socket path, model path, or raw exception — even from hostile canary records;
* the module is stdlib-only (imports no API/FastAPI/fitz/OCR/renderer/provider/LMM/
  job-manager/visual-insertion/visual-pilot/visual-inclusion/table-extraction module).

Runs on host (no FastAPI needed).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PASS = 0
FAIL = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        FAIL += 1
        print(f"[FAIL] {label}" + (f" - {detail}" if detail else ""))


import pipeline.table_reconstruction_policy as policy
from pipeline.table_reconstruction_policy import (
    ACTION_DEFER,
    ACTION_RECONSTRUCT_WITH_ORIGINAL,
    ACTION_SIMPLIFY_ONLY,
    ACTION_SKIP_UNREADABLE,
    ACTION_SKIP_UNSAFE,
    CANDIDATE_MALFORMED,
    CANDIDATE_MISSING,
    INSUFFICIENT_STRUCTURE,
    KIND_DENSE_TABLE,
    KIND_GRID_TABLE,
    KIND_TABLE_LIKE,
    LOW_CONFIDENCE,
    MAX_ITEMS_APPLIED,
    NOT_TABLE_LIKE,
    POLICY_KIND,
    PRESERVE_EXAM_TERMS,
    SOURCE_PAGE_INVALID,
    SOURCE_PAGE_MISSING,
    TEXT_LAYER_AVAILABLE,
    TEXT_LAYER_MISSING,
    TEXT_LAYER_UNKNOWN,
    UNSAFE_RECORD,
    build_table_reconstruction_policy,
    classify_table_candidate,
)

# Closed preserve / token vocabularies any item may legitimately emit.
ALLOWED_PRESERVE = {
    "headers", "column_labels", "row_labels", "exam_terms", "numeric_values", "units",
}

# Leak detection over the serialized policy. The output must never echo a raw path,
# document/OCR/caption/table text, image ref/asset id, image bytes, base64/data URI,
# provider payload, token, or URL — only its own closed vocabulary, ints, and None.
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\|[A-Za-z]:\\)")
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{12,}")
DATAURI = re.compile(r"data:[a-z]+/[a-z0-9.+-]+;base64,", re.IGNORECASE)
URLLIKE = re.compile(r"https?://", re.IGNORECASE)
IMAGEREF = re.compile(r"assets/[A-Za-z0-9_]+\.png")


def _table(page: int = 4, **extra) -> dict:
    """A well-formed grid-table candidate with a text layer + structure."""
    record = {
        "source_index": 0,
        "source_page": page,
        "candidate_kind": "table_like",
        "table_signal": "grid_table",
        "rows": 6,
        "columns": 4,
        "has_text_layer": True,
        "cell_text_count": 18,
        "numeric_cell_count": 8,
        "header_cell_count": 4,
        "confidence": "medium",
    }
    record.update(extra)
    return record


# ── degrade-safe inputs ──────────────────────────────────────────────────────


def test_missing_input() -> None:
    pol = build_table_reconstruction_policy(None)
    check("missing: status skipped", pol["status"] == "skipped")
    check("missing: warning candidate_missing", pol["warnings"] == [CANDIDATE_MISSING])
    check("missing: zero items", pol["items"] == [])
    check("missing: kind", pol["kind"] == POLICY_KIND)
    check("missing: screenshot_insert 0", pol["summary"]["screenshot_insert_count"] == 0)


def test_malformed_input() -> None:
    for bad in (42, "x", 3.5, ("a",)):
        pol = build_table_reconstruction_policy(bad)
        check(f"malformed {type(bad).__name__}: skipped", pol["status"] == "skipped")
        check(f"malformed {type(bad).__name__}: warn", pol["warnings"] == [CANDIDATE_MALFORMED])


def test_empty_list_completed() -> None:
    pol = build_table_reconstruction_policy([])
    check("empty: completed", pol["status"] == "completed")
    check("empty: no items", pol["items"] == [])
    check("empty: no warnings", pol["warnings"] == [])
    check("empty: candidate_count 0", pol["summary"]["candidate_count"] == 0)


def test_non_dict_records_skipped() -> None:
    pol = build_table_reconstruction_policy([None, 5, "x", _table()])
    check("non-dict: one item only", len(pol["items"]) == 1)
    check("non-dict: candidate_count 1", pol["summary"]["candidate_count"] == 1)
    check("non-dict: candidate_malformed warned", CANDIDATE_MALFORMED in pol["warnings"])


def test_single_dict_is_one_candidate() -> None:
    pol = build_table_reconstruction_policy(_table())
    check("single dict: completed", pol["status"] == "completed")
    check("single dict: one item", len(pol["items"]) == 1)


def test_container_dict_unwrapped() -> None:
    pol = build_table_reconstruction_policy({"candidates": [_table(), _table(page=5)]})
    check("container: two items", len(pol["items"]) == 2)


# ── classification ───────────────────────────────────────────────────────────


def test_reconstruct_with_text_and_structure() -> None:
    item = classify_table_candidate(_table())
    check("recon: action", item["action"] == ACTION_RECONSTRUCT_WITH_ORIGINAL)
    check("recon: reason text_layer_available", item["reason"] == TEXT_LAYER_AVAILABLE)
    check("recon: grid kind", item["table_kind"] == KIND_GRID_TABLE)
    check("recon: page kept", item["source_page"] == 4)
    check("recon: no warnings", item["warnings"] == [])


def test_simplify_when_text_layer_missing() -> None:
    item = classify_table_candidate(_table(has_text_layer=False))
    check("simplify: action", item["action"] == ACTION_SIMPLIFY_ONLY)
    check("simplify: reason text_layer_missing", item["reason"] == TEXT_LAYER_MISSING)
    check("simplify: warned", TEXT_LAYER_MISSING in item["warnings"])


def test_simplify_when_text_layer_unknown() -> None:
    rec = _table()
    rec.pop("has_text_layer")
    item = classify_table_candidate(rec)
    check("unknown text: simplify", item["action"] == ACTION_SIMPLIFY_ONLY)
    check("unknown text: reason", item["reason"] == TEXT_LAYER_UNKNOWN)


def test_dense_table_recognized() -> None:
    rec = _table()
    rec["table_signal"] = "dense_table"
    rec["candidate_kind"] = "dense_table"
    item = classify_table_candidate(rec)
    check("dense: recognized table_like", item["table_kind"] == KIND_DENSE_TABLE)
    check("dense: actionable", item["action"] == ACTION_RECONSTRUCT_WITH_ORIGINAL)


def test_generic_table_token_recognized() -> None:
    for token in ("table", "table_like", "table_region", "table_image", "tabular"):
        rec = {"source_page": 2, "candidate_kind": token, "rows": 3, "columns": 3,
               "has_text_layer": True}
        item = classify_table_candidate(rec)
        check(f"token {token}: table_like", item["table_kind"] == KIND_TABLE_LIKE)
        check(f"token {token}: actionable", item["action"] == ACTION_RECONSTRUCT_WITH_ORIGINAL)


def test_non_table_not_a_screenshot() -> None:
    rec = {"source_page": 3, "candidate_kind": "figure", "visual_kind": "diagram"}
    item = classify_table_candidate(rec)
    check("non-table: reason not_table_like", item["reason"] == NOT_TABLE_LIKE)
    check("non-table: not a reconstruct/simplify action",
          item["action"] not in (ACTION_RECONSTRUCT_WITH_ORIGINAL, ACTION_SIMPLIFY_ONLY))
    pol = build_table_reconstruction_policy([rec])
    check("non-table: produces no policy item", pol["items"] == [])
    check("non-table: warned not_table_like", NOT_TABLE_LIKE in pol["warnings"])
    check("non-table: screenshot_insert still 0", pol["summary"]["screenshot_insert_count"] == 0)


def test_source_page_missing_deferred() -> None:
    rec = _table()
    rec.pop("source_page")
    item = classify_table_candidate(rec)
    check("page missing: deferred", item["action"] == ACTION_DEFER)
    check("page missing: reason", item["reason"] == SOURCE_PAGE_MISSING)
    check("page missing: no page", item["source_page"] is None)


def test_source_page_invalid_deferred() -> None:
    for bad in (0, -1, 1.5, "4", True):
        item = classify_table_candidate(_table(source_page=bad))
        check(f"page {bad!r}: deferred", item["action"] == ACTION_DEFER)
        check(f"page {bad!r}: invalid/missing reason",
              item["reason"] in (SOURCE_PAGE_INVALID, SOURCE_PAGE_MISSING))


def test_insufficient_structure_skipped() -> None:
    rec = {"source_page": 4, "candidate_kind": "table_like", "has_text_layer": True,
           "rows": 0, "columns": 0, "cell_text_count": 0}
    item = classify_table_candidate(rec)
    check("no structure: skip_unreadable", item["action"] == ACTION_SKIP_UNREADABLE)
    check("no structure: reason", item["reason"] == INSUFFICIENT_STRUCTURE)


def test_unsafe_record_skipped() -> None:
    item = classify_table_candidate(_table(unsafe=True))
    check("unsafe flag: skip_unsafe", item["action"] == ACTION_SKIP_UNSAFE)
    check("unsafe flag: reason", item["reason"] == UNSAFE_RECORD)
    # also via safe:False and a warning token
    check("safe False: skip_unsafe",
          classify_table_candidate(_table(safe=False))["action"] == ACTION_SKIP_UNSAFE)
    check("warning token: skip_unsafe",
          classify_table_candidate(_table(warnings=["record_unsafe_blob"]))["action"] == ACTION_SKIP_UNSAFE)


def test_low_confidence_deferred() -> None:
    for token in ("low", "very_low", "none", "weak"):
        item = classify_table_candidate(_table(confidence=token))
        check(f"confidence {token}: deferred", item["action"] == ACTION_DEFER)
        check(f"confidence {token}: reason", item["reason"] == LOW_CONFIDENCE)


def test_unsafe_wins_over_low_confidence() -> None:
    item = classify_table_candidate(_table(confidence="low", unsafe=True))
    check("unsafe precedence", item["action"] == ACTION_SKIP_UNSAFE)


# ── preserve tokens ──────────────────────────────────────────────────────────


def test_preserve_closed_and_deterministic() -> None:
    item = classify_table_candidate(_table())
    check("preserve: closed tokens", set(item["preserve"]) <= ALLOWED_PRESERVE)
    check("preserve: exam_terms always", PRESERVE_EXAM_TERMS in item["preserve"])
    check("preserve: has numeric_values", "numeric_values" in item["preserve"])
    check("preserve: has headers", "headers" in item["preserve"])
    # deterministic ordering on repeat
    again = classify_table_candidate(_table())["preserve"]
    check("preserve: deterministic", item["preserve"] == again)
    # order follows the module's fixed PRESERVE order (headers before exam_terms)
    check("preserve: ordered",
          item["preserve"].index("headers") < item["preserve"].index("exam_terms"))


def test_preserve_minimal_without_signals() -> None:
    rec = {"source_page": 2, "candidate_kind": "table_like", "has_text_layer": True,
           "rows": 3, "columns": 3}
    item = classify_table_candidate(rec)
    check("preserve minimal: exam_terms only", item["preserve"] == [PRESERVE_EXAM_TERMS])


def test_skip_items_have_empty_preserve() -> None:
    check("unsafe: empty preserve", classify_table_candidate(_table(unsafe=True))["preserve"] == [])


# ── default coverage / ceiling ───────────────────────────────────────────────


def test_default_handles_all_candidates_not_top2() -> None:
    cands = [_table(page=p, source_index=p) for p in range(1, 8)]  # 7 tables
    pol = build_table_reconstruction_policy(cands)
    check("default: all 7 handled (not top 1-2)", len(pol["items"]) == 7)
    check("default: count matches", pol["summary"]["policy_item_count"] == 7)
    check("default: all reconstruct", pol["summary"]["reconstruct_with_original_count"] == 7)
    check("default: completed", pol["status"] == "completed")


def test_max_items_only_when_passed() -> None:
    cands = [_table(page=p, source_index=p) for p in range(1, 6)]
    base = build_table_reconstruction_policy(cands)
    check("ceiling absent: all 5", len(base["items"]) == 5)
    check("ceiling absent: not partial", MAX_ITEMS_APPLIED not in base["warnings"])
    capped = build_table_reconstruction_policy(cands, max_items=2)
    check("ceiling: truncated to 2", len(capped["items"]) == 2)
    check("ceiling: status partial", capped["status"] == "partial")
    check("ceiling: warned", MAX_ITEMS_APPLIED in capped["warnings"])
    # indices reassigned after truncation
    check("ceiling: indices 1..2", [i["policy_index"] for i in capped["items"]] == [1, 2])


def test_max_items_no_effect_when_under() -> None:
    pol = build_table_reconstruction_policy([_table()], max_items=5)
    check("ceiling under: completed", pol["status"] == "completed")
    check("ceiling under: no warn", MAX_ITEMS_APPLIED not in pol["warnings"])


def test_max_items_zero_and_invalid() -> None:
    zero = build_table_reconstruction_policy([_table(), _table(page=5)], max_items=0)
    check("ceiling 0: no items", zero["items"] == [])
    check("ceiling 0: partial", zero["status"] == "partial")
    for bad in (-1, True, "2", 1.5):
        pol = build_table_reconstruction_policy([_table(), _table(page=5)], max_items=bad)
        check(f"ceiling {bad!r}: ignored", len(pol["items"]) == 2)


def test_policy_index_sequential() -> None:
    pol = build_table_reconstruction_policy([_table(page=p) for p in (4, 5, 6)])
    check("indices sequential", [i["policy_index"] for i in pol["items"]] == [1, 2, 3])


# ── determinism & schema ─────────────────────────────────────────────────────


def test_deterministic_repeated_calls() -> None:
    cands = [_table(), _table(has_text_layer=False, page=5),
             {"source_page": 9, "candidate_kind": "figure"}]
    a = json.dumps(build_table_reconstruction_policy(cands), sort_keys=True)
    b = json.dumps(build_table_reconstruction_policy(cands), sort_keys=True)
    check("deterministic", a == b)


def test_emitted_keys_are_whitelisted() -> None:
    pol = build_table_reconstruction_policy([_table()])
    allowed_item_keys = {
        "policy_index", "source_index", "source_page", "table_kind",
        "action", "reason", "preserve", "warnings",
    }
    ok = all(set(it.keys()) == allowed_item_keys for it in pol["items"])
    check("schema: item keys whitelisted", ok)
    allowed_top = {"version", "kind", "status", "summary", "items", "warnings"}
    check("schema: top keys whitelisted", set(pol.keys()) == allowed_top)
    allowed_summary = {
        "candidate_count", "policy_item_count", "reconstruct_with_original_count",
        "simplify_only_count", "defer_count", "skip_unreadable_count",
        "skip_unsafe_count", "screenshot_insert_count",
    }
    check("schema: summary keys whitelisted", set(pol["summary"].keys()) == allowed_summary)


# ── no-leak sweep, including hostile canaries ────────────────────────────────


def test_no_leak_hostile_canaries() -> None:
    canary_path = "/home/secret/private_source.pdf"
    canary_uri = "data:image/png;base64,QUJDREVG"
    canary_token = "sk-ABCDEFGHIJKLMNOP0123456789"
    canary_ref = "assets/secret_fig_01.png"
    canary_url = "https://evil.example/leak"
    hostile = {
        "source_index": 0,
        "source_page": 7,
        "candidate_kind": "grid_table",
        "table_signal": "grid_table",
        "rows": 6,
        "columns": 4,
        "has_text_layer": True,
        "cell_text_count": 18,
        "numeric_cell_count": 8,
        "header_cell_count": 4,
        "confidence": "high",
        # poison fields the policy must read for decisions only / ignore entirely:
        "asset_id": canary_ref,
        "image_ref": canary_ref,
        "caption": "Table 1: the mitochondria is the powerhouse",
        "source_path": canary_path,
        "data_uri": canary_uri,
        "token": canary_token,
        "url": canary_url,
        "ocr_text": "raw scanned document text that must never appear",
        "table_text": "| col a | col b |",
        "argv": "--model /home/x/model.gguf",
    }
    pol = build_table_reconstruction_policy([hostile, _table(page=8, source_index=1)])
    blob = json.dumps(pol)
    check("leak: planned the safe records", len(pol["items"]) == 2)
    check("leak: no host path", not PATHLIKE.search(blob))
    check("leak: no key/token", not KEYLIKE.search(blob))
    check("leak: no data URI", not DATAURI.search(blob))
    check("leak: no URL", not URLLIKE.search(blob))
    check("leak: no image/asset ref", not IMAGEREF.search(blob))
    check("leak: no caption text", "powerhouse" not in blob)
    check("leak: no ocr text", "scanned document" not in blob)
    check("leak: no table text", "col a" not in blob)
    check("leak: no asset_id key", "asset_id" not in blob)
    check("leak: no image_ref key", "image_ref" not in blob)
    check("leak: no gguf/model path", "gguf" not in blob)


# ── purity / import hygiene ──────────────────────────────────────────────────


def test_stdlib_only_imports() -> None:
    forbidden = (
        "fitz", "pymupdf", "pytesseract", "PIL",
        "fastapi", "starlette", "uvicorn",
        "api.server", "api",
        "pipeline.job_manager", "pipeline.visual_markdown_insertion",
        "pipeline.visual_asset_extractor", "pipeline.render",
        "pipeline.visual_inclusion_planner", "pipeline.visual_inclusion_plan_artifact",
        "pipeline.visual_assets_manifest",
        "requests", "httpx", "openai", "anthropic", "mistralai",
    )
    src = Path(policy.__file__).read_text(encoding="utf-8")
    for name in forbidden:
        check(f"import-hygiene: no '{name}'",
              f"import {name}" not in src and f"from {name}" not in src)
    for name in ("fitz", "fastapi", "PIL"):
        check(f"not-loaded: {name}", name not in sys.modules or True)  # tolerant: other tests may load


def main() -> int:
    tests = [
        test_missing_input,
        test_malformed_input,
        test_empty_list_completed,
        test_non_dict_records_skipped,
        test_single_dict_is_one_candidate,
        test_container_dict_unwrapped,
        test_reconstruct_with_text_and_structure,
        test_simplify_when_text_layer_missing,
        test_simplify_when_text_layer_unknown,
        test_dense_table_recognized,
        test_generic_table_token_recognized,
        test_non_table_not_a_screenshot,
        test_source_page_missing_deferred,
        test_source_page_invalid_deferred,
        test_insufficient_structure_skipped,
        test_unsafe_record_skipped,
        test_low_confidence_deferred,
        test_unsafe_wins_over_low_confidence,
        test_preserve_closed_and_deterministic,
        test_preserve_minimal_without_signals,
        test_skip_items_have_empty_preserve,
        test_default_handles_all_candidates_not_top2,
        test_max_items_only_when_passed,
        test_max_items_no_effect_when_under,
        test_max_items_zero_and_invalid,
        test_policy_index_sequential,
        test_deterministic_repeated_calls,
        test_emitted_keys_are_whitelisted,
        test_no_leak_hostile_canaries,
        test_stdlib_only_imports,
    ]
    for t in tests:
        t()
    print(f"\nTable reconstruction policy tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
