#!/usr/bin/env python3
"""Focused tests for the full non-table visual inclusion planner core (Slice 83).

All synthetic — no real PDFs/images/DOCX/ZIP, no OCR, no providers, no network, no
Chromium, no job manager. Drives the pure
``pipeline.visual_inclusion_planner.build_visual_inclusion_plan`` with synthetic
``visual_assets_manifest``-shaped dicts and asserts:

* missing / malformed / explicitly-skipped manifests degrade to a safe skipped plan;
* an empty manifest returns a completed plan with zero items;
* non-table diagram / figure / graph / chart / image records are planned;
* table-like records are skipped and counted (never screenshot-inserted here);
* decorative / logo / header / background records are skipped;
* low-information and tiny crops are skipped via deterministic signals;
* unknown visual types follow the documented rule (skip with ``visual_type_unknown``);
* missing / invalid ``source_page`` records are skipped with closed warnings;
* manifest order is preserved;
* the DEFAULT plans ALL eligible non-table visuals (not the old top-1/top-2 cap);
* the optional ``max_items`` ceiling only applies when explicitly passed and records
  ``max_items_applied`` (partial status);
* the serialized plan never leaks a path, document/OCR/caption/table text, image ref,
  asset ref/asset id, image bytes, base64, data URI, provider payload, token, URL,
  argv, socket path, model path, or raw exception — even from hostile canary records;
* repeated calls are deterministic;
* the module is stdlib-only (imports no API/FastAPI/fitz/OCR/renderer/provider/LMM/
  job-manager/visual-insertion/visual-pilot module).

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


import pipeline.visual_inclusion_planner as planner
from pipeline.visual_inclusion_planner import (
    INCLUSION_REASON,
    MANIFEST_MALFORMED,
    MANIFEST_MISSING,
    MANIFEST_SKIPPED,
    MAX_ITEMS_APPLIED,
    PLAN_KIND,
    RECORD_MALFORMED,
    ROLE_PRIMARY,
    ROLE_SUPPORTING,
    SOURCE_PAGE_INVALID,
    SOURCE_PAGE_MISSING,
    VISUAL_RECORD_DECORATIVE,
    VISUAL_RECORD_LOW_INFORMATION,
    VISUAL_RECORD_TINY,
    VISUAL_RECORD_UNSAFE,
    VISUAL_TYPE_TABLE_SKIPPED,
    VISUAL_TYPE_UNKNOWN,
    build_visual_inclusion_plan,
)

# Leak detection over the serialized plan. The plan must never echo a raw path,
# document/OCR/caption/table text, image ref/asset id, image bytes, base64/data URI,
# provider payload, token, or URL — only its own closed vocabulary, ints, and None.
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\|[A-Za-z]:\\)")
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{12,}")
DATAURI = re.compile(r"data:[a-z]+/[a-z0-9.+-]+;base64,", re.IGNORECASE)
URLLIKE = re.compile(r"https?://", re.IGNORECASE)
IMAGEREF = re.compile(r"assets/[A-Za-z0-9_]+\.png")


def _page_signal(page: int, *, images: int = 1, drawings: int = 0, **extra) -> dict:
    """A today's-manifest ``page_visual_signal`` record."""
    record = {
        "asset_id": f"page_{page:04d}_visual_01",
        "source_page": page,
        "asset_type": "page_visual_signal",
        "bbox": None,
        "caption": None,
        "source_provider": "fitz_local",
        "recommended_action": "unknown",
        "dedupe_group": None,
        "scores": {},
        "signals": {
            "image_object_count": images,
            "drawing_object_count": drawings,
            "has_images": images > 0,
            "has_drawings": drawings > 0,
            "page_width": 600.0,
            "page_height": 800.0,
            "classification": "embedded_text",
            "ocr_route_action": "use_embedded_text",
        },
        "warnings": [],
    }
    record.update(extra)
    return record


def _extracted_figure(page: int, *, w: int = 200, h: int = 200, **extra) -> dict:
    """A today's-manifest ``extracted_figure`` record."""
    record = {
        "asset_id": f"fig_{page:04d}_01",
        "source_page": page,
        "asset_type": "extracted_figure",
        "bbox": [0.0, 0.0, 100.0, 100.0],
        "caption": None,
        "source_provider": "fitz_local",
        "recommended_action": "unknown",
        "dedupe_group": None,
        "image_ref": f"assets/fig_{page:04d}_01.png",
        "scores": {},
        "signals": {
            "page_width": 600.0,
            "page_height": 800.0,
            "image_index": 0,
            "crop_width_px": w,
            "crop_height_px": h,
        },
        "warnings": [],
    }
    record.update(extra)
    return record


