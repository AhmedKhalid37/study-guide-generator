#!/usr/bin/env python3
"""Focused tests for the missing diagram/table explainer core (Slice 94).

Run with:

    python test_scripts/test_missing_material_explainer.py

Synthetic dictionaries only. No PDFs, images, providers, renderers, OCR engines, or
model calls are required. The module turns the already-sanitized Slice 84 visual
inclusion plan + Slice 92 table candidate manifest + Slice 85/92 table
reconstruction policy into honest "what was missing" guidance whose ``prompt_block``
is safe to append to the existing generation prompt. It reconstructs no table,
inspects no PDF/image, and generates no image-derived diagram explanation.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
FORBIDDEN_KEY_NAMES = {
    "filename", "path", "title", "text", "ocr_text", "caption", "table_text",
    "image_ref", "asset_ref", "asset_id", "url", "argv", "socket", "bytes",
}
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\\\|\\\\\\\\|[A-Za-z]:\\\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z]|mmproj|\.gguf|llama-server)")
ITEM_ID_RE = re.compile(r"^missing_material_\d{4,}$")
CLOSED_MATERIAL_KINDS = {"diagram", "figure", "graph", "chart", "table", "table_like", "unknown"}
CLOSED_REASONS = {
    "visual_not_inserted", "table_deferred", "table_unreadable", "table_unsafe",
    "content_unavailable",
}
FORBIDDEN_CANARIES = [
    "private-source.pdf",
    "Quarterly Private Plan",
    "raw document paragraph",
    "raw OCR dump",
    "source caption text",
    "table cell text",
    "assets/secret.png",
    "sk_missingmaterialexplainer1234567890",
    "synthetic boom with private details",
]

from pipeline.missing_material_explainer import (  # noqa: E402
    CONTEXT_KIND,
    MAX_ITEMS_APPLIED,
    UNSAFE_SKIPPED,
    VISUAL_INSERTION_ENABLED_NO_FAILURE_SIGNAL,
    build_missing_material_explainer_context,
)
from pipeline.visual_inclusion_planner import build_visual_inclusion_plan  # noqa: E402
from pipeline.table_candidate_manifest import (  # noqa: E402
    build_table_candidates_manifest,
    table_policy_candidates,
)
from pipeline.table_reconstruction_policy import (  # noqa: E402
    build_table_reconstruction_policy,
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


# --- Synthetic input builders -------------------------------------------------


def _leaky_fields() -> dict[str, Any]:
    return {
        "filename": "private-source.pdf",
        "path": "/home/example/private-source.pdf",
        "title": "Quarterly Private Plan",
        "text": "raw document paragraph",
        "ocr_text": "raw OCR dump",
        "caption": "source caption text",
        "table_text": "table cell text",
        "image_ref": "assets/secret.png",
        "url": "https://example.invalid/private-source.pdf",
        "argv": "--model /home/example/model.gguf --mmproj /home/example/mmproj.gguf",
        "socket": "/tmp/private.sock",
        "bytes": "data:image/png;base64,AAAA",
    }


def _plan_item(source_page: Any, visual_kind: str = "figure", leaky: bool = False) -> dict[str, Any]:
    item = {
        "plan_index": 1,
        "candidate_id": "visual_candidate_0001",
        "source_index": 0,
        "source_page": source_page,
        "visual_kind": visual_kind,
        "inclusion_role": "primary_visual",
        "reason": "non_table_visual_from_included_page",
        "warnings": [],
    }
    if leaky:
        item.update(_leaky_fields())
    return item


def _plan(items: list[Any], status: str = "completed") -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "visual_inclusion_plan",
        "status": status,
        "summary": {"planned_count": len(items)},
        "items": items,
        "warnings": [],
    }


def _policy_item(action: str, source_page: Any, table_kind: str = "grid_table", leaky: bool = False) -> dict[str, Any]:
    item = {
        "source_index": 0,
        "source_page": source_page,
        "table_kind": table_kind,
        "action": action,
        "reason": "text_layer_missing",
        "preserve": ["headers"],
        "warnings": [],
        "policy_index": 1,
    }
    if leaky:
        item.update(_leaky_fields())
    return item


def _policy(items: list[Any], status: str = "completed") -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "table_reconstruction_policy",
        "status": status,
        "summary": {"policy_item_count": len(items)},
        "items": items,
        "warnings": [],
    }


def _manifest(count: int = 1) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "table_candidates_manifest",
        "status": "completed",
        "summary": {"table_like_candidate_count": count},
        "candidates": [
            {"candidate_id": f"table_candidate_{i + 1:04d}", "source_index": i,
             "source_page": i + 1, "table_kind": "grid_table", "signals": {}}
            for i in range(count)
        ],
        "warnings": [],
    }


def _scan_for_leak(node: Any, path: str = "") -> str | None:
    if isinstance(node, dict):
        for key, value in node.items():
            lower = str(key).lower()
            if lower in SECRET_KEY_NAMES:
                return f"{path}.{key} (secret-like field name)"
            if lower in FORBIDDEN_KEY_NAMES:
                return f"{path}.{key} (forbidden field)"
            found = _scan_for_leak(value, f"{path}.{key}")
            if found:
                return found
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found = _scan_for_leak(value, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(node, str):
        for canary in FORBIDDEN_CANARIES:
            if canary in node:
                return f"{path} (canary leaked: {canary})"
        if KEYLIKE.search(node):
            return f"{path} (credential-like value)"
        if PATHLIKE.search(node):
            return f"{path} (path-like value)"
        if URLLIKE.search(node):
            return f"{path} (URL-like value)"
        if DATA_OR_BASE64.search(node):
            return f"{path} (data/base64-like value)"
        if ARGV_OR_SOCKET.search(node):
            return f"{path} (argv/socket/model-like value)"
    return None


def _assert_shape(ctx: dict[str, Any], label: str) -> None:
    for item in ctx["items"]:
        check(f"{label}: item_id safe ({item['item_id']})", ITEM_ID_RE.match(item["item_id"]) is not None)
        check(f"{label}: material_kind closed ({item['material_kind']})", item["material_kind"] in CLOSED_MATERIAL_KINDS)
        check(f"{label}: reason closed ({item['reason']})", item["reason"] in CLOSED_REASONS)
        page = item["source_page"]
        check(f"{label}: page positive int ({page!r})", isinstance(page, int) and not isinstance(page, bool) and page > 0)


# --- Degenerate / missing / malformed inputs ---------------------------------


def test_all_missing_skipped() -> None:
    ctx = build_missing_material_explainer_context(None, None, None)
    check("all None → skipped", ctx["status"] == "skipped")
    check("all None empty block", ctx["prompt_block"] == "")
    check("all None no items", ctx["items"] == [])
    check("all None kind", ctx["kind"] == CONTEXT_KIND)


def test_malformed_inputs_degrade() -> None:
    for bad in (123, "x", 4.5):
        ctx = build_missing_material_explainer_context(bad, None, bad)
        check(f"malformed {type(bad).__name__} → skipped", ctx["status"] == "skipped")
        check(f"malformed {type(bad).__name__} empty block", ctx["prompt_block"] == "")
    bad_items = build_missing_material_explainer_context(
        {"status": "completed", "items": 5}, None, {"status": "completed", "items": 9}
    )
    check("non-list items → skipped", bad_items["status"] == "skipped")


def test_empty_plan_and_policy_skipped() -> None:
    ctx = build_missing_material_explainer_context(_plan([]), _manifest(0), _policy([]))
    check("empty inputs → skipped", ctx["status"] == "skipped")
    check("empty inputs empty block", ctx["prompt_block"] == "")
    skipped = build_missing_material_explainer_context(
        _plan([], status="skipped"), None, _policy([], status="skipped")
    )
    check("skipped inputs → skipped", skipped["status"] == "skipped")


# --- Table handling -----------------------------------------------------------


def test_table_defer_missing_item() -> None:
    ctx = build_missing_material_explainer_context(
        None, _manifest(1), _policy([_policy_item("defer", 4, "grid_table")])
    )
    check("defer → completed", ctx["status"] == "completed")
    item = ctx["items"][0]
    check("defer reason", item["reason"] == "table_deferred")
    check("defer material table", item["material_kind"] == "table")
    check("defer honest note", "not readable" in item["instruction"] or "not available" in item["instruction"])
    check("defer no-invent", "do not invent" in item["instruction"].lower())
    check("defer counted", ctx["summary"]["deferred_count"] == 1)
    check("defer missing_table_count", ctx["summary"]["missing_table_count"] == 1)
    _assert_shape(ctx, "defer")


def test_table_unreadable_missing_item() -> None:
    ctx = build_missing_material_explainer_context(
        None, _manifest(1), _policy([_policy_item("skip_unreadable", 9, "table_like")])
    )
    item = ctx["items"][0]
    check("unreadable reason", item["reason"] == "table_unreadable")
    check("unreadable material table_like", item["material_kind"] == "table_like")
    check("unreadable honest note", "not available" in item["instruction"] or "not readable" in item["instruction"])
    check("unreadable counted", ctx["summary"]["unreadable_count"] == 1)
    _assert_shape(ctx, "unreadable")


def test_table_unsafe_not_explained() -> None:
    ctx = build_missing_material_explainer_context(
        None, _manifest(1), _policy([_policy_item("skip_unsafe", 5, "grid_table")])
    )
    reasons = [item["reason"] for item in ctx["items"]]
    check("unsafe not an item", "table_unsafe" not in reasons)
    check("unsafe no items at all", ctx["items"] == [])
    check("unsafe skipped → skipped status", ctx["status"] == "skipped")
    check("unsafe counted", ctx["summary"]["unsafe_skipped_count"] == 1)
    check("unsafe warning", UNSAFE_SKIPPED in ctx["warnings"])


def test_table_reconstruct_not_missing() -> None:
    # reconstruct/simplify are handled by Slice 93, never "missing" here.
    ctx = build_missing_material_explainer_context(
        None,
        _manifest(2),
        _policy([
            _policy_item("reconstruct_with_original", 4, "grid_table"),
            _policy_item("simplify_only", 5, "grid_table"),
        ]),
    )
    check("reconstruct/simplify → no missing items", ctx["items"] == [])
    check("reconstruct/simplify → skipped", ctx["status"] == "skipped")


# --- Visual handling ----------------------------------------------------------


def test_visual_missing_when_insertion_disabled() -> None:
    ctx = build_missing_material_explainer_context(
        _plan([_plan_item(4, "diagram"), _plan_item(7, "graph")]),
        None,
        None,
        full_visual_insertion_enabled=False,
    )
    check("disabled → completed", ctx["status"] == "completed")
    check("disabled → two items", len(ctx["items"]) == 2)
    for item in ctx["items"]:
        check("visual reason", item["reason"] == "visual_not_inserted")
        check("visual no-invent", "do not invent" in item["instruction"].lower())
        check("visual points to source page", "source page" in item["instruction"].lower())
    check("missing_visual_count", ctx["summary"]["missing_visual_count"] == 2)
    check("visual block guidance", "Missing visual/table guidance:" in ctx["prompt_block"])
    _assert_shape(ctx, "visual-disabled")


def test_visual_not_invented_when_insertion_enabled() -> None:
    ctx = build_missing_material_explainer_context(
        _plan([_plan_item(4, "diagram"), _plan_item(7, "graph")]),
        None,
        None,
        full_visual_insertion_enabled=True,
    )
    check("enabled → no invented visual items", ctx["items"] == [])
    check("enabled → skipped", ctx["status"] == "skipped")
    check("enabled → no-failure-signal warning", VISUAL_INSERTION_ENABLED_NO_FAILURE_SIGNAL in ctx["warnings"])
    check("enabled → empty block", ctx["prompt_block"] == "")


def test_visual_kind_mapping_closed() -> None:
    ctx = build_missing_material_explainer_context(
        _plan([
            _plan_item(1, "image"),       # → figure
            _plan_item(2, "chart"),
            _plan_item(3, "totally_bogus_kind"),  # → unknown
        ]),
        None,
        None,
    )
    kinds = {item["source_page"]: item["material_kind"] for item in ctx["items"]}
    check("image → figure", kinds.get(1) == "figure")
    check("chart preserved", kinds.get(2) == "chart")
    check("bogus → unknown", kinds.get(3) == "unknown")


# --- Sanitization / determinism guarantees -----------------------------------


def test_invalid_pages_skipped() -> None:
    ctx = build_missing_material_explainer_context(
        _plan([_plan_item(0, "figure"), _plan_item(-2, "figure"), _plan_item("4", "figure"), _plan_item(2.0, "figure")]),
        None,
        _policy([_policy_item("defer", 0), _policy_item("skip_unreadable", None)]),
    )
    check("all invalid pages dropped", ctx["items"] == [])
    check("invalid pages → skipped", ctx["status"] == "skipped")


def test_item_ids_deterministic_and_ordered() -> None:
    ctx = build_missing_material_explainer_context(
        _plan([_plan_item(7, "figure"), _plan_item(2, "diagram")]),
        _manifest(1),
        _policy([_policy_item("defer", 2, "grid_table")]),
    )
    ids = [item["item_id"] for item in ctx["items"]]
    check("ids sequential", ids == ["missing_material_0001", "missing_material_0002", "missing_material_0003"])
    pages = [item["source_page"] for item in ctx["items"]]
    check("ordered by page", pages == sorted(pages))
    # On page 2 the table bullet must precede the figure bullet.
    page2 = [item for item in ctx["items"] if item["source_page"] == 2]
    check("table before visual on same page", page2[0]["reason"] == "table_deferred")


def test_max_items_defensive_cap() -> None:
    items = [_plan_item(i + 1, "figure") for i in range(5)]
    ctx = build_missing_material_explainer_context(_plan(items), None, None, max_items=2)
    check("max_items truncates", len(ctx["items"]) == 2)
    check("max_items partial", ctx["status"] == "partial")
    check("max_items warning", MAX_ITEMS_APPLIED in ctx["warnings"])
    zero = build_missing_material_explainer_context(_plan(items), None, None, max_items=0)
    check("max_items 0 → skipped", zero["status"] == "skipped")


def test_hostile_canaries_stripped() -> None:
    ctx = build_missing_material_explainer_context(
        _plan([_plan_item(4, "diagram", leaky=True)]),
        _manifest(1),
        _policy([_policy_item("defer", 8, "grid_table", leaky=True),
                 _policy_item("skip_unsafe", 9, "grid_table", leaky=True)]),
    )
    leak = _scan_for_leak(ctx)
    check("no leak in full context", leak is None, leak or "")
    for canary in FORBIDDEN_CANARIES:
        check(f"prompt_block free of canary: {canary[:24]}", canary not in ctx["prompt_block"])


def test_deterministic_repeated_calls() -> None:
    plan = _plan([_plan_item(4, "figure"), _plan_item(9, "chart")])
    policy = _policy([_policy_item("defer", 4, "grid_table"), _policy_item("skip_unreadable", 6, "table_like")])
    first = build_missing_material_explainer_context(plan, _manifest(2), policy)
    second = build_missing_material_explainer_context(plan, _manifest(2), policy)
    check("deterministic dict", first == second)
    check("deterministic block", first["prompt_block"] == second["prompt_block"])


# --- Real end-to-end chain (real planner + policy cores) ---------------------


def test_real_chain_from_visual_manifest() -> None:
    visual_manifest = {
        "status": "completed",
        "assets": [
            # a non-table figure → planned visual
            {"source_index": 0, "source_page": 3, "asset_type": "extracted_figure",
             "visual_kind": "diagram", "crop_width_px": 200, "crop_height_px": 200,
             **_leaky_fields()},
            # an image-only table with no text layer / no structure → unreadable
            {"source_index": 1, "source_page": 5, "asset_type": "grid_table",
             "confidence": "high", "signals": {"has_text_layer": False, "rows": 1, "columns": 1},
             **_leaky_fields()},
        ],
    }
    plan = build_visual_inclusion_plan(visual_manifest)
    candidate_manifest = build_table_candidates_manifest(visual_manifest)
    policy = build_table_reconstruction_policy(table_policy_candidates(candidate_manifest))
    ctx = build_missing_material_explainer_context(
        plan, candidate_manifest, policy, full_visual_insertion_enabled=False
    )
    check("real chain completed", ctx["status"] == "completed")
    check("real chain has visual + table", ctx["summary"]["missing_visual_count"] >= 1)
    check("real chain no leak", _scan_for_leak(ctx) is None)
    _assert_shape(ctx, "real-chain")


# --- Integration: run_llm_job prompt wiring (cheap helper only) ---------------


def test_run_llm_job_prompt_helper() -> None:
    try:
        from pipeline.run_llm_job import _build_missing_material_prompt_block_safely
    except Exception as exc:  # pragma: no cover - host import guard
        print(f"[SKIP] run_llm_job helper import ({type(exc).__name__})")
        return
    check("helper none → empty", _build_missing_material_prompt_block_safely(None, None, None) == "")
    check(
        "helper skipped → empty",
        _build_missing_material_prompt_block_safely(_plan([], status="skipped"), None, _policy([], status="skipped")) == "",
    )
    block = _build_missing_material_prompt_block_safely(
        _plan([_plan_item(4, "diagram")]), None, _policy([_policy_item("defer", 7, "grid_table")])
    )
    check("helper actionable → guidance", "Missing visual/table guidance:" in block)
    check("helper actionable no-invent", "do not invent" in block.lower())
    check("helper block no leak", _scan_for_leak(block) is None)


# --- Import hygiene (no provider/model/cloud/render/OCR/FastAPI/frontend) -----


def test_no_forbidden_imports() -> None:
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "pipeline" / "missing_material_explainer.py"
    text = src.read_text(encoding="utf-8")
    for forbidden in (
        "mistralai", "google.generativeai", "openai", "requests", "urllib.request",
        "httpx", "socket", "chandra", "fastapi", "PIL", "fitz", "playwright",
        "pipeline.run_llm_job", "pipeline.visual_inclusion_planner",
    ):
        check(f"no import of {forbidden}", f"import {forbidden}" not in text and f"from {forbidden}" not in text)


def test_module_not_loaded_heavy_deps() -> None:
    for forbidden in ("fastapi", "PIL", "fitz", "openai", "playwright"):
        check(f"not loaded after import: {forbidden}", forbidden not in sys.modules)


def main() -> int:
    test_all_missing_skipped()
    test_malformed_inputs_degrade()
    test_empty_plan_and_policy_skipped()
    test_table_defer_missing_item()
    test_table_unreadable_missing_item()
    test_table_unsafe_not_explained()
    test_table_reconstruct_not_missing()
    test_visual_missing_when_insertion_disabled()
    test_visual_not_invented_when_insertion_enabled()
    test_visual_kind_mapping_closed()
    test_invalid_pages_skipped()
    test_item_ids_deterministic_and_ordered()
    test_max_items_defensive_cap()
    test_hostile_canaries_stripped()
    test_deterministic_repeated_calls()
    test_real_chain_from_visual_manifest()
    # Import-hygiene checks run BEFORE the run_llm_job integration test, which may
    # itself import heavy extraction deps and pollute sys.modules.
    test_no_forbidden_imports()
    test_module_not_loaded_heavy_deps()
    test_run_llm_job_prompt_helper()
    print(f"\nMissing material explainer tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
