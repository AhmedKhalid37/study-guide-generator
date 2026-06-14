#!/usr/bin/env python3
"""Focused tests for the table reconstruction prompt-context builder (Slice 93).

Run with:

    python test_scripts/test_table_reconstruction_prompt_context.py

Synthetic dictionaries only. No PDFs, images, providers, renderers, OCR engines, or
model calls are required. The module turns the already-sanitized Slice 92 table
candidate manifest + Slice 85 reconstruction policy into a short, deterministic,
leak-free prompt context whose ``prompt_block`` is safe to append to the existing
generation prompt. It reconstructs no table and inspects no PDF/image.
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
CANDIDATE_ID_RE = re.compile(r"^table_candidate_\d{4,}$")
FORBIDDEN_CANARIES = [
    "private-source.pdf",
    "Quarterly Private Plan",
    "raw document paragraph",
    "raw OCR dump",
    "source caption text",
    "table cell text",
    "assets/secret.png",
    "sk_tablepromptcontext1234567890",
    "synthetic boom with private details",
]

from pipeline.table_reconstruction_prompt_context import (  # noqa: E402
    CONTEXT_KIND,
    MAX_ITEMS_APPLIED,
    SKIP_UNSAFE_EXCLUDED,
    build_table_reconstruction_prompt_context,
)
from pipeline.table_candidate_manifest import (  # noqa: E402
    build_table_candidates_manifest,
)
from pipeline.table_reconstruction_policy import (  # noqa: E402
    build_table_reconstruction_policy,
)
from pipeline.table_reconstruction_policy_artifact import (  # noqa: E402
    write_table_reconstruction_policy,
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
    """Hostile fields that must never survive into the prompt context."""
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


def _policy_item(action: str, source_page: Any, preserve: list[str], leaky: bool = False) -> dict[str, Any]:
    item = {
        "source_index": 0,
        "source_page": source_page,
        "table_kind": "grid_table",
        "action": action,
        "reason": "text_layer_available",
        "preserve": list(preserve),
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


def _manifest(candidate_ids: list[str], leaky: bool = False) -> dict[str, Any]:
    candidates = []
    for index, cid in enumerate(candidate_ids):
        rec = {
            "candidate_id": cid,
            "source_index": index,
            "source_page": index + 1,
            "table_kind": "grid_table",
            "confidence": "high",
            "signals": {"has_text_layer": True, "rows": 4, "columns": 3},
            "warnings": [],
        }
        if leaky:
            rec.update(_leaky_fields())
        candidates.append(rec)
    return {
        "version": 1,
        "kind": "table_candidates_manifest",
        "status": "completed",
        "summary": {"table_like_candidate_count": len(candidates)},
        "candidates": candidates,
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


# --- Degenerate / missing / malformed inputs ---------------------------------


def test_missing_artifacts_skipped() -> None:
    both_none = build_table_reconstruction_prompt_context(None, None)
    check("both None → skipped", both_none["status"] == "skipped")
    check("both None empty block", both_none["prompt_block"] == "")
    check("both None no items", both_none["items"] == [])
    check("both None prompt_item_count 0", both_none["summary"]["prompt_item_count"] == 0)
    policy_none = build_table_reconstruction_prompt_context(_manifest(["table_candidate_0001"]), None)
    check("policy None → skipped", policy_none["status"] == "skipped")
    check("policy None empty block", policy_none["prompt_block"] == "")


def test_malformed_artifacts_degrade() -> None:
    for bad in (123, "x", [1, 2], 4.5):
        ctx = build_table_reconstruction_prompt_context(None, bad)
        check(f"malformed policy {type(bad).__name__} → skipped", ctx["status"] == "skipped")
        check(f"malformed policy {type(bad).__name__} empty block", ctx["prompt_block"] == "")
    bad_items = build_table_reconstruction_prompt_context(None, {"status": "completed", "items": 5})
    check("non-list items → skipped", bad_items["status"] == "skipped")
    # A malformed manifest still degrades safely (ids synthesized) when policy is ok.
    ctx = build_table_reconstruction_prompt_context(
        99, _policy([_policy_item("reconstruct_with_original", 4, ["headers"])])
    )
    check("malformed manifest + ok policy → context built", ctx["status"] == "completed")
    check("malformed manifest synthesizes id", CANDIDATE_ID_RE.match(ctx["items"][0]["candidate_id"]) is not None)


def test_skipped_policy_skips_context() -> None:
    ctx = build_table_reconstruction_prompt_context(None, _policy([], status="skipped"))
    check("skipped policy → skipped context", ctx["status"] == "skipped")
    check("skipped policy empty block", ctx["prompt_block"] == "")


def test_empty_policy_items_empty_context() -> None:
    ctx = build_table_reconstruction_prompt_context(_manifest([]), _policy([]))
    check("empty items not skipped", ctx["status"] == "completed")
    check("empty items prompt_item_count 0", ctx["summary"]["prompt_item_count"] == 0)
    check("empty items empty block", ctx["prompt_block"] == "")
    check("kind set", ctx["kind"] == CONTEXT_KIND)


# --- Action handling ----------------------------------------------------------


def test_reconstruct_with_original_instruction() -> None:
    ctx = build_table_reconstruction_prompt_context(
        _manifest(["table_candidate_0001"]),
        _policy([_policy_item("reconstruct_with_original", 4, ["headers", "numeric_values", "units"])]),
    )
    item = ctx["items"][0]
    check("reconstruct action preserved", item["action"] == "reconstruct_with_original")
    check("reconstruct instruction reconstructs", "Reconstruct the table on page 4" in item["instruction"])
    check("reconstruct instruction no-invent", "Do not invent" in item["instruction"])
    check("reconstruct instruction source-text-only", "source text" in item["instruction"])
    check("reconstruct instruction preserves", "Preserve" in item["instruction"])
    check("reconstruct counted", ctx["summary"]["reconstruct_with_original_count"] == 1)
    check("reconstruct block has guidance", "Table reconstruction guidance:" in ctx["prompt_block"])
    check("reconstruct block has page line", "Page 4: reconstruct with original" in ctx["prompt_block"])


def test_simplify_only_instruction() -> None:
    ctx = build_table_reconstruction_prompt_context(
        _manifest(["table_candidate_0001"]),
        _policy([_policy_item("simplify_only", 7, ["exam_terms"])]),
    )
    item = ctx["items"][0]
    check("simplify action preserved", item["action"] == "simplify_only")
    check("simplify instruction simplifies", "simplified version of the table on page 7" in item["instruction"])
    check("simplify instruction no-invent", "Do not invent" in item["instruction"])
    check("simplify counted", ctx["summary"]["simplify_only_count"] == 1)
    check("simplify block page line", "Page 7: simplify only" in ctx["prompt_block"])


def test_defer_and_skip_unreadable_notes() -> None:
    ctx = build_table_reconstruction_prompt_context(
        _manifest(["table_candidate_0001", "table_candidate_0002"]),
        _policy(
            [
                _policy_item("defer", 3, []),
                _policy_item("skip_unreadable", 9, []),
            ]
        ),
    )
    defer_item, skip_item = ctx["items"][0], ctx["items"][1]
    check("defer honest note", "not be readable" in defer_item["instruction"])
    check("defer no-invent", "Do not invent" in defer_item["instruction"])
    check("skip_unreadable honest note", "not be readable" in skip_item["instruction"])
    check("skip_unreadable no-invent", "Do not invent" in skip_item["instruction"])
    check("defer counted", ctx["summary"]["defer_count"] == 1)
    check("skip counted", ctx["summary"]["skip_count"] == 1)
    check("note block line", "do not invent rows or values" in ctx["prompt_block"])


def test_skip_unsafe_excluded() -> None:
    ctx = build_table_reconstruction_prompt_context(
        _manifest(["table_candidate_0001", "table_candidate_0002"]),
        _policy(
            [
                _policy_item("reconstruct_with_original", 4, ["headers"]),
                _policy_item("skip_unsafe", 5, []),
            ]
        ),
    )
    actions = [item["action"] for item in ctx["items"]]
    check("skip_unsafe not an item", "skip_unsafe" not in actions)
    check("only one emitted item", len(ctx["items"]) == 1)
    check("skip_unsafe warning recorded", SKIP_UNSAFE_EXCLUDED in ctx["warnings"])
    check("policy_item_count counts both", ctx["summary"]["policy_item_count"] == 2)
    check("prompt_item_count counts emitted only", ctx["summary"]["prompt_item_count"] == 1)


def test_unknown_action_dropped() -> None:
    ctx = build_table_reconstruction_prompt_context(
        _manifest(["table_candidate_0001"]),
        _policy([_policy_item("hostile_action_boom", 4, [])]),
    )
    check("unknown action drops item", ctx["items"] == [])
    check("unknown action empty block", ctx["prompt_block"] == "")


# --- Sanitization guarantees --------------------------------------------------


def test_preserve_tokens_closed_and_deterministic() -> None:
    closed = {"headers", "column_labels", "row_labels", "exam_terms", "numeric_values", "units"}
    canonical = ["headers", "column_labels", "row_labels", "exam_terms", "numeric_values", "units"]
    ctx = build_table_reconstruction_prompt_context(
        _manifest(["table_candidate_0001"]),
        _policy([_policy_item(
            "reconstruct_with_original", 4,
            # deliberately scrambled + hostile tokens
            ["units", "headers", "synthetic boom with private details", "numeric_values",
             "row_labels", "exam_terms", "column_labels"],
        )]),
    )
    preserve = ctx["items"][0]["preserve"]
    check("preserve subset of closed set", set(preserve) <= closed)
    check("preserve hostile token dropped", "synthetic boom with private details" not in preserve)
    check("preserve canonical order", preserve == canonical)


def test_pages_are_positive_ints_only() -> None:
    ctx = build_table_reconstruction_prompt_context(
        _manifest(["table_candidate_0001"] * 4),
        _policy(
            [
                _policy_item("reconstruct_with_original", 0, ["headers"]),    # non-positive
                _policy_item("simplify_only", -3, ["headers"]),               # negative
                _policy_item("defer", "4", []),                               # string
                _policy_item("skip_unreadable", 2.0, []),                     # float
            ]
        ),
    )
    for item in ctx["items"]:
        page = item["source_page"]
        check(
            f"page None or positive int ({page!r})",
            page is None or (isinstance(page, int) and not isinstance(page, bool) and page > 0),
        )


def test_candidate_ids_safe_shape() -> None:
    # Manifest carries valid ids; one hostile id forces synthesis.
    manifest = _manifest(["table_candidate_0001"])
    manifest["candidates"].append(
        {"candidate_id": "../../etc/passwd", "source_index": 1, "source_page": 2,
         "table_kind": "grid_table", "signals": {}}
    )
    ctx = build_table_reconstruction_prompt_context(
        manifest,
        _policy(
            [
                _policy_item("reconstruct_with_original", 4, ["headers"]),
                _policy_item("simplify_only", 5, ["headers"]),
            ]
        ),
    )
    for item in ctx["items"]:
        check(f"candidate_id safe shape ({item['candidate_id']})", CANDIDATE_ID_RE.match(item["candidate_id"]) is not None)


def test_hostile_canaries_stripped() -> None:
    manifest = _manifest(["table_candidate_0001", "table_candidate_0002"], leaky=True)
    policy = _policy(
        [
            _policy_item("reconstruct_with_original", 4, ["headers"], leaky=True),
            _policy_item("skip_unreadable", 8, [], leaky=True),
        ]
    )
    ctx = build_table_reconstruction_prompt_context(manifest, policy)
    leak = _scan_for_leak(ctx)
    check("no leak in full context", leak is None, leak or "")
    for canary in FORBIDDEN_CANARIES:
        check(f"prompt_block free of canary: {canary[:24]}", canary not in ctx["prompt_block"])


def test_deterministic_repeated_calls() -> None:
    manifest = _manifest(["table_candidate_0001", "table_candidate_0002"])
    policy = _policy(
        [
            _policy_item("reconstruct_with_original", 4, ["headers", "numeric_values"]),
            _policy_item("defer", 9, []),
        ]
    )
    first = build_table_reconstruction_prompt_context(manifest, policy)
    second = build_table_reconstruction_prompt_context(manifest, policy)
    check("deterministic dict", first == second)
    check("deterministic block", first["prompt_block"] == second["prompt_block"])


def test_max_items_defensive_cap() -> None:
    ids = [f"table_candidate_{i:04d}" for i in range(1, 6)]
    items = [_policy_item("reconstruct_with_original", i + 1, ["headers"]) for i in range(5)]
    ctx = build_table_reconstruction_prompt_context(_manifest(ids), _policy(items), max_items=2)
    check("max_items truncates", len(ctx["items"]) == 2)
    check("max_items partial", ctx["status"] == "partial")
    check("max_items warning", MAX_ITEMS_APPLIED in ctx["warnings"])
    check("max_items prompt_item_count", ctx["summary"]["prompt_item_count"] == 2)
    # max_items=0 emits nothing.
    zero = build_table_reconstruction_prompt_context(_manifest(ids), _policy(items), max_items=0)
    check("max_items 0 empty", zero["items"] == [])


# --- Real end-to-end chain (Slice 92 manifest + Slice 85 policy) -------------


def test_real_chain_from_visual_manifest() -> None:
    # Synthetic sanitized visual manifest with one rich table-like record.
    visual_manifest = {
        "status": "completed",
        "assets": [
            {
                "source_index": 0,
                "source_page": 4,
                "asset_type": "grid_table",
                "confidence": "high",
                "signals": {
                    "has_text_layer": True,
                    "rows": 5,
                    "columns": 3,
                    "cell_text_count": 15,
                    "numeric_cell_count": 6,
                    "header_cell_count": 3,
                },
                # hostile fields the chain must never echo
                **_leaky_fields(),
            },
            {"source_index": 1, "source_page": 2, "asset_type": "figure", **_leaky_fields()},
        ],
    }
    candidate_manifest = build_table_candidates_manifest(visual_manifest)
    from pipeline.table_candidate_manifest import table_policy_candidates
    policy = build_table_reconstruction_policy(table_policy_candidates(candidate_manifest))
    ctx = build_table_reconstruction_prompt_context(candidate_manifest, policy)
    check("real chain completed", ctx["status"] == "completed")
    check("real chain one item", len(ctx["items"]) == 1)
    item = ctx["items"][0]
    check("real chain reconstruct", item["action"] == "reconstruct_with_original")
    check("real chain page 4", item["source_page"] == 4)
    check("real chain candidate id", CANDIDATE_ID_RE.match(item["candidate_id"]) is not None)
    check("real chain preserves numeric", "numeric_values" in item["preserve"])
    check("real chain no leak", _scan_for_leak(ctx) is None)


# --- Integration: run_llm_job prompt wiring (cheap helper only) ---------------


def test_run_llm_job_prompt_helper() -> None:
    try:
        from pipeline.run_llm_job import _build_table_prompt_block_safely
    except Exception as exc:  # pragma: no cover - host import guard
        print(f"[SKIP] run_llm_job helper import ({type(exc).__name__})")
        return
    # No artifacts → empty (prompt byte-identical).
    check("helper none → empty", _build_table_prompt_block_safely(None, None) == "")
    check(
        "helper skipped policy → empty",
        _build_table_prompt_block_safely(None, _policy([], status="skipped")) == "",
    )
    check(
        "helper empty items → empty",
        _build_table_prompt_block_safely(_manifest([]), _policy([])) == "",
    )
    # Actionable items → safe guidance block.
    block = _build_table_prompt_block_safely(
        _manifest(["table_candidate_0001"]),
        _policy([_policy_item("reconstruct_with_original", 4, ["headers"])]),
    )
    check("helper actionable → guidance", "Table reconstruction guidance:" in block)
    check("helper actionable no-invent", "Do not invent" in block)
    check("helper block no leak", _scan_for_leak(block) is None)


def test_writer_then_context_roundtrip() -> None:
    # Policy artifact writer output (degraded to skipped via None) → skipped context.
    class _StubJob:
        table_reconstruction_policy_json = "/dev/null"

        def save_text(self, *_args: Any, **_kwargs: Any) -> None:
            return None

    policy = write_table_reconstruction_policy(_StubJob(), None)
    ctx = build_table_reconstruction_prompt_context(None, policy)
    check("skipped policy artifact → skipped context", ctx["status"] == "skipped")


# --- Import hygiene (no provider/model/cloud/render/OCR/FastAPI/frontend) -----


def test_no_forbidden_imports() -> None:
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "pipeline" / "table_reconstruction_prompt_context.py"
    text = src.read_text(encoding="utf-8")
    for forbidden in (
        "mistralai", "google.generativeai", "openai", "requests", "urllib.request",
        "httpx", "socket", "chandra", "fastapi", "PIL", "fitz", "playwright",
        "pipeline.run_llm_job",
    ):
        check(f"no import of {forbidden}", f"import {forbidden}" not in text and f"from {forbidden}" not in text)


def test_module_not_loaded_heavy_deps() -> None:
    # Importing the builder must not drag in providers/renderers/FastAPI.
    for forbidden in ("fastapi", "PIL", "fitz", "openai", "playwright"):
        check(f"not loaded after import: {forbidden}", forbidden not in sys.modules)


def main() -> int:
    test_missing_artifacts_skipped()
    test_malformed_artifacts_degrade()
    test_skipped_policy_skips_context()
    test_empty_policy_items_empty_context()
    test_reconstruct_with_original_instruction()
    test_simplify_only_instruction()
    test_defer_and_skip_unreadable_notes()
    test_skip_unsafe_excluded()
    test_unknown_action_dropped()
    test_preserve_tokens_closed_and_deterministic()
    test_pages_are_positive_ints_only()
    test_candidate_ids_safe_shape()
    test_hostile_canaries_stripped()
    test_deterministic_repeated_calls()
    test_max_items_defensive_cap()
    test_real_chain_from_visual_manifest()
    # Import-hygiene checks run BEFORE the run_llm_job integration test, which may
    # itself import heavy extraction deps and pollute sys.modules.
    test_no_forbidden_imports()
    test_module_not_loaded_heavy_deps()
    test_run_llm_job_prompt_helper()
    test_writer_then_context_roundtrip()
    print(f"\nTable reconstruction prompt context tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
