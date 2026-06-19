#!/usr/bin/env python3
"""Tests for Slice 173B verified-numeric generation prompt context.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, paths,
URLs, images, PDFs, DOCX files, ZIPs, or runtime artifacts. All ids, labels,
values, and canaries are synthetic.

Covers the pure ``verified_numeric_prompt_context`` builder and the off-by-default
``run_llm_job`` prompt-block hook ``_build_verified_numeric_prompt_block_safely``.
The hook is verified without importing FastAPI by parsing/importing only the helper.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.verified_numeric_prompt_context import (  # noqa: E402
    build_verified_numeric_prompt_context,
    CLOSED_FALLBACK_PHRASE,
    CONTEXT_KIND,
)

PASS = 0
FAIL = 0

HOSTILE_CANARIES = (
    "/home/private/source-deck.pdf",
    "C:\\private\\uploaded-source.docx",
    "https://private.invalid/source",
    "Authorization: Bearer sk_verifiednumeric1234567890",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_VNUM_MARKER",
    "TABLE_TEXT_PRIVATE_VNUM_MARKER",
    "CAPTION_PRIVATE_VNUM_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_VNUM_MARKER",
    "source text private marker",
)


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        suffix = f" - {detail}" if detail else ""
        print(f"[FAIL] {name}{suffix}")


def serialized(node: Any) -> str:
    return json.dumps(node, sort_keys=True)


def assert_no_canary(name: str, node: Any) -> None:
    blob = serialized(node)
    markers = [
        "/home/private",
        "C:\\private",
        "https://",
        "Authorization",
        "Bearer",
        "data:image",
        "base64",
        "OCR_PRIVATE",
        "TABLE_TEXT_PRIVATE",
        "CAPTION_PRIVATE",
        "PROVIDER_PAYLOAD_PRIVATE",
        "source text private marker",
    ]
    found = [m for m in markers if m in blob]
    found += [c for c in HOSTILE_CANARIES if c in blob]
    check(f"{name}: no hostile canary", not found, str(found))


def _verified_record(label: str, value: str, *, kind: str = "numeric", conf: str = "high") -> dict[str, Any]:
    return {
        "source_label": "synth",
        "target_id": label,
        "expected_label": label,
        "verified_value_rendered": value,
        "verified_value_kind": kind,
        "confidence": conf,
        "instruction_token": "use_verified_value",
    }


# ── 1. Off by default ───────────────────────────────────────────────────────


def test_off_by_default() -> None:
    recs = [_verified_record("synth_alpha", "0.69")]
    # No enabled flag at all -> skipped, empty block, prompt byte-identical.
    out = build_verified_numeric_prompt_context(recs)
    check("default skipped", out["status"] == "skipped", str(out))
    check("default empty block", out["prompt_block"] == "", str(out))
    check("default no fallback flag", out["summary"]["fallback_instruction_present"] is False, str(out))
    # Explicit False is the same.
    out_false = build_verified_numeric_prompt_context(recs, enabled=False)
    check("explicit false skipped", out_false["status"] == "skipped" and out_false["prompt_block"] == "", str(out_false))
    # Non-bool enabled degrades to off with a closed warning.
    out_bad = build_verified_numeric_prompt_context(recs, enabled="yes")
    check("non-bool enabled off", out_bad["status"] == "skipped" and out_bad["prompt_block"] == "", str(out_bad))
    check("non-bool warning", "enabled_not_bool" in out_bad["warnings"], str(out_bad))


# ── 2. Enabled: verified values + closed fallback ───────────────────────────


def test_enabled_renders_verified_and_fallback() -> None:
    recs = [
        _verified_record("synth_cross_entropy", "0.69"),
        _verified_record("synth_amount_of_say", "0.55"),
    ]
    out = build_verified_numeric_prompt_context(recs, enabled=True)
    check("enabled completed", out["status"] == "completed", str(out))
    check("enabled fact count", out["summary"]["verified_fact_count"] == 2, str(out))
    check("enabled fallback flag", out["summary"]["fallback_instruction_present"] is True, str(out))
    block = out["prompt_block"]
    check("block has header", "Verified numeric facts:" in block, block)
    check("block has value 1", "synth_cross_entropy = 0.69" in block, block)
    check("block has value 2", "synth_amount_of_say = 0.55" in block, block)
    check("block has closed fallback", CLOSED_FALLBACK_PHRASE in block, block)
    check("block forbids competing values", "Never present competing unresolved numeric values" in block, block)
    check("block forbids re-estimation", "do not replace them with newly estimated values" in block, block)


def test_enabled_with_no_records_still_emits_fallback() -> None:
    # Phase 0 pair with zero independently-verified values: the writer must still be
    # told to use the closed fallback rather than guess.
    out = build_verified_numeric_prompt_context([], enabled=True)
    check("empty completed", out["status"] == "completed", str(out))
    check("empty fact count 0", out["summary"]["verified_fact_count"] == 0, str(out))
    check("empty fallback present", out["summary"]["fallback_instruction_present"] is True, str(out))
    check("empty block has fallback", CLOSED_FALLBACK_PHRASE in out["prompt_block"], str(out))
    check("empty block has no value bullet", " = " not in out["prompt_block"], str(out))


# ── 3. Does not ban ordinary teaching / questions ───────────────────────────


def test_block_does_not_ban_questions_or_teaching() -> None:
    out = build_verified_numeric_prompt_context([_verified_record("synth_a", "1")], enabled=True)
    low = out["prompt_block"].lower()
    # The numeric discipline must not globally forbid questions or teaching wording.
    for banned in ("do not ask questions", "no questions", "do not explain", "no examples", "do not teach"):
        check(f"no global ban: {banned!r}", banned not in low, low)


# ── 4. Malformed / unverified records are not rendered ──────────────────────


def test_malformed_records_excluded_from_block() -> None:
    recs = [
        _verified_record("synth_good", "0.5"),
        {"target_id": "synth_no_token", "expected_label": "synth_no_token", "verified_value_rendered": "9.9"},  # wrong/absent token
        {"instruction_token": "use_verified_value", "expected_label": "synth_no_value"},  # no rendered value
        "not-a-dict",
    ]
    out = build_verified_numeric_prompt_context(recs, enabled=True)
    check("only valid rendered", out["summary"]["verified_fact_count"] == 1, str(out))
    block = out["prompt_block"]
    check("good rendered", "synth_good = 0.5" in block, block)
    check("token-less value not rendered", "9.9" not in block, block)
    check("malformed warning", "record_skipped_malformed" in out["warnings"], str(out))


# ── 5. Accepts the full generation-ready envelope ───────────────────────────


def test_accepts_envelope_shape() -> None:
    envelope = {"kind": "x", "records": [_verified_record("synth_env", "0.42")]}
    out = build_verified_numeric_prompt_context(envelope, enabled=True)
    check("envelope rendered", out["summary"]["verified_fact_count"] == 1, str(out))
    check("envelope value", "synth_env = 0.42" in out["prompt_block"], str(out))


# ── 6. Degrades safely ──────────────────────────────────────────────────────


def test_degrades_safely() -> None:
    for bad in (None, 123, "x", {"records": "nope"}):
        out = build_verified_numeric_prompt_context(bad, enabled=True)
        check(f"degrade kind {type(bad).__name__}", out["kind"] == CONTEXT_KIND, str(out))
        # Bad records list -> still a valid completed/ skipped context, never raises.
        check(f"degrade block str {type(bad).__name__}", isinstance(out["prompt_block"], str), str(out))
        assert_no_canary(f"degrade {type(bad).__name__}", out)


# ── 7. No leak in any output ─────────────────────────────────────────────────


def test_no_leak_sweep() -> None:
    recs = [_verified_record("synth_x", "0.1"), _verified_record("synth_y", "0.2")]
    assert_no_canary("enabled", build_verified_numeric_prompt_context(recs, enabled=True))
    assert_no_canary("disabled", build_verified_numeric_prompt_context(recs))


# ── 8. run_llm_job off-by-default hook ──────────────────────────────────────


def test_run_llm_job_hook_off_by_default() -> None:
    # Import only the helper to avoid pulling FastAPI/render deps at module import.
    from pipeline.run_llm_job import _build_verified_numeric_prompt_block_safely as hook

    # Normal user path: nothing passed -> empty block -> prompt byte-identical.
    check("hook none -> empty", hook(None) == "", "expected empty")
    check("hook non-dict -> empty", hook("x") == "", "expected empty")
    check("hook skipped ctx -> empty", hook({"status": "skipped", "prompt_block": ""}) == "", "expected empty")
    # Operator path: a completed context yields its block.
    ctx = build_verified_numeric_prompt_context([_verified_record("synth_a", "0.9")], enabled=True)
    block = hook(ctx)
    check("hook completed -> block", isinstance(block, str) and "synth_a = 0.9" in block, block)
    # Malformed context never raises.
    check("hook bad block type -> empty", hook({"status": "completed", "prompt_block": 123}) == "", "expected empty")


def test_run_llm_job_signature_default_none() -> None:
    # The new kwarg must default to None so existing callers are byte-identical.
    src = (REPO / "pipeline" / "run_llm_job.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_llm_job":
            found = True
            names = [a.arg for a in node.args.kwonlyargs]
            check("kwarg present", "verified_numeric_context" in names, str(names))
            idx = names.index("verified_numeric_context")
            default = node.args.kw_defaults[idx]
            is_none = isinstance(default, ast.Constant) and default.value is None
            check("kwarg defaults None", is_none, ast.dump(default) if default else "missing")
    check("run_llm_job found", found)


# ── 9. Import hygiene (pure module) ─────────────────────────────────────────


def test_import_hygiene() -> None:
    tree = ast.parse((REPO / "pipeline" / "verified_numeric_prompt_context.py").read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    forbidden = ("fastapi", "frontend", "provider", "openai", "pipeline", "requests", "httpx", "socket", "subprocess")
    bad = [n for n in imports for part in forbidden if part in n.lower()]
    check("no forbidden imports", bad == [], str(bad))


def run() -> int:
    test_off_by_default()
    test_enabled_renders_verified_and_fallback()
    test_enabled_with_no_records_still_emits_fallback()
    test_block_does_not_ban_questions_or_teaching()
    test_malformed_records_excluded_from_block()
    test_accepts_envelope_shape()
    test_degrades_safely()
    test_no_leak_sweep()
    test_run_llm_job_hook_off_by_default()
    test_run_llm_job_signature_default_none()
    test_import_hygiene()
    print(f"\nverified_numeric_prompt_context: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
