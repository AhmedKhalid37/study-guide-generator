#!/usr/bin/env python3
"""Focused tests for the pure visual insertion planner core (Slice 52, roadmap V3+).

Run with:

    python test_scripts/test_visual_insertion_planner.py

No external APIs and no PyMuPDF/Tesseract/llama.cpp/Mistral/Gemini/Chandra-runtime
or Local-Model-Manager dependency: the planner is a pure function of already-
sanitized ``visual_replacement_plan.json``-shaped items (optionally placed against a
safe-only source-page anchor inventory), so these tests feed it tiny *handcrafted
synthetic* records. No real model dumps, private documents, screenshots, image
bytes, or local paths are used.
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

# Leak detectors — none of these may appear anywhere in planner output.
KEYLIKE = re.compile(r"(sk-|sk_|pk-|rk_)[A-Za-z0-9_\-]{12,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/root/|/tmp/|/opt/|C:\\|\\\\)")
URLLIKE = re.compile(r"https?://|file://|ftp://")
AUTHLIKE = re.compile(r"Authorization|Bearer\s+\S", re.IGNORECASE)
SOCKETLIKE = re.compile(r"\.sock\b")
ARGVLIKE = re.compile(r"(?<!\S)--[A-Za-z]")
BASE64URI = re.compile(r"data:[^;]+;base64,")
GGUFLIKE = re.compile(r"\.gguf\b|mmproj", re.IGNORECASE)

from pipeline.visual_insertion_planner import (  # noqa: E402
    ANCHOR_STATUSES,
    ASSET_TYPES,
    CANDIDATE_ACTIONS,
    INSERTION_MODES,
    PLACEMENTS,
    REASONS,
    REPORT_KIND,
    REPORT_VERSION,
    SOURCE_PROVIDERS,
    WARNINGS,
    build_visual_insertion_plan,
    plan_visual_insertion_item,
    plan_visual_insertions,
)


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        msg = f"[FAIL] {name}"
        if detail:
            msg += f" - {detail}"
        print(msg)


def _is_json_safe(obj) -> bool:
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


def _item_keys() -> set:
    return {
        "asset_id", "source_page", "source_provider", "asset_type",
        "candidate_action", "insertion_mode", "placement", "anchor_id",
        "anchor_status", "reasons", "warnings",
    }


def _vocab_ok(item: dict) -> bool:
    return (
        item["asset_type"] in ASSET_TYPES
        and item["source_provider"] in SOURCE_PROVIDERS
        and item["candidate_action"] in CANDIDATE_ACTIONS
        and item["insertion_mode"] in INSERTION_MODES
        and item["placement"] in PLACEMENTS
        and item["anchor_status"] in ANCHOR_STATUSES
        and (item["anchor_id"] is None or re.fullmatch(r"[A-Za-z0-9_]+", item["anchor_id"]))
        and all(r in REASONS for r in item["reasons"])
        and all(w in WARNINGS for w in item["warnings"])
    )


# --- Synthetic replacement-plan-shaped fixtures (no real data) ----------------

def _item(candidate_action: str, asset_type: str, *, asset_id: str = "page_0001_visual_01",
          source_page: int = 1, provider: str = "fitz_local", priority: str = "high") -> dict:
    return {
        "asset_id": asset_id,
        "source_page": source_page,
        "source_provider": provider,
        "asset_type": asset_type,
        "priority": priority,
        "candidate_action": candidate_action,
        "placement": "source_page_reference",
        "reasons": ["score_high"],
        "warnings": [],
    }


def _plan(items: list) -> dict:
    return {
        "version": 1,
        "kind": "visual_replacement_plan",
        "status": "completed",
        "source": "visual_asset_scoring.json",
        "items": items,
        "summary": {"item_count": len(items)},
        "warnings": [],
    }


def _anchors_list(pages: list) -> list:
    return [{"source_page": p, "anchor_id": f"source_page_{p:04d}"} for p in pages]


# --- 1. include-as-figure + matching anchor → figure_reference ----------------

def test_include_as_figure_matched() -> None:
    anchors = _anchors_list([2])
    for atype in ("diagram", "extracted_figure", "figure", "image_region", "cropped_region"):
        item = plan_visual_insertion_item(
            _item("candidate_include_as_figure", atype, source_page=2), anchors_by_page=anchors
        )
        check(f"fig.keys[{atype}]", set(item) == _item_keys(), str(set(item)))
        check(f"fig.vocab[{atype}]", _vocab_ok(item))
        check(f"fig.mode[{atype}]", item["insertion_mode"] == "figure_reference", item["insertion_mode"])
        check(f"fig.placement[{atype}]", item["placement"] == "source_page_reference", item["placement"])
        check(f"fig.anchor_status[{atype}]", item["anchor_status"] == "matched", item["anchor_status"])
        check(f"fig.anchor_id[{atype}]", item["anchor_id"] == "source_page_0002", item["anchor_id"])
        check(f"fig.reason_matched[{atype}]", "anchor_matched" in item["reasons"])
        check(f"fig.reason_action[{atype}]", "candidate_include_as_figure" in item["reasons"])
        check(f"fig.page[{atype}]", item["source_page"] == 2)
        check(f"fig.json_safe[{atype}]", _is_json_safe(item))


# --- 2. convert-to-table + matching anchor → table_reference ------------------

def test_convert_to_table_matched() -> None:
    anchors = {1: "source_page_0001"}
    for atype in ("table", "table_region"):
        item = plan_visual_insertion_item(
            _item("candidate_convert_to_table", atype), anchors_by_page=anchors
        )
        check(f"tbl.mode[{atype}]", item["insertion_mode"] == "table_reference", item["insertion_mode"])
        check(f"tbl.placement[{atype}]", item["placement"] == "source_page_reference")
        check(f"tbl.anchor[{atype}]", item["anchor_status"] == "matched" and item["anchor_id"] == "source_page_0001")
        check(f"tbl.reason[{atype}]", "candidate_convert_to_table" in item["reasons"])


# --- 3. summarize-as-text + matching anchor → text_summary_reference ----------

def test_summarize_as_text_matched() -> None:
    anchors = _anchors_list([1])
    item = plan_visual_insertion_item(
        _item("candidate_summarize_as_text", "equation_block"), anchors_by_page=anchors
    )
    check("txt.mode", item["insertion_mode"] == "text_summary_reference", item["insertion_mode"])
    check("txt.placement", item["placement"] == "source_page_reference")
    check("txt.anchor", item["anchor_status"] == "matched")
    check("txt.reason", "candidate_summarize_as_text" in item["reasons"])


# --- 4. review-only → review_only, anchor not required ------------------------

def test_review_only_no_anchor_required() -> None:
    # No anchors supplied at all; review_only must still resolve cleanly.
    item = plan_visual_insertion_item(_item("review_only", "page_visual_signal", priority="low"))
    check("rev.mode", item["insertion_mode"] == "review_only", item["insertion_mode"])
    check("rev.placement", item["placement"] == "review_appendix", item["placement"])
    check("rev.anchor_status", item["anchor_status"] == "not_required", item["anchor_status"])
    check("rev.anchor_id_none", item["anchor_id"] is None)
    check("rev.reason_review", "review_only" in item["reasons"])
    check("rev.reason_appendix", "review_appendix" in item["reasons"])
    check("rev.low_info", "low_information_signal" in item["reasons"])
    check("rev.no_anchor_warning", "anchor_lookup_missing" not in item["warnings"])
    check("rev.vocab", _vocab_ok(item))


# --- 5. missing anchor degrades safely ---------------------------------------

def test_missing_anchor_degrades() -> None:
    # Reference action but no anchor inventory at all.
    item = plan_visual_insertion_item(_item("candidate_include_as_figure", "diagram"))
    check("miss.mode_kept", item["insertion_mode"] == "figure_reference", item["insertion_mode"])
    check("miss.anchor_status", item["anchor_status"] == "missing", item["anchor_status"])
    check("miss.anchor_id_none", item["anchor_id"] is None)
    check("miss.placement_unknown", item["placement"] == "unknown", item["placement"])
    check("miss.reason", "anchor_missing" in item["reasons"])
    check("miss.warning", "anchor_lookup_missing" in item["warnings"])
    check("miss.vocab", _vocab_ok(item))

    # Inventory present but does NOT cover the item's source page.
    item2 = plan_visual_insertion_item(
        _item("candidate_convert_to_table", "table", source_page=9), anchors_by_page=_anchors_list([1, 2])
    )
    check("miss.page_uncovered_status", item2["anchor_status"] == "missing")
    check("miss.page_uncovered_warning", "anchor_lookup_missing" in item2["warnings"])
    check("miss.page_uncovered_reason", "anchor_missing" in item2["reasons"])


# --- 6. malformed replacement plan → safe completed report -------------------

def test_malformed_plan() -> None:
    for bad in (None, 123, "nope", [], object(), {"items": "not-a-list"}, {"no_items": 1}):
        report = build_visual_insertion_plan(bad)  # type: ignore[arg-type]
        check(f"plan.completed[{type(bad).__name__}]", report["status"] == "completed")
        check(f"plan.kind[{type(bad).__name__}]", report["kind"] == REPORT_KIND == "visual_insertion_plan")
        check(f"plan.empty[{type(bad).__name__}]", report["insertions"] == [])
        check(f"plan.json_safe[{type(bad).__name__}]", _is_json_safe(report))
    r1 = build_visual_insertion_plan({"items": "nope"})
    check("plan.bad_items_warning", "replacement_plan_malformed" in r1["warnings"])
    r2 = build_visual_insertion_plan(None)
    check("plan.nondict_warning", "replacement_plan_malformed" in r2["warnings"])
    # Valid empty plan → completed, no warning.
    r3 = build_visual_insertion_plan(_plan([]))
    check("plan.empty_ok", r3["status"] == "completed" and r3["warnings"] == [])
    check("plan.empty_summary", r3["summary"]["insertion_count"] == 0)
    check("plan.envelope", r3["version"] == REPORT_VERSION and r3["source"] == "visual_replacement_plan.json")


# --- 7. malformed item → safe fallback with unknown --------------------------

def test_malformed_item() -> None:
    for bad in (None, 123, "x", [], object()):
        item = plan_visual_insertion_item(bad)  # type: ignore[arg-type]
        check(f"mal.mode[{type(bad).__name__}]", item["insertion_mode"] == "unknown")
        check(f"mal.action[{type(bad).__name__}]", item["candidate_action"] == "unknown")
        check(f"mal.warning[{type(bad).__name__}]", "replacement_item_malformed" in item["warnings"])
        check(f"mal.vocab[{type(bad).__name__}]", _vocab_ok(item))
        check(f"mal.fallback_id[{type(bad).__name__}]", item["asset_id"] == "asset_0001", item["asset_id"])
        check(f"mal.placement[{type(bad).__name__}]", item["placement"] == "unknown")
        check(f"mal.anchor_unknown[{type(bad).__name__}]", item["anchor_status"] == "unknown")
    # Mixed list keeps positional fallback ids.
    items = plan_visual_insertions([_item("candidate_convert_to_table", "table"), None, 42])
    check("mal.mixed_len", len(items) == 3)
    check("mal.mixed_ids", items[1]["asset_id"] == "asset_0002" and items[2]["asset_id"] == "asset_0003")
    # An unrecognized candidate_action degrades to unknown with a warning.
    weird = _item("not_a_real_action", "table")
    w = plan_visual_insertion_item(weird)
    check("mal.action_coerced", w["insertion_mode"] == "unknown" and w["candidate_action"] == "unknown")
    check("mal.action_warning", "candidate_action_unrecognized" in w["warnings"])


# --- 8. invalid asset ids → deterministic safe fallback / sanitized ----------

def test_asset_id_fallback() -> None:
    missing = _item("candidate_convert_to_table", "table")
    del missing["asset_id"]
    item = plan_visual_insertion_item(missing)
    check("id.missing_fallback", item["asset_id"] == "asset_0001", item["asset_id"])
    check("id.missing_warning", "asset_id_missing" in item["warnings"])

    nonstr = _item("candidate_convert_to_table", "table")
    nonstr["asset_id"] = 12345
    s2 = plan_visual_insertion_item(nonstr)
    check("id.nonstr_fallback", s2["asset_id"] == "asset_0001")
    check("id.nonstr_warning", "asset_id_missing" in s2["warnings"])

    unsafe = _item("candidate_convert_to_table", "table", asset_id="../../etc/passwd")
    s3 = plan_visual_insertion_item(unsafe)
    check("id.unsafe_sanitized", re.fullmatch(r"[A-Za-z0-9_]+", s3["asset_id"]) is not None, s3["asset_id"])
    check("id.unsafe_warning", "asset_id_invalid" in s3["warnings"])
    check("id.unsafe_no_path", "/" not in s3["asset_id"] and ".." not in s3["asset_id"])

    empty = _item("candidate_convert_to_table", "table", asset_id="///")
    s4 = plan_visual_insertion_item(empty)
    check("id.empty_after_sanitize", s4["asset_id"] == "asset_0001")
    check("id.empty_warning", "asset_id_invalid" in s4["warnings"])

    items = plan_visual_insertions([{"candidate_action": "candidate_convert_to_table", "asset_type": "table"},
                                    {"candidate_action": "candidate_include_as_figure", "asset_type": "figure"}])
    check("id.list_fallback_seq", [s["asset_id"] for s in items] == ["asset_0001", "asset_0002"])


# --- 9. invalid source page → None plus warning ------------------------------

def test_source_page_invalid() -> None:
    for bad_page in ("not-a-number", -3, 0, [1], {"p": 1}):
        item = plan_visual_insertion_item(_item("candidate_convert_to_table", "table", source_page=bad_page))  # type: ignore[arg-type]
        check(f"page.none[{bad_page!r}]", item["source_page"] is None, str(item["source_page"]))
        check(f"page.warning[{bad_page!r}]", "source_page_invalid" in item["warnings"])
        # An item with no usable page cannot match an anchor.
        check(f"page.anchor_missing[{bad_page!r}]", item["anchor_status"] == "missing")
    # Missing source_page (absent key) → None, no warning.
    no_page = _item("review_only", "page_visual_signal", priority="low")
    del no_page["source_page"]
    item = plan_visual_insertion_item(no_page)
    check("page.absent_none", item["source_page"] is None)
    check("page.absent_no_warning", "source_page_invalid" not in item["warnings"])


# --- 10. invalid anchor id is not emitted ------------------------------------

def test_invalid_anchor_not_emitted() -> None:
    # Anchor entry carries an unsafe/unslugged id and a smuggled path: it is dropped.
    anchors = [{"source_page": 1, "anchor_id": "/home/victim/secret.png"},
               {"source_page": 2, "anchor_id": ""}]
    report = build_visual_insertion_plan(
        _plan([_item("candidate_include_as_figure", "diagram", source_page=1)]),
        source_page_anchors=anchors,
    )
    item = report["insertions"][0]
    # The id slugifies to a safe token if anything survives; here the unsafe entry's
    # path collapses to a slug-safe token only — but it must never echo the path.
    blob = json.dumps(report)
    check("anchor.no_path_leak", "/home/" not in blob and "secret.png" not in blob, blob)
    check("anchor.id_safe_or_none", item["anchor_id"] is None or re.fullmatch(r"[A-Za-z0-9_]+", item["anchor_id"]))
    # The empty anchor id (page 2) is dropped, surfacing a report-level warning.
    check("anchor.invalid_warning", "anchor_id_invalid" in report["warnings"])
    # An anchor whose id sanitizes to empty makes its page unmatchable.
    only_empty = build_visual_insertion_plan(
        _plan([_item("candidate_include_as_figure", "diagram", source_page=2)]),
        source_page_anchors=[{"source_page": 2, "anchor_id": "***"}],
    )
    it2 = only_empty["insertions"][0]
    check("anchor.empty_dropped", it2["anchor_status"] == "missing" and it2["anchor_id"] is None)
    check("anchor.empty_warning", "anchor_id_invalid" in only_empty["warnings"])


# --- 11. Chandra item: advisory only, never a direct insertion ---------------

def test_chandra_blocked() -> None:
    anchors = _anchors_list([1])
    # chandra_local provider: even an include-as-figure action must NOT become figure_reference.
    item = plan_visual_insertion_item(
        _item("candidate_include_as_figure", "diagram", provider="chandra_local"), anchors_by_page=anchors
    )
    check("chandra.not_figure", item["insertion_mode"] != "figure_reference", item["insertion_mode"])
    check("chandra.review_only", item["insertion_mode"] == "review_only")
    check("chandra.placement", item["placement"] == "review_appendix")
    check("chandra.anchor_not_required", item["anchor_status"] == "not_required")
    check("chandra.anchor_id_none", item["anchor_id"] is None)
    check("chandra.reason", "chandra_blocked" in item["reasons"])
    check("chandra.provider", item["source_provider"] == "chandra_local")
    check("chandra.vocab", _vocab_ok(item))
    # A chandra_blocked marker on a fitz item also blocks a direct insertion.
    marked = _item("candidate_convert_to_table", "table")
    marked["reasons"] = ["score_high", "chandra_blocked"]
    m = plan_visual_insertion_item(marked, anchors_by_page=anchors)
    check("chandra.marker_review_only", m["insertion_mode"] == "review_only")
    check("chandra.marker_reason", "chandra_blocked" in m["reasons"])


# --- 12. no mutation of replacement plan or anchors --------------------------

def test_no_mutation() -> None:
    plan = _plan([
        _item("candidate_convert_to_table", "table", asset_id="page_0002_fig_01", source_page=2),
        _item("candidate_summarize_as_text", "equation_block", asset_id="page_0003_eq_01"),
        _item("review_only", "page_visual_signal", asset_id="page_0001_visual_01", priority="low"),
    ])
    anchors = _anchors_list([1, 2])
    plan_before = copy.deepcopy(plan)
    anchors_before = copy.deepcopy(anchors)
    report = build_visual_insertion_plan(plan, source_page_anchors=anchors)
    check("nomut.plan", plan == plan_before)
    check("nomut.anchors", anchors == anchors_before)
    check("nomut.report_is_new", report is not plan and report is not anchors)
    check("nomut.summary", report["summary"]["insertion_count"] == 3)


# --- 13. smuggled secrets / paths never leak ---------------------------------

def test_smuggled_content_does_not_leak() -> None:
    hostile = {
        "asset_id": "page /home/victim/secret.pdf 01",
        "source_page": "https://evil.example.com/x",
        "asset_type": "Authorization: Bearer sk-ABCDEF0123456789ABCDEF",
        "source_provider": "/run/companion/host.sock --model /opt/models/x.gguf",
        "priority": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==",
        "candidate_action": "see C:\\Users\\me\\key.txt and --image-min-tokens 1024",
        "placement": "/home/victim/leak.png",
        "caption": "CONFIDENTIAL patient John Doe MRN 12345",
        "image_ref": "/home/victim/leak.png",
        "asset_ref": "/opt/models/chandra.mmproj",
        "include_score": "sk_live_0123456789ABCDEFGHIJ",
        "reasons": ["smuggled --flag /etc/passwd"],
        "warnings": ["ftp://x/y"],
    }
    hostile_anchors = [{"source_page": 1, "anchor_id": "Bearer sk-LEAK /etc/shadow"}]
    item = plan_visual_insertion_item(hostile, anchors_by_page=hostile_anchors)
    report = build_visual_insertion_plan(_plan([hostile]), source_page_anchors=hostile_anchors)
    for label, obj in (("item", item), ("report", report)):
        blob = json.dumps(obj)
        check(f"leak.no_url[{label}]", not URLLIKE.search(blob), blob)
        check(f"leak.no_path[{label}]", not PATHLIKE.search(blob), blob)
        check(f"leak.no_auth[{label}]", not AUTHLIKE.search(blob), blob)
        check(f"leak.no_socket[{label}]", not SOCKETLIKE.search(blob), blob)
        check(f"leak.no_argv[{label}]", not ARGVLIKE.search(blob), blob)
        check(f"leak.no_keylike[{label}]", not KEYLIKE.search(blob), blob)
        check(f"leak.no_base64uri[{label}]", not BASE64URI.search(blob), blob)
        check(f"leak.no_gguf_mmproj[{label}]", not GGUFLIKE.search(blob), blob)
        check(f"leak.no_caption[{label}]", "patient" not in blob and "John Doe" not in blob and "MRN" not in blob, blob)
        check(f"leak.json_safe[{label}]", _is_json_safe(obj))
    # Hostile type/provider/action are coerced + warned, never echoed.
    check("leak.type_coerced", item["asset_type"] == "unknown")
    check("leak.provider_coerced", item["source_provider"] == "unknown")
    check("leak.action_coerced", item["candidate_action"] == "unknown")
    check("leak.type_warning", "asset_type_unrecognized" in item["warnings"])
    check("leak.provider_warning", "source_provider_unrecognized" in item["warnings"])
    check("leak.action_warning", "candidate_action_unrecognized" in item["warnings"])
    check("leak.vocab_only", _vocab_ok(item))
    # No raw fields survive onto the item.
    for forbidden in ("caption", "image_ref", "asset_ref", "include_score", "priority"):
        check(f"leak.no_field[{forbidden}]", forbidden not in item)


# --- 14. summary counts -------------------------------------------------------

def test_summary_counts() -> None:
    anchors = _anchors_list([1])
    plan = _plan([
        _item("candidate_convert_to_table", "table", asset_id="a1"),                 # table_reference, matched
        _item("candidate_include_as_figure", "diagram", asset_id="a2"),              # figure_reference, matched
        _item("candidate_summarize_as_text", "equation_block", asset_id="a3"),       # text_summary_reference, matched
        _item("review_only", "page_visual_signal", asset_id="a4", priority="low"),   # review_only, not_required
        _item("candidate_include_as_figure", "figure", asset_id="a5", source_page=9),  # figure_reference, missing
        _item("unknown", "unknown", asset_id="a6"),                                  # unknown
    ])
    report = build_visual_insertion_plan(plan, source_page_anchors=anchors)
    s = report["summary"]
    check("summary.count", s["insertion_count"] == 6, str(s))
    check("summary.fig", s["figure_reference_count"] == 2, str(s))
    check("summary.table", s["table_reference_count"] == 1, str(s))
    check("summary.text", s["text_summary_reference_count"] == 1, str(s))
    check("summary.review", s["review_only_count"] == 1, str(s))
    check("summary.unknown", s["unknown_count"] == 1, str(s))
    check("summary.anchor_matched", s["anchor_matched_count"] == 3, str(s))
    check("summary.anchor_missing", s["anchor_missing_count"] == 1, str(s))
    total = (s["figure_reference_count"] + s["table_reference_count"]
             + s["text_summary_reference_count"] + s["review_only_count"] + s["unknown_count"])
    check("summary.total_matches", total == 6)


# --- 15. determinism ----------------------------------------------------------

def test_determinism() -> None:
    plan = _plan([_item("candidate_include_as_figure", "diagram"),
                  _item("candidate_convert_to_table", "table", asset_id="t1")])
    anchors = _anchors_list([1])
    a = build_visual_insertion_plan(plan, source_page_anchors=anchors)
    b = build_visual_insertion_plan(plan, source_page_anchors=anchors)
    check("det.identical", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))


# --- 16. no forbidden imports -------------------------------------------------

def test_no_forbidden_imports() -> None:
    path = os.path.join(os.path.dirname(__file__), "..", "pipeline", "visual_insertion_planner.py")
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    import_lines = [
        ln.strip().lower()
        for ln in src.splitlines()
        if ln.strip().startswith(("import ", "from "))
    ]
    forbidden = ["fitz", "pymupdf", "pytesseract", "tesseract", "llama_cpp",
                 "llama-cpp", "mistral", "google.generativeai", "genai", "gemini",
                 "chandra", "local_model", "companion", "requests", "httpx",
                 "urllib", "socket", "subprocess", "json", "os", "pathlib",
                 "visual_assets_manifest", "visual_asset_scoring", "visual_replacement_planner",
                 "visual_asset_extractor", "extract", "run_llm_job", "job_manager",
                 "render", "server"]
    leaks = sorted({tok for ln in import_lines for tok in forbidden if tok in ln})
    check("imports.none_forbidden", not leaks, f"found in imports: {leaks}")
    allowed_prefixes = ("import re", "from __future__", "from typing import")
    unexpected = [ln for ln in import_lines if not ln.startswith(allowed_prefixes)]
    check("imports.only_expected_stdlib", not unexpected, f"unexpected: {unexpected}")


def main() -> int:
    test_include_as_figure_matched()
    test_convert_to_table_matched()
    test_summarize_as_text_matched()
    test_review_only_no_anchor_required()
    test_missing_anchor_degrades()
    test_malformed_plan()
    test_malformed_item()
    test_asset_id_fallback()
    test_source_page_invalid()
    test_invalid_anchor_not_emitted()
    test_chandra_blocked()
    test_no_mutation()
    test_smuggled_content_does_not_leak()
    test_summary_counts()
    test_determinism()
    test_no_forbidden_imports()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
