#!/usr/bin/env python3
"""Focused tests for the dual-explanation generation prompt context (Slice 99).

Run with:

    python test_scripts/test_dual_explanation_prompt_context.py

Explain like I'm 10 / Exam answer mode v1. The module turns a single safe boolean
(``enabled``) into a short, deterministic, leak-free ``prompt_block`` that asks the
guide generator to add a beginner-friendly "Explain it simply" block plus a formal
"Exam answer" block for difficult / exam-important concepts. It reads no source
text, inspects no PDF/image, OCRs nothing, reconstructs no table, and calls no
provider / model / cloud. Synthetic inputs only.
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
# Synthetic canaries that must NEVER appear in the emitted context/prompt block.
FORBIDDEN_CANARIES = [
    "private-source.pdf",
    "Quarterly Private Plan",
    "raw document paragraph",
    "raw OCR dump",
    "source caption text",
    "table cell text",
    "assets/secret.png",
    "sk_dualexplanationcontext1234567890",
    "synthetic boom with private details",
]

from pipeline.dual_explanation_prompt_context import (  # noqa: E402
    CONTEXT_KIND,
    CONTEXT_VERSION,
    ENABLED_NOT_BOOL,
    MAX_ITEMS_APPLIED,
    build_dual_explanation_prompt_context,
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
                return f"{path} (canary: {canary!r})"
        for label, pattern in (
            ("keylike", KEYLIKE),
            ("pathlike", PATHLIKE),
            ("urllike", URLLIKE),
            ("data/base64", DATA_OR_BASE64),
            ("argv/socket", ARGV_OR_SOCKET),
        ):
            if pattern.search(node):
                return f"{path} ({label}: {node[:40]!r})"
    return None


# --- Tests --------------------------------------------------------------------


def test_disabled_and_missing_skipped() -> None:
    for label, value in (("None", None), ("False", False)):
        ctx = build_dual_explanation_prompt_context(value)
        check(f"{label} → skipped", ctx["status"] == "skipped")
        check(f"{label} → empty prompt_block", ctx["prompt_block"] == "")
        check(f"{label} → no item", ctx["summary"]["prompt_item_count"] == 0)
        check(f"{label} → enabled flag false", ctx["summary"]["enabled"] is False)
        check(f"{label} → no warnings", ctx["warnings"] == [])
        check(f"{label} → kind/version", ctx["kind"] == CONTEXT_KIND and ctx["version"] == CONTEXT_VERSION)


def test_enabled_completed_with_both_modes() -> None:
    ctx = build_dual_explanation_prompt_context(True)
    check("True → completed", ctx["status"] == "completed")
    check("True → enabled flag true", ctx["summary"]["enabled"] is True)
    check("True → one prompt item", ctx["summary"]["prompt_item_count"] == 1)
    block = ctx["prompt_block"]
    check("True → non-empty block", isinstance(block, str) and bool(block.strip()))
    # Both requested explanation modes must be present.
    check("block has 'Explain it simply'", "Explain it simply:" in block)
    check("block has 'Exam answer'", "Exam answer:" in block)
    check("block names dual explanation mode", "Dual explanation mode:" in block)
    # Source-grounded / no-invent guardrails must be present.
    check("block says source-grounded", "source-grounded" in block)
    check("block says do not invent", "Do not invent" in block)
    check("block has no warnings", ctx["warnings"] == [])


def test_malformed_enabled_degrades_safely() -> None:
    # Any non-bool, non-None enabled value is malformed: off + closed warning.
    for label, value in (
        ("string", "true"),
        ("int", 1),
        ("list", ["yes"]),
        ("dict", {"enabled": True}),
        ("leaky string", "sk_dualexplanationcontext1234567890"),
    ):
        ctx = build_dual_explanation_prompt_context(value)
        check(f"malformed {label} → skipped", ctx["status"] == "skipped")
        check(f"malformed {label} → empty block", ctx["prompt_block"] == "")
        check(f"malformed {label} → enabled_not_bool warning", ctx["warnings"] == [ENABLED_NOT_BOOL])
        check(f"malformed {label} → no leak", _scan_for_leak(ctx) is None)


def test_max_items_defensive_cap() -> None:
    # max_items below the single item count zeroes the block out (defensive only).
    ctx = build_dual_explanation_prompt_context(True, max_items=0)
    check("max_items=0 → skipped", ctx["status"] == "skipped")
    check("max_items=0 → empty block", ctx["prompt_block"] == "")
    check("max_items=0 → enabled flag stays true", ctx["summary"]["enabled"] is True)
    check("max_items=0 → MAX_ITEMS_APPLIED warning", ctx["warnings"] == [MAX_ITEMS_APPLIED])
    # max_items at/above the item count leaves the completed block intact.
    for value in (1, 5, 500):
        ctx_ok = build_dual_explanation_prompt_context(True, max_items=value)
        check(f"max_items={value} → completed", ctx_ok["status"] == "completed")
        check(f"max_items={value} → block present", "Exam answer:" in ctx_ok["prompt_block"])
    # A bool max_items is never a valid count and must not silently cap.
    ctx_bool = build_dual_explanation_prompt_context(True, max_items=True)
    check("max_items=True (bool) ignored → completed", ctx_bool["status"] == "completed")
    # A negative max_items is ignored (defensive ceiling only applies to >= 0).
    ctx_neg = build_dual_explanation_prompt_context(True, max_items=-1)
    check("max_items=-1 ignored → completed", ctx_neg["status"] == "completed")


def test_deterministic() -> None:
    a = build_dual_explanation_prompt_context(True)
    b = build_dual_explanation_prompt_context(True)
    check("deterministic enabled block", a == b)
    check("deterministic enabled block text", a["prompt_block"] == b["prompt_block"])
    c = build_dual_explanation_prompt_context(False)
    d = build_dual_explanation_prompt_context(None)
    check("deterministic disabled shape (False==None)", c == d)


def test_no_leak_in_outputs() -> None:
    for value in (True, False, None, "true", 1, {"x": 1}):
        ctx = build_dual_explanation_prompt_context(value)
        leak = _scan_for_leak(ctx)
        check(f"no leak for input {value!r}", leak is None, leak or "")


def test_never_raises() -> None:
    class Hostile:
        def __bool__(self):  # pragma: no cover - defensive
            raise RuntimeError("synthetic boom with private details")

    try:
        ctx = build_dual_explanation_prompt_context(Hostile())
        ok = ctx["status"] == "skipped" and ctx["prompt_block"] == ""
        check("hostile input degrades safely", ok)
        check("hostile input no leak", _scan_for_leak(ctx) is None)
    except Exception as exc:  # pragma: no cover - must never happen
        check("hostile input degrades safely", False, f"raised {type(exc).__name__}")


# --- Import hygiene (no provider/model/cloud/render/OCR/FastAPI/frontend) -----


def test_no_forbidden_imports() -> None:
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "pipeline" / "dual_explanation_prompt_context.py"
    text = src.read_text(encoding="utf-8")
    for forbidden in (
        "mistralai", "google.generativeai", "openai", "requests", "urllib.request",
        "httpx", "socket", "chandra", "fastapi", "PIL", "fitz", "playwright",
        "pipeline.run_llm_job", "pipeline.llm_client", "pipeline.orchestrator",
    ):
        check(
            f"no import of {forbidden}",
            f"import {forbidden}" not in text and f"from {forbidden}" not in text,
        )


def test_module_not_loaded_heavy_deps() -> None:
    for forbidden in ("fastapi", "PIL", "fitz", "openai", "playwright"):
        check(f"not loaded after import: {forbidden}", forbidden not in sys.modules)


def test_run_llm_job_prompt_helper() -> None:
    try:
        from pipeline.run_llm_job import _build_dual_explanation_prompt_block_safely
    except Exception as exc:  # pragma: no cover - host import guard
        print(f"[SKIP] run_llm_job helper import ({type(exc).__name__})")
        return
    check(
        "integration: disabled → empty (byte-equivalent)",
        _build_dual_explanation_prompt_block_safely(False) == "",
    )
    check(
        "integration: None → empty (byte-equivalent)",
        _build_dual_explanation_prompt_block_safely(None) == "",
    )
    block = _build_dual_explanation_prompt_block_safely(True)
    check("integration: enabled → guidance", "Dual explanation mode:" in block)
    check("integration: enabled has both modes", "Explain it simply:" in block and "Exam answer:" in block)
    check("integration: block no leak", _scan_for_leak(block) is None)
    check("integration: malformed → empty", _build_dual_explanation_prompt_block_safely("true") == "")


def main() -> int:
    test_disabled_and_missing_skipped()
    test_enabled_completed_with_both_modes()
    test_malformed_enabled_degrades_safely()
    test_max_items_defensive_cap()
    test_deterministic()
    test_no_leak_in_outputs()
    test_never_raises()
    # Import-hygiene checks run BEFORE the run_llm_job integration test, which may
    # itself import heavy extraction deps and pollute sys.modules.
    test_no_forbidden_imports()
    test_module_not_loaded_heavy_deps()
    test_run_llm_job_prompt_helper()
    print(f"\nDual explanation prompt context tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