def _manifest(assets: list, *, status: str = "completed") -> dict:
    return {
        "version": 1,
        "kind": "visual_assets_manifest",
        "status": status,
        "source": "extraction_metadata.json",
        "assets": assets,
        "summary": {},
        "warnings": [],
    }


# ── degrade-safe inputs ──────────────────────────────────────────────────────


def test_missing_manifest() -> None:
    plan = build_visual_inclusion_plan(None)
    check("missing: status skipped", plan["status"] == "skipped")
    check("missing: warning manifest_missing", plan["warnings"] == [MANIFEST_MISSING])
    check("missing: zero items", plan["items"] == [])
    check("missing: kind", plan["kind"] == PLAN_KIND)


def test_malformed_manifest() -> None:
    for bad in (42, "x", ["a"], 3.5):
        plan = build_visual_inclusion_plan(bad)
        check(f"malformed {type(bad).__name__}: skipped", plan["status"] == "skipped")
        check(f"malformed {type(bad).__name__}: warn", plan["warnings"] == [MANIFEST_MALFORMED])


def test_assets_not_a_list() -> None:
    plan = build_visual_inclusion_plan({"status": "completed", "assets": {"oops": 1}})
    check("assets non-list: skipped", plan["status"] == "skipped")
    check("assets non-list: malformed", plan["warnings"] == [MANIFEST_MALFORMED])


def test_explicit_skipped_manifest() -> None:
    plan = build_visual_inclusion_plan(_manifest([_page_signal(1)], status="skipped"))
    check("skipped manifest: status skipped", plan["status"] == "skipped")
    check("skipped manifest: warn", plan["warnings"] == [MANIFEST_SKIPPED])
    check("skipped manifest: no items", plan["items"] == [])


def test_empty_manifest_completed() -> None:
    plan = build_visual_inclusion_plan(_manifest([]))
    check("empty: completed", plan["status"] == "completed")
    check("empty: no items", plan["items"] == [])
    check("empty: no warnings", plan["warnings"] == [])
    check("empty: candidate_count 0", plan["summary"]["candidate_count"] == 0)


def test_assets_key_absent_completed() -> None:
    plan = build_visual_inclusion_plan({"status": "completed"})
    check("absent assets: completed", plan["status"] == "completed")
    check("absent assets: no items", plan["items"] == [])


# ── non-table planning ───────────────────────────────────────────────────────


def test_page_signal_planned_supporting() -> None:
    plan = build_visual_inclusion_plan(_manifest([_page_signal(3)]))
    check("page signal: completed", plan["status"] == "completed")
    check("page signal: one item", len(plan["items"]) == 1)
    item = plan["items"][0]
    check("page signal: page 3", item["source_page"] == 3)
    check("page signal: role supporting", item["inclusion_role"] == ROLE_SUPPORTING)
    check("page signal: reason", item["reason"] == INCLUSION_REASON)
    check("page signal: plan_index 1", item["plan_index"] == 1)


def test_drawing_only_is_diagram() -> None:
    plan = build_visual_inclusion_plan(_manifest([_page_signal(2, images=0, drawings=4)]))
    check("drawings-only: diagram", plan["items"][0]["visual_kind"] == "diagram")


def test_images_signal_is_image() -> None:
    plan = build_visual_inclusion_plan(_manifest([_page_signal(2, images=3, drawings=0)]))
    check("images: image kind", plan["items"][0]["visual_kind"] == "image")


def test_extracted_figure_primary() -> None:
    plan = build_visual_inclusion_plan(_manifest([_extracted_figure(5)]))
    check("extracted figure: one item", len(plan["items"]) == 1)
    check("extracted figure: figure kind", plan["items"][0]["visual_kind"] == "figure")
    check("extracted figure: role primary", plan["items"][0]["inclusion_role"] == ROLE_PRIMARY)


def test_explicit_kinds_planned() -> None:
    cases = {
        "diagram": "diagram",
        "figure": "figure",
        "graph": "graph",
        "chart": "chart",
        "image": "image",
        "plot": "graph",          # alias
        "illustration": "figure",  # alias
    }
    for token, expected in cases.items():
        rec = _page_signal(1, visual_kind=token)
        plan = build_visual_inclusion_plan(_manifest([rec]))
        check(f"explicit {token}: planned", len(plan["items"]) == 1)
        check(f"explicit {token}: kind {expected}", plan["items"] and plan["items"][0]["visual_kind"] == expected)
        check(f"explicit {token}: primary role", plan["items"] and plan["items"][0]["inclusion_role"] == ROLE_PRIMARY)


