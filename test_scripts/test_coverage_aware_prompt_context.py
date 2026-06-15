#!/usr/bin/env python3
"""Focused tests for the coverage-aware generation prompt context (Slice 95).

Run with:

    python test_scripts/test_coverage_aware_prompt_context.py

Synthetic dictionaries only. No PDFs, images, providers, renderers, OCR engines, or
model calls are required. The module summarises the already-sanitized coverage
signals (page selections, Slice 84 source coverage + visual inclusion plan, Slice
92 table candidate/policy artifacts, Slice 93 table prompt context, Slice 94
missing-material context) into one short, leak-free guidance block whose
``prompt_block`` is safe to append to the existing generation prompt. It inspects no
PDF/image, OCRs nothing, reconstructs no table, and calls no provider.
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
ITEM_ID_RE = re.compile(r"^coverage_context_\d{4,}$")
CLOSED_KINDS = {
    "included_page", "source_gap", "visual_plan", "table_policy", "missing_material",
}
FORBIDDEN_CANARIES = [
    "private-source.pdf",
    "Quarterly Private Plan",
    "raw document paragraph",
    "raw OCR dump",
    "source caption text",
    "table cell text",
    "assets/secret.png",
    "sk_coverageawarecontext1234567890",
    "synthetic boom with private details",
]

from pipeline.coverage_aware_prompt_context import (  # noqa: E402
    CONTEXT_KIND,
    MAX_ITEMS_APPLIED,
    JOB_REQUEST_MALFORMED,
    SOURCE_COVERAGE_MALFORMED,
    build_coverage_aware_prompt_context,
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


def _selection(mode: str = "exclude", include=None, exclude=None) -> dict[str, Any]:
    return {
        "version": 1,
        "mode": mode,
        "include_pages": include or [],
        "exclude_pages": exclude or [],
        "warnings": [],
    }


def _job_request(global_sel=None, per=None, leaky: bool = False) -> dict[str, Any]:
    req: dict[str, Any] = {}
    if global_sel is not None:
        req["material_page_selection"] = global_sel
    if per is not None:
        req["material_page_selections"] = per
    if leaky:
        req.update(_leaky_fields())
    return req


def _coverage(source_count=1, covered=8, unreadable=0, status="complete", leaky=False) -> dict[str, Any]:
    summary = {
        "source_count": source_count,
        "total_pages": covered + unreadable,
        "covered_pages": covered,
        "empty_or_unreadable_pages": unreadable,
    }
    if leaky:
        summary.update(_leaky_fields())
    return {
        "version": 1,
        "kind": "source_coverage_report",
        "status": status,
        "summary": summary,
        "sources": [],
        "warnings": [],
    }


def _plan(count=1, status="completed") -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "visual_inclusion_plan",
        "status": status,
        "summary": {"planned_count": count},
        "items": [{"plan_index": i + 1, **_leaky_fields()} for i in range(count)],
        "warnings": [],
    }


def _manifest(count=1, status="completed") -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "table_candidates_manifest",
        "status": status,
        "summary": {"table_like_candidate_count": count},
        "candidates": [{"candidate_id": f"table_candidate_{i + 1:04d}", **_leaky_fields()} for i in range(count)],
        "warnings": [],
    }


def _policy(count=1, status="completed") -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "table_reconstruction_policy",
        "status": status,
        "summary": {"policy_item_count": count},
        "items": [{"action": "defer", **_leaky_fields()} for _ in range(count)],
        "warnings": [],
    }


def _table_prompt_context(count=1, status="completed") -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "table_reconstruction_prompt_context",
        "status": status,
        "summary": {"prompt_item_count": count},
        "prompt_block": "table block",
        "items": [{"action": "defer"} for _ in range(count)],
        "warnings": [],
    }


def _missing(count=1, status="completed") -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "missing_material_explainer_context",
        "status": status,
        "summary": {"prompt_item_count": count, "missing_visual_count": count, "missing_table_count": 0},
        "items": [{"item_id": f"missing_material_{i + 1:04d}", **_leaky_fields()} for i in range(count)],
        "prompt_block": "missing block",
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
        check(f"{label}: kind closed ({item['kind']})", item["kind"] in CLOSED_KINDS)
        page = item["source_page"]
        check(
            f"{label}: page None or positive int ({page!r})",
            page is None or (isinstance(page, int) and not isinstance(page, bool) and page > 0),
        )


# --- Degenerate / missing / malformed inputs ---------------------------------


def test_all_missing_skipped() -> None:
    ctx = build_coverage_aware_prompt_context()
    check("all None → skipped", ctx["status"] == "skipped")
    check("all None empty block", ctx["prompt_block"] == "")
    check("all None no items", ctx["items"] == [])
    check("all None kind", ctx["kind"] == CONTEXT_KIND)
    check("all None prompt_item_count 0", ctx["summary"]["prompt_item_count"] == 0)


def test_malformed_inputs_degrade() -> None:
    ctx = build_coverage_aware_prompt_context(
        job_request=123,
        source_coverage_report="x",
        visual_inclusion_plan=4.5,
        table_candidates_manifest=[1, 2],
        table_reconstruction_policy=object(),
        missing_material_context=7,
    )
    check("malformed → skipped", ctx["status"] == "skipped")
    check("malformed empty block", ctx["prompt_block"] == "")
    check("malformed job_request warning", JOB_REQUEST_MALFORMED in ctx["warnings"])
    check("malformed coverage warning", SOURCE_COVERAGE_MALFORMED in ctx["warnings"])


def test_all_empty_skipped_and_byte_equivalent() -> None:
    ctx = build_coverage_aware_prompt_context(
        job_request=_job_request(global_sel=_selection(mode="all")),
        source_coverage_report=_coverage(unreadable=0),
        visual_inclusion_plan=_plan(0),
        table_candidates_manifest=_manifest(0),
        table_reconstruction_policy=_policy(0),
        table_prompt_context=_table_prompt_context(0),
        missing_material_context=_missing(0),
    )
    check("all-inactive → skipped", ctx["status"] == "skipped")
    check("all-inactive empty block", ctx["prompt_block"] == "")
    check("all-inactive no items", ctx["items"] == [])


# --- Material page selection handling ----------------------------------------


def test_material_selection_active_detected() -> None:
    ctx = build_coverage_aware_prompt_context(
        job_request=_job_request(global_sel=_selection(mode="exclude", exclude=[3, 4]), leaky=True),
    )
    check("exclude selection active", ctx["summary"]["has_material_page_selections"] is True)
    check("exclude → completed", ctx["status"] == "completed")
    kinds = [item["kind"] for item in ctx["items"]]
    check("included_page item present", "included_page" in kinds)
    check("selection block guidance", "Coverage-aware generation guidance:" in ctx["prompt_block"])
    _assert_shape(ctx, "selection")


def test_material_selection_per_attachment() -> None:
    per = {"attachments": {"attachment_1": _selection(mode="include", include=[1, 2])}}
    ctx = build_coverage_aware_prompt_context(job_request=_job_request(per=per))
    check("per-attachment include active", ctx["summary"]["has_material_page_selections"] is True)


def test_material_selection_inactive_all_mode() -> None:
    ctx = build_coverage_aware_prompt_context(
        job_request=_job_request(global_sel=_selection(mode="all")),
    )
    check("all-mode not active", ctx["summary"]["has_material_page_selections"] is False)
    check("all-mode → skipped", ctx["status"] == "skipped")


# --- Source coverage handling ------------------------------------------------


def test_source_coverage_counts_summarized() -> None:
    ctx = build_coverage_aware_prompt_context(
        source_coverage_report=_coverage(source_count=2, covered=10, unreadable=3, leaky=True),
    )
    check("source_count summarized", ctx["summary"]["source_count"] == 2)
    check("covered summarized", ctx["summary"]["covered_page_count"] == 10)
    check("unreadable summarized", ctx["summary"]["unreadable_page_count"] == 3)
    kinds = [item["kind"] for item in ctx["items"]]
    check("source_gap active when unreadable", "source_gap" in kinds)
    _assert_shape(ctx, "coverage")


def test_source_coverage_no_gap_when_all_readable() -> None:
    ctx = build_coverage_aware_prompt_context(source_coverage_report=_coverage(covered=8, unreadable=0))
    check("no source_gap when readable", ctx["status"] == "skipped")
    check("counts still summarized", ctx["summary"]["covered_page_count"] == 8)


def test_source_coverage_skipped_status() -> None:
    ctx = build_coverage_aware_prompt_context(source_coverage_report=_coverage(status="skipped", unreadable=5))
    check("skipped coverage → zero counts", ctx["summary"]["unreadable_page_count"] == 0)


# --- Visual plan handling -----------------------------------------------------


def test_visual_plan_count_summarized() -> None:
    ctx = build_coverage_aware_prompt_context(visual_inclusion_plan=_plan(4))
    check("planned_visual_count", ctx["summary"]["planned_visual_count"] == 4)
    kinds = [item["kind"] for item in ctx["items"]]
    check("visual_plan signal active", "visual_plan" in kinds)
    check("visual block bullet", "Non-table visuals were planned" in ctx["prompt_block"])


def test_visual_plan_list_fallback() -> None:
    plan = {"status": "completed", "items": [{"plan_index": 1}, {"plan_index": 2}]}
    ctx = build_coverage_aware_prompt_context(visual_inclusion_plan=plan)
    check("plan list fallback count", ctx["summary"]["planned_visual_count"] == 2)


# --- Table policy handling ----------------------------------------------------


def test_table_candidates_and_policy_summarized() -> None:
    ctx = build_coverage_aware_prompt_context(
        table_candidates_manifest=_manifest(3),
        table_reconstruction_policy=_policy(2),
    )
    check("table_candidate_count", ctx["summary"]["table_candidate_count"] == 3)
    check("table_policy_item_count", ctx["summary"]["table_policy_item_count"] == 2)
    kinds = [item["kind"] for item in ctx["items"]]
    check("table_policy signal active", "table_policy" in kinds)


def test_table_prompt_context_raises_policy_count() -> None:
    ctx = build_coverage_aware_prompt_context(
        table_reconstruction_policy=_policy(0),
        table_prompt_context=_table_prompt_context(5),
    )
    check("prompt context raises count", ctx["summary"]["table_policy_item_count"] == 5)
    kinds = [item["kind"] for item in ctx["items"]]
    check("table_policy active via prompt ctx", "table_policy" in kinds)


# --- Missing-material handling ------------------------------------------------


def test_missing_material_count_summarized() -> None:
    ctx = build_coverage_aware_prompt_context(missing_material_context=_missing(2))
    check("missing_material_item_count", ctx["summary"]["missing_material_item_count"] == 2)
    kinds = [item["kind"] for item in ctx["items"]]
    check("missing_material signal active", "missing_material" in kinds)
    check("missing block bullet", "Missing visual/table guidance is active." in ctx["prompt_block"])


# --- Determinism / ordering / defensive cap ----------------------------------


def test_signal_order_and_item_ids() -> None:
    ctx = build_coverage_aware_prompt_context(
        job_request=_job_request(global_sel=_selection(mode="exclude", exclude=[2])),
        source_coverage_report=_coverage(unreadable=2),
        visual_inclusion_plan=_plan(1),
        table_candidates_manifest=_manifest(1),
        missing_material_context=_missing(1),
    )
    kinds = [item["kind"] for item in ctx["items"]]
    check(
        "signals in fixed order",
        kinds == ["included_page", "source_gap", "visual_plan", "table_policy", "missing_material"],
    )
    ids = [item["item_id"] for item in ctx["items"]]
    check(
        "ids sequential",
        ids == [
            "coverage_context_0001", "coverage_context_0002", "coverage_context_0003",
            "coverage_context_0004", "coverage_context_0005",
        ],
    )
    check("prompt_item_count == len(items)", ctx["summary"]["prompt_item_count"] == 5)
    _assert_shape(ctx, "ordered")


def test_max_items_defensive_cap() -> None:
    ctx = build_coverage_aware_prompt_context(
        source_coverage_report=_coverage(unreadable=2),
        visual_inclusion_plan=_plan(1),
        table_candidates_manifest=_manifest(1),
        max_items=1,
    )
    check("max_items truncates", len(ctx["items"]) == 1)
    check("max_items partial", ctx["status"] == "partial")
    check("max_items warning", MAX_ITEMS_APPLIED in ctx["warnings"])
    zero = build_coverage_aware_prompt_context(visual_inclusion_plan=_plan(1), max_items=0)
    check("max_items 0 → skipped", zero["status"] == "skipped")


def test_deterministic_repeated_calls() -> None:
    kwargs = dict(
        job_request=_job_request(global_sel=_selection(mode="exclude", exclude=[2])),
        source_coverage_report=_coverage(unreadable=1),
        visual_inclusion_plan=_plan(2),
        table_candidates_manifest=_manifest(1),
        missing_material_context=_missing(1),
    )
    first = build_coverage_aware_prompt_context(**kwargs)
    second = build_coverage_aware_prompt_context(**kwargs)
    check("deterministic dict", first == second)
    check("deterministic block", first["prompt_block"] == second["prompt_block"])


def test_hostile_canaries_stripped() -> None:
    ctx = build_coverage_aware_prompt_context(
        job_request=_job_request(global_sel=_selection(mode="exclude", exclude=[2]), leaky=True),
        source_coverage_report=_coverage(unreadable=2, leaky=True),
        visual_inclusion_plan=_plan(2),
        table_candidates_manifest=_manifest(2),
        table_reconstruction_policy=_policy(2),
        missing_material_context=_missing(2),
    )
    leak = _scan_for_leak(ctx)
    check("no leak in full context", leak is None, leak or "")
    for canary in FORBIDDEN_CANARIES:
        check(f"prompt_block free of canary: {canary[:24]}", canary not in ctx["prompt_block"])


def test_invalid_page_lists_not_active() -> None:
    # Non-positive / wrong-typed pages must not count as a real selection.
    bad = _job_request(global_sel={"mode": "x", "include_pages": [0, -1, "3", 2.0, True], "exclude_pages": []})
    ctx = build_coverage_aware_prompt_context(job_request=bad)
    check("bad page list not active", ctx["summary"]["has_material_page_selections"] is False)


# --- Integration: run_llm_job prompt wiring (cheap helper only) ---------------


def test_run_llm_job_prompt_helper() -> None:
    try:
        from pipeline.run_llm_job import _build_coverage_aware_prompt_block_safely
    except Exception as exc:  # pragma: no cover - host import guard
        print(f"[SKIP] run_llm_job helper import ({type(exc).__name__})")
        return
    check(
        "helper none → empty",
        _build_coverage_aware_prompt_block_safely(None, None, None, None, None, None) == "",
    )
    check(
        "helper inactive → empty",
        _build_coverage_aware_prompt_block_safely(
            _job_request(global_sel=_selection(mode="all")),
            _coverage(unreadable=0), _plan(0), _manifest(0), _policy(0), _missing(0),
        ) == "",
    )
    block = _build_coverage_aware_prompt_block_safely(
        _job_request(global_sel=_selection(mode="exclude", exclude=[3])),
        _coverage(unreadable=2), _plan(1), _manifest(1), _policy(1), _missing(1),
    )
    check("helper actionable → guidance", "Coverage-aware generation guidance:" in block)
    check("helper actionable signals", "Coverage signals:" in block)
    check("helper block no leak", _scan_for_leak(block) is None)
    # Must not duplicate the raw Slice 93/94 per-item blocks.
    check("helper no raw table block", "table block" not in block)
    check("helper no raw missing block", "missing block" not in block)


# --- Import hygiene (no provider/model/cloud/render/OCR/FastAPI/frontend) -----


def test_no_forbidden_imports() -> None:
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "pipeline" / "coverage_aware_prompt_context.py"
    text = src.read_text(encoding="utf-8")
    for forbidden in (
        "mistralai", "google.generativeai", "openai", "requests", "urllib.request",
        "httpx", "socket", "chandra", "fastapi", "PIL", "fitz", "playwright",
        "pipeline.run_llm_job", "pipeline.source_coverage_report",
        "pipeline.visual_inclusion_planner",
    ):
        check(f"no import of {forbidden}", f"import {forbidden}" not in text and f"from {forbidden}" not in text)


def test_module_not_loaded_heavy_deps() -> None:
    for forbidden in ("fastapi", "PIL", "fitz", "openai", "playwright"):
        check(f"not loaded after import: {forbidden}", forbidden not in sys.modules)


def main() -> int:
    test_all_missing_skipped()
    test_malformed_inputs_degrade()
    test_all_empty_skipped_and_byte_equivalent()
    test_material_selection_active_detected()
    test_material_selection_per_attachment()
    test_material_selection_inactive_all_mode()
    test_source_coverage_counts_summarized()
    test_source_coverage_no_gap_when_all_readable()
    test_source_coverage_skipped_status()
    test_visual_plan_count_summarized()
    test_visual_plan_list_fallback()
    test_table_candidates_and_policy_summarized()
    test_table_prompt_context_raises_policy_count()
    test_missing_material_count_summarized()
    test_signal_order_and_item_ids()
    test_max_items_defensive_cap()
    test_deterministic_repeated_calls()
    test_hostile_canaries_stripped()
    test_invalid_page_lists_not_active()
    # Import-hygiene checks run BEFORE the run_llm_job integration test, which may
    # itself import heavy extraction deps and pollute sys.modules.
    test_no_forbidden_imports()
    test_module_not_loaded_heavy_deps()
    test_run_llm_job_prompt_helper()
    print(f"\nCoverage-aware prompt context tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
