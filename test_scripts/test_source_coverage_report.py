#!/usr/bin/env python3
"""Focused tests for the pure source coverage report builder.

Run with:

    python test_scripts/test_source_coverage_report.py

Synthetic dictionaries only. No PDFs, images, providers, renderers, OCR engines,
or job artifacts are read or written.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|C:\\\\|\\\\\\\\|[A-Za-z]:\\\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z]|mmproj|\\.gguf|llama-server)")
FORBIDDEN_CANARIES = [
    "private-source.pdf",
    "Quarterly Private Plan",
    "raw document paragraph",
    "raw OCR dump",
    "source caption text",
    "table cell text",
    "assets/secret.png",
    "sk_sourcecoveragecanary1234567890",
]

from pipeline.source_coverage_report import build_source_coverage_report  # noqa: E402


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


def _metadata(sources: list[dict]) -> dict:
    return {
        "version": 2,
        "kind": "extraction_metadata",
        "status": "completed",
        "sources": sources,
    }


def _pdf_source(pages: list[dict], *, page_count: int | None = None) -> dict:
    return {
        "filename": "private-source.pdf",
        "title": "Quarterly Private Plan",
        "path": "/home/example/private-source.pdf",
        "content_type": "application/pdf",
        "page_count": page_count if page_count is not None else len(pages),
        "pages": pages,
        "warnings": ["upstream warning with /home/example/private-source.pdf"],
    }


def _page(
    page: int,
    method: str,
    chars: int,
    words: int,
    *,
    anchor: bool = False,
    extra: dict | None = None,
) -> dict:
    record = {
        "page": page,
        "method": method,
        "text_chars": chars,
        "word_count": words,
        "has_page_anchor": anchor,
        "text": "raw document paragraph",
        "ocr_text": "raw OCR dump",
        "caption": "source caption text",
        "table_text": "table cell text",
    }
    if extra:
        record.update(extra)
    return record


def _scan_for_leak(node, path: str = "") -> str | None:
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in SECRET_KEY_NAMES:
                return f"{path}.{key} (secret-like field name)"
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


def test_completed_all_embedded_text_pdf_source() -> None:
    report = build_source_coverage_report(_metadata([
        _pdf_source([
            _page(1, "embedded_text", 80, 12, anchor=True),
            _page(2, "embedded_text", 42, 6, anchor=True),
        ])
    ]))
    summary = report["summary"]
    check("embedded/status completed", report["status"] == "completed", str(report))
    check("embedded/source complete", report["sources"][0]["status"] == "complete", str(report["sources"]))
    check("embedded/pdf source count", summary["pdf_source_count"] == 1, str(summary))
    check("embedded/total pages", summary["total_pages"] == 2, str(summary))
    check("embedded/covered pages", summary["covered_pages"] == 2, str(summary))
    check("embedded/page method count", summary["embedded_text_pages"] == 2, str(summary))
    check("embedded/anchor count", summary["anchor_pages"] == 2, str(summary))


def test_mixed_embedded_text_and_ocr_source() -> None:
    report = build_source_coverage_report(_metadata([
        _pdf_source([
            _page(1, "embedded_text", 120, 18, anchor=True),
            _page(2, "ocr", 55, 9, anchor=False),
        ])
    ]))
    summary = report["summary"]
    check("mixed/status completed", report["status"] == "completed", str(report))
    check("mixed/embedded count", summary["embedded_text_pages"] == 1, str(summary))
    check("mixed/ocr count", summary["ocr_pages"] == 1, str(summary))
    check("mixed/covered count", summary["covered_pages"] == 2, str(summary))


def test_partial_coverage_with_blank_pages() -> None:
    report = build_source_coverage_report(_metadata([
        _pdf_source([
            _page(1, "embedded_text", 70, 10, anchor=True),
            _page(2, "none", 0, 0, anchor=False),
            _page(3, "embedded_text", 0, 0, anchor=False),
        ])
    ]))
    source = report["sources"][0]
    check("partial/top status", report["status"] == "partial", str(report))
    check("partial/source status", source["status"] == "partial", str(source))
    check("partial/covered pages", source["covered_page_count"] == 1, str(source))
    check("partial/blank count", source["empty_or_unreadable_page_count"] == 2, str(source))


def test_unreadable_source() -> None:
    report = build_source_coverage_report(_metadata([
        _pdf_source([
            _page(1, "none", 0, 0),
            _page(2, "none", 0, 0),
        ])
    ]))
    check("unreadable/source status", report["sources"][0]["status"] == "unreadable", str(report))
    check("unreadable/summary count", report["summary"]["unreadable_source_count"] == 1, str(report["summary"]))


def test_skipped_extraction_metadata() -> None:
    report = build_source_coverage_report({
        "version": 2,
        "kind": "extraction_metadata",
        "status": "skipped",
        "reason": "metadata_unavailable",
        "safe_message": "Extraction metadata could not be collected.",
    })
    check("skipped/status", report["status"] == "skipped", str(report))
    check("skipped/warning token", report["warnings"] == ["metadata_skipped"], str(report["warnings"]))
    check("skipped/no sources", report["sources"] == [], str(report["sources"]))


def test_malformed_metadata_degrades_safely() -> None:
    for bad in [None, 123, "bad", {"kind": "other"}, {"kind": "extraction_metadata", "status": "completed"}]:
        report = build_source_coverage_report(bad)  # type: ignore[arg-type]
        ok = report["status"] == "skipped" and report["sources"] == []
        check(f"malformed metadata degrades: {type(bad).__name__}", ok, str(report))


def test_input_filename_path_title_and_text_are_not_emitted() -> None:
    report = build_source_coverage_report(_metadata([
        _pdf_source([
            _page(1, "embedded_text", 80, 12, anchor=True, extra={
                "api_key": "sk_sourcecoveragecanary1234567890",
                "url": "https://example.invalid/private-source.pdf",
                "argv": "--model /home/example/model.gguf --mmproj /home/example/mmproj.gguf",
                "socket": "/tmp/private.sock",
                "image_ref": "assets/secret.png",
                "bytes": "data:image/png;base64,AAAA",
            }),
        ])
    ]))
    text = json.dumps(report, sort_keys=True)
    for forbidden in FORBIDDEN_CANARIES + ["/home/example", "https://", "data:image", "--model"]:
        check(f"no forbidden input emitted: {forbidden}", forbidden not in text, text)
    check("serialized report no-leak scan", _scan_for_leak(report) is None, _scan_for_leak(report) or "")


def test_hostile_visual_manifest_fields_are_not_emitted() -> None:
    report = build_source_coverage_report(
        _metadata([_pdf_source([_page(1, "embedded_text", 60, 8)])]),
        visual_manifest={
            "version": 1,
            "kind": "visual_assets_manifest",
            "assets": [
                {
                    "source_page": 1,
                    "asset_id": "sk_sourcecoveragecanary1234567890",
                    "caption": "source caption text",
                    "image_ref": "assets/secret.png",
                    "source_provider": "https://provider.invalid",
                    "bbox": [1, 2, 3, 4],
                }
            ],
        },
    )
    text = json.dumps(report, sort_keys=True)
    check("visual/count only", report["summary"]["visual_candidate_pages"] == 1, str(report["summary"]))
    check("visual hostile fields not emitted", _scan_for_leak(report) is None, text)


def test_visual_candidate_page_count_unique_positive_integers_only() -> None:
    report = build_source_coverage_report(
        _metadata([_pdf_source([
            _page(1, "embedded_text", 60, 8),
            _page(2, "embedded_text", 60, 8),
            _page(3, "embedded_text", 60, 8),
        ])]),
        visual_manifest={
            "assets": [
                {"source_page": 1},
                {"source_page": 1},
                {"source_page": 2},
                {"source_page": 0},
                {"source_page": -1},
                {"source_page": "3"},
                {"source_page": True},
            ]
        },
    )
    check("visual unique positive integer count", report["summary"]["visual_candidate_pages"] == 2, str(report))
    check("visual source-level count", report["sources"][0]["visual_candidate_page_count"] == 2, str(report))
    check("invalid visual pages warn", "visual_page_out_of_range" in report["warnings"], str(report["warnings"]))


def test_invalid_visual_pages_ignored_with_closed_warning() -> None:
    report = build_source_coverage_report(
        _metadata([_pdf_source([_page(1, "embedded_text", 60, 8)], page_count=1)]),
        visual_manifest={"assets": [{"source_page": 2}, {"source_page": None}, "bad"]},
    )
    check("invalid visual ignored", report["summary"]["visual_candidate_pages"] == 0, str(report))
    check("visual out-of-range warning", "visual_page_out_of_range" in report["warnings"], str(report["warnings"]))
    check("visual malformed warning", "visual_manifest_malformed" in report["warnings"], str(report["warnings"]))


def test_summary_counts_match_per_source_counts() -> None:
    report = build_source_coverage_report(
        _metadata([
            _pdf_source([
                _page(1, "embedded_text", 40, 5, anchor=True),
                _page(2, "ocr", 30, 4),
            ]),
            _pdf_source([
                _page(1, "none", 0, 0),
            ]),
        ]),
        visual_manifest={"assets": [{"source_index": 1, "source_page": 1}, {"source_index": 2, "source_page": 1}]},
    )
    fields = [
        ("total_pages", "page_count"),
        ("covered_pages", "covered_page_count"),
        ("embedded_text_pages", "embedded_text_page_count"),
        ("ocr_pages", "ocr_page_count"),
        ("empty_or_unreadable_pages", "empty_or_unreadable_page_count"),
        ("anchor_pages", "anchor_page_count"),
    ]
    for summary_key, source_key in fields:
        expected = sum(source[source_key] for source in report["sources"])
        check(f"summary matches sources: {summary_key}", report["summary"][summary_key] == expected, str(report))
    expected_visual = sum(source["visual_candidate_page_count"] for source in report["sources"])
    check("summary matches sources: visual_candidate_pages", report["summary"]["visual_candidate_pages"] == expected_visual, str(report))


def test_unknown_page_methods_do_not_crash_and_warn() -> None:
    report = build_source_coverage_report(_metadata([
        _pdf_source([_page(1, "hybrid_ai_magic", 0, 0)])
    ]))
    check("unknown method warning", report["sources"][0]["warnings"] == ["unknown_method"], str(report))
    check("unknown method unreadable", report["sources"][0]["status"] == "unreadable", str(report))


def test_report_deterministic_across_repeated_calls() -> None:
    metadata = _metadata([_pdf_source([_page(1, "embedded_text", 50, 6)])])
    visual = {"assets": [{"source_page": 1}]}
    first = build_source_coverage_report(metadata, visual_manifest=visual)
    second = build_source_coverage_report(metadata, visual_manifest=visual)
    check("deterministic repeated calls", first == second, f"{first} != {second}")


def test_builder_is_pure_stdlib_and_no_forbidden_imports() -> None:
    import pipeline.source_coverage_report as mod

    source_text = Path(mod.__file__).read_text(encoding="utf-8")
    import_lines = [
        line.strip()
        for line in source_text.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    forbidden = [
        "fitz",
        "pytesseract",
        "fastapi",
        "mistral",
        "gemini",
        "chandra",
        "provider",
        "renderer",
        "visual_assets_manifest",
        "job_manager",
        "run_llm_job",
    ]
    offenders = [token for token in forbidden if any(token in line for line in import_lines)]
    check("no forbidden imports in module source", not offenders, str(import_lines))
    importlib.reload(mod)
    loaded = [name for name in ("fitz", "pytesseract", "fastapi", "mistralai") if name in sys.modules]
    check("no forbidden modules loaded", not loaded, str(loaded))


def test_no_leak_sweep_over_serialized_report() -> None:
    report = build_source_coverage_report(
        _metadata([_pdf_source([_page(1, "embedded_text", 99, 14, anchor=True)])]),
        visual_manifest={"assets": [{"source_page": 1, "image_ref": "assets/secret.png"}]},
    )
    serialized = json.dumps(report, sort_keys=True)
    leak = _scan_for_leak(json.loads(serialized))
    check("serialized no-leak sweep", leak is None, leak or serialized)


def main() -> int:
    test_completed_all_embedded_text_pdf_source()
    test_mixed_embedded_text_and_ocr_source()
    test_partial_coverage_with_blank_pages()
    test_unreadable_source()
    test_skipped_extraction_metadata()
    test_malformed_metadata_degrades_safely()
    test_input_filename_path_title_and_text_are_not_emitted()
    test_hostile_visual_manifest_fields_are_not_emitted()
    test_visual_candidate_page_count_unique_positive_integers_only()
    test_invalid_visual_pages_ignored_with_closed_warning()
    test_summary_counts_match_per_source_counts()
    test_unknown_page_methods_do_not_crash_and_warn()
    test_report_deterministic_across_repeated_calls()
    test_builder_is_pure_stdlib_and_no_forbidden_imports()
    test_no_leak_sweep_over_serialized_report()
    total = PASS + FAIL
    print(f"\nSource coverage report tests: {PASS}/{total} PASS  {FAIL} FAIL")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