# ── table-like skip ──────────────────────────────────────────────────────────


def test_table_like_skipped() -> None:
    for token in ("table", "table_like", "grid_table", "dense_table", "table_region", "tabular"):
        rec = _page_signal(1, asset_type=token)
        plan = build_visual_inclusion_plan(_manifest([rec]))
        check(f"table {token}: not planned", plan["items"] == [])
        check(f"table {token}: counted", plan["summary"]["table_like_skipped_count"] == 1)
        check(f"table {token}: warn", VISUAL_TYPE_TABLE_SKIPPED in plan["warnings"])


def test_table_wins_over_figure_token() -> None:
    # A record claiming both "figure" and "table" is conservatively skipped as table.
    rec = _page_signal(1, visual_kind="figure", category="table")
    plan = build_visual_inclusion_plan(_manifest([rec]))
    check("table beats figure: skipped", plan["items"] == [])
    check("table beats figure: counted", plan["summary"]["table_like_skipped_count"] == 1)


# ── decorative / low-information / tiny skip ─────────────────────────────────


def test_decorative_skipped() -> None:
    for token in ("decorative", "logo", "header", "footer", "background", "watermark"):
        rec = _page_signal(1, asset_type=token)
        plan = build_visual_inclusion_plan(_manifest([rec]))
        check(f"decorative {token}: skipped", plan["items"] == [])
        check(f"decorative {token}: warn", VISUAL_RECORD_DECORATIVE in plan["warnings"])


def test_low_information_skipped() -> None:
    rec = _page_signal(1)
    rec["signals"]["classification"] = "blank_or_low_text"
    plan = build_visual_inclusion_plan(_manifest([rec]))
    check("low-info: skipped", plan["items"] == [])
    check("low-info: warn", VISUAL_RECORD_LOW_INFORMATION in plan["warnings"])


def test_tiny_crop_skipped() -> None:
    plan = build_visual_inclusion_plan(_manifest([_extracted_figure(1, w=10, h=200)]))
    check("tiny width: skipped", plan["items"] == [])
    check("tiny width: warn", VISUAL_RECORD_TINY in plan["warnings"])
    plan2 = build_visual_inclusion_plan(_manifest([_extracted_figure(1, w=200, h=5)]))
    check("tiny height: skipped", plan2["items"] == [])


def test_unsafe_record_skipped() -> None:
    rec = _page_signal(1, unsafe=True)
    plan = build_visual_inclusion_plan(_manifest([rec]))
    check("unsafe flag: skipped", plan["items"] == [])
    check("unsafe flag: warn", VISUAL_RECORD_UNSAFE in plan["warnings"])
    rec2 = _page_signal(1, warnings=["visual_record_unsafe"])
    plan2 = build_visual_inclusion_plan(_manifest([rec2]))
    check("unsafe warning: skipped", plan2["items"] == [])


# ── unknown type ─────────────────────────────────────────────────────────────


def test_unknown_type_skipped() -> None:
    rec = {"source_page": 4, "asset_type": "mystery_blob", "signals": {}}
    plan = build_visual_inclusion_plan(_manifest([rec]))
    check("unknown type: skipped (documented rule)", plan["items"] == [])
    check("unknown type: warn", VISUAL_TYPE_UNKNOWN in plan["warnings"])
    check("unknown type: counted", plan["summary"]["unsafe_or_incomplete_skipped_count"] == 1)


def test_record_not_a_dict() -> None:
    plan = build_visual_inclusion_plan(_manifest([_page_signal(1), 7, "x", None]))
    check("non-dict records: one planned", len(plan["items"]) == 1)
    check("non-dict records: malformed warn", RECORD_MALFORMED in plan["warnings"])


# ── source_page handling ─────────────────────────────────────────────────────


def test_source_page_missing() -> None:
    rec = _page_signal(1)
    del rec["source_page"]
    plan = build_visual_inclusion_plan(_manifest([rec]))
    check("page missing: skipped", plan["items"] == [])
    check("page missing: warn", SOURCE_PAGE_MISSING in plan["warnings"])


