#!/usr/bin/env python3
"""Focused tests for the pure page/slide inclusion-exclusion model (Slice 78).

Run with:

    python test_scripts/test_page_selection_model.py

Synthetic dictionaries/lists only. No PDFs, images, providers, renderers, OCR
engines, or job artifacts are read or written. The module under test is pure and
stdlib-only.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

# Leak-detection regexes (synthetic canaries below are fed in to prove the model
# never copies hostile input into its output).
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|C:\\|[A-Za-z]:\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z]|mmproj|\.gguf|llama-server)")
FORBIDDEN_CANARIES = [
    "private-source.pdf",
    "Quarterly Private Plan",
    "raw document paragraph",
    "raw OCR dump",
    "source caption text",
    "table cell text",
    "assets/secret.png",
    "sk_pageselectioncanary1234567890",
    "/home/example/private-source.pdf",
    "synthetic boom",
]

from pipeline.page_selection_model import (  # noqa: E402
    MODE_ALL,
    MODE_EXCLUDE,
    MODE_INCLUDE,
    apply_page_selection,
    normalize_page_selection,
    summarize_page_selection,
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


def _no_leak(name: str, obj) -> None:
    blob = json.dumps(obj, sort_keys=True)
    check(f"{name}: no keylike", not KEYLIKE.search(blob), blob)
    check(f"{name}: no pathlike", not PATHLIKE.search(blob), blob)
    check(f"{name}: no urllike", not URLLIKE.search(blob), blob)
    check(f"{name}: no data/base64", not DATA_OR_BASE64.search(blob), blob)
    check(f"{name}: no argv/socket", not ARGV_OR_SOCKET.search(blob), blob)
    for canary in FORBIDDEN_CANARIES:
        check(f"{name}: no canary {canary!r}", canary not in blob, blob)


# ---------------------------------------------------------------------------
# normalize_page_selection
# ---------------------------------------------------------------------------

def test_missing_selection_defaults_to_all() -> None:
    out = normalize_page_selection(None)
    check("missing → mode all", out["mode"] == MODE_ALL, str(out))
    check("missing → empty include", out["include_pages"] == [], str(out))
    check("missing → empty exclude", out["exclude_pages"] == [], str(out))
    check("missing → selection_missing warning", "selection_missing" in out["warnings"], str(out))


def test_malformed_selection_degrades() -> None:
    for bad in ["not-a-dict", 42, [1, 2, 3], 3.14]:
        out = normalize_page_selection(bad)
        check(f"malformed {type(bad).__name__} → all", out["mode"] == MODE_ALL, str(out))
        check(
            f"malformed {type(bad).__name__} → selection_malformed",
            "selection_malformed" in out["warnings"],
            str(out),
        )


def test_unknown_mode_warns_and_falls_back() -> None:
    out = normalize_page_selection({"mode": "bogus", "include_pages": [1]})
    check("unknown mode → all", out["mode"] == MODE_ALL, str(out))
    check("unknown mode → mode_unknown warning", "mode_unknown" in out["warnings"], str(out))


def test_absent_mode_defaults_all_no_warning() -> None:
    out = normalize_page_selection({"exclude_pages": [2]})
    check("absent mode → all", out["mode"] == MODE_ALL, str(out))
    check("absent mode → no mode_unknown", "mode_unknown" not in out["warnings"], str(out))


def test_include_mode_explicit_only() -> None:
    out = normalize_page_selection({"mode": "include", "include_pages": [3, 1, 2]})
    check("include normalizes mode", out["mode"] == MODE_INCLUDE, str(out))
    check("include sorted/unique", out["include_pages"] == [1, 2, 3], str(out))


def test_exclude_mode() -> None:
    out = normalize_page_selection({"mode": "exclude", "exclude_pages": [5, 4]})
    check("exclude normalizes mode", out["mode"] == MODE_EXCLUDE, str(out))
    check("exclude sorted/unique", out["exclude_pages"] == [4, 5], str(out))


def test_all_mode_with_exclusions() -> None:
    out = normalize_page_selection({"mode": "all", "exclude_pages": [2, 4]})
    check("all keeps exclusions", out["exclude_pages"] == [2, 4], str(out))
    check("all mode preserved", out["mode"] == MODE_ALL, str(out))


def test_invalid_page_values_ignored() -> None:
    out = normalize_page_selection(
        {"mode": "include", "include_pages": [1, 0, -3, "x", 2.0, None, True, 2]}
    )
    check("invalid pages dropped", out["include_pages"] == [1, 2], str(out))
    check("invalid pages warn", "page_invalid" in out["warnings"], str(out))


def test_page_out_of_range_with_page_count() -> None:
    out = normalize_page_selection(
        {"mode": "include", "include_pages": [1, 2, 9]}, page_count=3
    )
    check("out-of-range dropped", out["include_pages"] == [1, 2], str(out))
    check("out-of-range warn", "page_out_of_range" in out["warnings"], str(out))


def test_invalid_page_count_warns() -> None:
    for bad in [0, -1, "five", 2.5, True]:
        out = normalize_page_selection(
            {"mode": "include", "include_pages": [1, 50]}, page_count=bad
        )
        check(f"bad page_count {bad!r} warns", "page_count_invalid" in out["warnings"], str(out))
        # No range filtering applied when page_count is invalid.
        check(f"bad page_count {bad!r} keeps pages", out["include_pages"] == [1, 50], str(out))


def test_duplicates_deduped_and_sorted() -> None:
    out = normalize_page_selection(
        {"mode": "include", "include_pages": [3, 3, 1, 2, 1], "exclude_pages": [5, 5]}
    )
    check("dedup/sort include", out["include_pages"] == [1, 2, 3], str(out))
    check("dedup/sort exclude", out["exclude_pages"] == [5], str(out))


def test_overlap_warns() -> None:
    out = normalize_page_selection(
        {"mode": "include", "include_pages": [1, 2, 3], "exclude_pages": [2]}
    )
    check("overlap warns", "exclude_overlaps_include" in out["warnings"], str(out))


def test_empty_include_mode_warns() -> None:
    out = normalize_page_selection({"mode": "include", "include_pages": []})
    check("empty include → empty list", out["include_pages"] == [], str(out))
    check("empty include warns", "include_empty" in out["warnings"], str(out))
    # all-mode with no pages must NOT warn include_empty
    out2 = normalize_page_selection({"mode": "all"})
    check("all mode no include_empty", "include_empty" not in out2["warnings"], str(out2))


def test_malformed_page_lists() -> None:
    out = normalize_page_selection({"mode": "include", "include_pages": "1,2,3"})
    check("string include list → empty", out["include_pages"] == [], str(out))
    check("string include list malformed", "selection_malformed" in out["warnings"], str(out))


# ---------------------------------------------------------------------------
# apply_page_selection
# ---------------------------------------------------------------------------

def test_apply_all_mode() -> None:
    out = apply_page_selection([3, 1, 2], {"mode": "all"})
    check("apply all included", out["included_pages"] == [1, 2, 3], str(out))
    check("apply all none excluded", out["excluded_pages"] == [], str(out))
    check("apply all effective mode", out["effective_mode"] == MODE_ALL, str(out))


def test_apply_all_with_exclusions() -> None:
    out = apply_page_selection([1, 2, 3, 4], {"mode": "all", "exclude_pages": [2, 4]})
    check("apply all-excl included", out["included_pages"] == [1, 3], str(out))
    check("apply all-excl excluded", out["excluded_pages"] == [2, 4], str(out))


def test_apply_include_mode() -> None:
    out = apply_page_selection([1, 2, 3, 4], {"mode": "include", "include_pages": [2, 3, 99]})
    # page 99 is not in the universe, so it is simply not included
    check("apply include included", out["included_pages"] == [2, 3], str(out))
    check("apply include excluded", out["excluded_pages"] == [1, 4], str(out))


def test_apply_exclude_mode() -> None:
    out = apply_page_selection([1, 2, 3], {"mode": "exclude", "exclude_pages": [2]})
    check("apply exclude included", out["included_pages"] == [1, 3], str(out))
    check("apply exclude excluded", out["excluded_pages"] == [2], str(out))
    check("apply exclude effective mode", out["effective_mode"] == MODE_EXCLUDE, str(out))


def test_apply_overlap_subtracts() -> None:
    out = apply_page_selection(
        [1, 2, 3], {"mode": "include", "include_pages": [1, 2, 3], "exclude_pages": [2]}
    )
    check("overlap subtracts exclusion", out["included_pages"] == [1, 3], str(out))
    check("overlap excluded shows page", out["excluded_pages"] == [2], str(out))
    check("overlap warning carried", "exclude_overlaps_include" in out["warnings"], str(out))


def test_apply_empty_include_yields_empty() -> None:
    out = apply_page_selection([1, 2, 3], {"mode": "include", "include_pages": []})
    check("empty include → nothing included", out["included_pages"] == [], str(out))
    check("empty include → all excluded", out["excluded_pages"] == [1, 2, 3], str(out))
    check("empty include warning carried", "include_empty" in out["warnings"], str(out))


def test_apply_invalid_page_numbers_degrade() -> None:
    out = apply_page_selection([1, 0, -2, "x", None, True, 2.0, 3], {"mode": "all"})
    check("apply drops invalid universe", out["included_pages"] == [1, 3], str(out))
    check("apply invalid universe warns", "page_invalid" in out["warnings"], str(out))


def test_apply_non_list_page_numbers() -> None:
    for bad in [None, "1,2,3", 5, {"a": 1}]:
        out = apply_page_selection(bad, {"mode": "all"})
        check(f"apply non-list {type(bad).__name__} → empty", out["included_pages"] == [], str(out))


def test_apply_no_inference() -> None:
    # No page numbers provided → nothing is included; pages are never invented.
    out = apply_page_selection([], {"mode": "include", "include_pages": [1, 2, 3]})
    check("apply no inference included", out["included_pages"] == [], str(out))
    check("apply no inference excluded", out["excluded_pages"] == [], str(out))


# ---------------------------------------------------------------------------
# summarize_page_selection
# ---------------------------------------------------------------------------

def test_summary_counts_with_page_count() -> None:
    out = summarize_page_selection(
        {"mode": "exclude", "exclude_pages": [2, 4]}, page_count=5
    )
    check("summary mode", out["mode"] == MODE_EXCLUDE, str(out))
    check("summary included count", out["included_page_count"] == 3, str(out))
    check("summary excluded count", out["excluded_page_count"] == 2, str(out))
    check("summary explicit exclude", out["explicit_exclude_count"] == 2, str(out))
    check("summary explicit include", out["explicit_include_count"] == 0, str(out))


def test_summary_include_counts_with_page_count() -> None:
    out = summarize_page_selection(
        {"mode": "include", "include_pages": [1, 2, 3], "exclude_pages": [2]}, page_count=10
    )
    check("summary include included count", out["included_page_count"] == 2, str(out))
    # excluded = universe(10) - included(2) = 8
    check("summary include excluded count", out["excluded_page_count"] == 8, str(out))
    check("summary include explicit include", out["explicit_include_count"] == 3, str(out))


def test_summary_without_page_count() -> None:
    out = summarize_page_selection({"mode": "include", "include_pages": [1, 2, 3], "exclude_pages": [2]})
    check("summary no-count included", out["included_page_count"] == 2, str(out))
    check("summary no-count excluded", out["excluded_page_count"] == 1, str(out))
    out2 = summarize_page_selection({"mode": "all", "exclude_pages": [1]})
    check("summary all no-count included unknown", out2["included_page_count"] == 0, str(out2))
    check("summary all no-count excluded", out2["excluded_page_count"] == 1, str(out2))


# ---------------------------------------------------------------------------
# determinism / purity / no-leak
# ---------------------------------------------------------------------------

def test_deterministic_repeated_calls() -> None:
    sel = {"mode": "include", "include_pages": [3, 1, 2, 2], "exclude_pages": [2, 9]}
    a = normalize_page_selection(sel, page_count=5)
    b = normalize_page_selection(sel, page_count=5)
    check("normalize deterministic", a == b, f"{a} != {b}")
    c = apply_page_selection([5, 4, 3, 2, 1], sel)
    d = apply_page_selection([5, 4, 3, 2, 1], sel)
    check("apply deterministic", c == d, f"{c} != {d}")
    e = summarize_page_selection(sel, page_count=5)
    f = summarize_page_selection(sel, page_count=5)
    check("summarize deterministic", e == f, f"{e} != {f}")


def test_no_raw_exception_messages() -> None:
    # A dict-like object whose attribute access raises must not leak its message.
    class Hostile(dict):
        def get(self, *a, **k):  # noqa: D401
            raise RuntimeError("synthetic boom sk_pageselectioncanary1234567890")

    out = normalize_page_selection(Hostile())
    check("hostile normalize degrades", out["mode"] == MODE_ALL, str(out))
    _no_leak("hostile normalize", out)
    out2 = summarize_page_selection(Hostile())
    _no_leak("hostile summarize", out2)


def test_no_leak_over_outputs() -> None:
    hostile_selection = {
        "mode": "/home/example/private-source.pdf",
        "include_pages": ["assets/secret.png", "raw OCR dump", 1],
        "exclude_pages": ["table cell text", 2],
        "note": "data:image/png;base64,AAAA",
        "url": "https://example.invalid/private-source.pdf",
    }
    _no_leak("normalize hostile", normalize_page_selection(hostile_selection, page_count=3))
    _no_leak("apply hostile", apply_page_selection([1, 2, "raw document paragraph"], hostile_selection))
    _no_leak("summarize hostile", summarize_page_selection(hostile_selection, page_count=3))


def test_module_is_pure_stdlib() -> None:
    import pipeline.page_selection_model as mod

    src = open(mod.__file__, encoding="utf-8").read()
    forbidden = [
        "fastapi",
        "import fitz",
        "pytesseract",
        "tesseract",
        "api.server",
        "job_manager",
        "JobManager",
        "source_coverage_artifact",
        "visual_assets_manifest",
        "visual_asset_scoring",
        "visual_replacement",
        "renderer",
        "import requests",
        "httpx",
        "openai",
        "anthropic",
        "clean.md",
    ]
    for token in forbidden:
        check(f"source free of {token!r}", token not in src, "")

    # Confirm none of the heavy/forbidden modules were imported at runtime.
    loaded = set(sys.modules)
    for token in ["fastapi", "fitz", "pytesseract", "requests", "httpx", "openai", "anthropic"]:
        check(f"{token} not loaded by import", token not in loaded, "")


def main() -> int:
    test_missing_selection_defaults_to_all()
    test_malformed_selection_degrades()
    test_unknown_mode_warns_and_falls_back()
    test_absent_mode_defaults_all_no_warning()
    test_include_mode_explicit_only()
    test_exclude_mode()
    test_all_mode_with_exclusions()
    test_invalid_page_values_ignored()
    test_page_out_of_range_with_page_count()
    test_invalid_page_count_warns()
    test_duplicates_deduped_and_sorted()
    test_overlap_warns()
    test_empty_include_mode_warns()
    test_malformed_page_lists()
    test_apply_all_mode()
    test_apply_all_with_exclusions()
    test_apply_include_mode()
    test_apply_exclude_mode()
    test_apply_overlap_subtracts()
    test_apply_empty_include_yields_empty()
    test_apply_invalid_page_numbers_degrade()
    test_apply_non_list_page_numbers()
    test_apply_no_inference()
    test_summary_counts_with_page_count()
    test_summary_include_counts_with_page_count()
    test_summary_without_page_count()
    test_deterministic_repeated_calls()
    test_no_raw_exception_messages()
    test_no_leak_over_outputs()
    test_module_is_pure_stdlib()

    print()
    print(f"Page selection model tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