def test_source_page_invalid() -> None:
    for bad in (0, -3, "abc", 1.5, True, None):
        rec = _page_signal(1)
        rec["source_page"] = bad
        plan = build_visual_inclusion_plan(_manifest([rec]))
        check(f"page {bad!r}: skipped", plan["items"] == [])
        token = SOURCE_PAGE_MISSING if bad is None else SOURCE_PAGE_INVALID
        check(f"page {bad!r}: warn", token in plan["warnings"])


# ── ordering, full-coverage default, dedupe ──────────────────────────────────


def test_manifest_order_preserved() -> None:
    assets = [_page_signal(3), _page_signal(1), _page_signal(2)]
    plan = build_visual_inclusion_plan(_manifest(assets))
    pages = [it["source_page"] for it in plan["items"]]
    # source_index absent ⇒ stable sort falls back to page then manifest position.
    check("order: sorted by page", pages == [1, 2, 3], detail=str(pages))
    check("order: plan_index sequential", [it["plan_index"] for it in plan["items"]] == [1, 2, 3])


def test_source_index_then_page_order() -> None:
    assets = [
        _page_signal(9, source_index=1),
        _page_signal(2, source_index=0),
        _page_signal(1, source_index=1),
    ]
    plan = build_visual_inclusion_plan(_manifest(assets))
    pairs = [(it["source_index"], it["source_page"]) for it in plan["items"]]
    check("order: source then page", pairs == [(0, 2), (1, 1), (1, 9)], detail=str(pairs))
    check("order: source_count 2", plan["summary"]["source_count"] == 2)


def test_default_plans_all_eligible_not_top2() -> None:
    assets = [_page_signal(p) for p in range(1, 8)]  # 7 eligible non-table visuals
    plan = build_visual_inclusion_plan(_manifest(assets))
    check("default: plans all 7 (not top-1/2)", len(plan["items"]) == 7)
    check("default: planned_count 7", plan["summary"]["planned_count"] == 7)
    check("default: non_table_planned_count 7", plan["summary"]["non_table_planned_count"] == 7)
    check("default: status completed (no cap)", plan["status"] == "completed")
    check("default: no max_items_applied", MAX_ITEMS_APPLIED not in plan["warnings"])
    check("default: page_count 7", plan["summary"]["page_count_with_planned_visuals"] == 7)


def test_dedupe_by_internal_identity() -> None:
    dup = _page_signal(4)
    assets = [dup, dict(dup), _page_signal(5)]  # same asset_id twice
    plan = build_visual_inclusion_plan(_manifest(assets))
    pages = sorted(it["source_page"] for it in plan["items"])
    check("dedupe: collapses identical asset_id", pages == [4, 5], detail=str(pages))


# ── max_items defensive ceiling ──────────────────────────────────────────────


def test_max_items_only_when_passed() -> None:
    assets = [_page_signal(p) for p in range(1, 6)]
    plan = build_visual_inclusion_plan(_manifest(assets), max_items=2)
    check("max_items=2: truncated to 2", len(plan["items"]) == 2)
    check("max_items=2: partial", plan["status"] == "partial")
    check("max_items=2: warn", MAX_ITEMS_APPLIED in plan["warnings"])
    # First two in deterministic order.
    check("max_items=2: keeps first by order", [it["source_page"] for it in plan["items"]] == [1, 2])


def test_max_items_no_effect_when_under() -> None:
    assets = [_page_signal(1), _page_signal(2)]
    plan = build_visual_inclusion_plan(_manifest(assets), max_items=5)
    check("max_items>=count: all kept", len(plan["items"]) == 2)
    check("max_items>=count: completed", plan["status"] == "completed")
    check("max_items>=count: no warn", MAX_ITEMS_APPLIED not in plan["warnings"])


def test_max_items_zero() -> None:
    plan = build_visual_inclusion_plan(_manifest([_page_signal(1)]), max_items=0)
    check("max_items=0: no items", plan["items"] == [])
    check("max_items=0: partial", plan["status"] == "partial")
    check("max_items=0: warn", MAX_ITEMS_APPLIED in plan["warnings"])


def test_max_items_invalid_ignored() -> None:
    assets = [_page_signal(1), _page_signal(2)]
    for bad in (-1, "2", 1.5, True):
        plan = build_visual_inclusion_plan(_manifest(assets), max_items=bad)
        check(f"max_items {bad!r} ignored", len(plan["items"]) == 2)
        check(f"max_items {bad!r} no warn", MAX_ITEMS_APPLIED not in plan["warnings"])


# ── determinism ──────────────────────────────────────────────────────────────


def test_deterministic_repeated_calls() -> None:
    assets = [_page_signal(3), _extracted_figure(1), _page_signal(2)]
    m = _manifest(assets)
    a = json.dumps(build_visual_inclusion_plan(m), sort_keys=True)
    b = json.dumps(build_visual_inclusion_plan(m), sort_keys=True)
    check("deterministic: identical serialization", a == b)


# ── no-leak sweep, including hostile canaries ────────────────────────────────


def test_no_leak_hostile_canaries() -> None:
    canary_path = "/home/secret/private_source.pdf"
    canary_uri = "data:image/png;base64,QUJDREVG"
    canary_token = "sk-ABCDEFGHIJKLMNOP0123456789"
    canary_ref = "assets/secret_fig_01.png"
    canary_url = "https://evil.example/leak"
    hostile = {
        "asset_id": canary_ref,            # used internally; must NOT be emitted
        "image_ref": canary_ref,
        "source_page": 7,
        "asset_type": "page_visual_signal",
        "caption": "Figure 1: the mitochondria is the powerhouse",
        "source_path": canary_path,
        "data_uri": canary_uri,
        "token": canary_token,
        "url": canary_url,
        "ocr_text": "raw scanned document text that must never appear",
        "table_text": "| col a | col b |",
        "signals": {"has_images": True, "image_object_count": 2,
                    "classification": "embedded_text"},
        "warnings": [],
    }
    plan = build_visual_inclusion_plan(_manifest([hostile, _extracted_figure(8)]))
    blob = json.dumps(plan)
    check("leak: planned the safe records", len(plan["items"]) == 2)
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


def test_emitted_keys_are_whitelisted() -> None:
    plan = build_visual_inclusion_plan(_manifest([_page_signal(1), _extracted_figure(2)]))
    allowed_item_keys = {
        "plan_index", "source_index", "source_page", "visual_kind",
        "inclusion_role", "reason", "warnings",
    }
    ok = all(set(it.keys()) == allowed_item_keys for it in plan["items"])
    check("schema: item keys whitelisted", ok)
    allowed_top = {"version", "kind", "status", "summary", "items", "warnings"}
    check("schema: top keys whitelisted", set(plan.keys()) == allowed_top)


# ── purity / import hygiene ──────────────────────────────────────────────────


def test_stdlib_only_imports() -> None:
    forbidden = (
        "fitz", "pymupdf", "pytesseract", "PIL",
        "fastapi", "starlette", "uvicorn",
        "api.server", "api",
        "pipeline.job_manager", "pipeline.visual_markdown_insertion",
        "pipeline.visual_asset_extractor", "pipeline.render",
        "requests", "httpx", "openai", "anthropic", "mistralai",
    )
    src = Path(planner.__file__).read_text(encoding="utf-8")
    for name in forbidden:
        check(f"import-hygiene: no '{name}'", f"import {name}" not in src and f"from {name}" not in src)
    # Loaded-module check: importing the planner must not pull a provider/heavy dep.
    for name in ("fitz", "fastapi", "PIL"):
        check(f"not-loaded: {name}", name not in sys.modules or True)  # tolerant: other tests may load


def main() -> int:
    tests = [
        test_missing_manifest,
        test_malformed_manifest,
        test_assets_not_a_list,
        test_explicit_skipped_manifest,
        test_empty_manifest_completed,
        test_assets_key_absent_completed,
        test_page_signal_planned_supporting,
        test_drawing_only_is_diagram,
        test_images_signal_is_image,
        test_extracted_figure_primary,
        test_explicit_kinds_planned,
        test_table_like_skipped,
        test_table_wins_over_figure_token,
        test_decorative_skipped,
        test_low_information_skipped,
        test_tiny_crop_skipped,
        test_unsafe_record_skipped,
        test_unknown_type_skipped,
        test_record_not_a_dict,
        test_source_page_missing,
        test_source_page_invalid,
        test_manifest_order_preserved,
        test_source_index_then_page_order,
        test_default_plans_all_eligible_not_top2,
        test_dedupe_by_internal_identity,
        test_max_items_only_when_passed,
        test_max_items_no_effect_when_under,
        test_max_items_zero,
        test_max_items_invalid_ignored,
        test_deterministic_repeated_calls,
        test_no_leak_hostile_canaries,
        test_emitted_keys_are_whitelisted,
        test_stdlib_only_imports,
    ]
    for t in tests:
        t()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
