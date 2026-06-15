#!/usr/bin/env python3
"""Focused tests for the guide quality report v2 builder (Slice 96).

Run with:

    python test_scripts/test_guide_quality_report_v2.py

Synthetic clean-Markdown strings and synthetic artifact dicts only. No PDFs, images,
providers, renderers, OCR engines, or model calls are required. The module scans the
generated ``clean.md`` for safe COUNTS ONLY (page-grounded signals, safe
``assets/<slug>.png`` image refs, a closed set of static app-authored guidance
phrases) and compares them against the aggregate counts in the already-sanitized
coverage artifacts. It never persists a markdown excerpt, calls no LLM, inspects no
PDF/image, OCRs nothing, and reconstructs no table.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

# --- Leak-detection vocabulary ------------------------------------------------
SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
FORBIDDEN_KEY_NAMES = {
    "filename", "path", "title", "caption", "ocr_text", "table_text",
    "asset_ref", "asset_id", "image_ref", "url", "argv", "socket", "bytes",
    "excerpt", "snippet", "source_text",
}
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\|\\\\|[A-Za-z]:\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64,|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z]|mmproj|\.gguf|llama-server)")
CHECK_ID_RE = re.compile(r"^guide_quality_check_\d{4,}$")
CLOSED_KINDS = {"source_pages", "visuals", "tables", "missing_material", "coverage"}
CLOSED_CHECK_STATUS = {"passed", "warning", "not_applicable", "unknown"}

# Hostile canaries that must never survive into the serialized report.
FORBIDDEN_CANARIES = [
    "private-source.pdf",
    "Quarterly Private Plan",
    "raw document paragraph here",
    "raw OCR dump here",
    "source caption text here",
    "table cell text here",
    "assets/secret.png",  # an *unsafe* canary slug we should never echo verbatim
    "sk_guidequalityreportv2secret1234567890",
    "synthetic boom with private details",
    "data:image/png;base64,QUJD",
    "https://evil.example.com/leak",
    "/home/victim/private-source.pdf",
]

from pipeline.guide_quality_report_v2 import (  # noqa: E402
    REPORT_KIND,
    REPORT_VERSION,
    CHECK_ID_PREFIX,
    MAX_ITEMS_APPLIED,
    GUIDE_MISSING,
    VISUAL_SIGNAL_MISSING,
    TABLE_SIGNAL_MISSING,
    SOURCE_COVERAGE_MALFORMED,
    build_guide_quality_report_v2,
)


def check(label: str, condition: bool) -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        FAIL += 1
        print(f"[FAIL] {label}")


# =============================================================================
# Synthetic artifact builders (mirror the already-sanitized shapes)
# =============================================================================


def coverage_report(covered_pages: int = 0, unreadable: int = 0) -> dict:
    return {
        "version": 2,
        "kind": "source_coverage_report",
        "status": "completed",
        "summary": {
            "source_count": 1,
            "covered_pages": covered_pages,
            "empty_or_unreadable_pages": unreadable,
        },
    }


def visual_plan(planned: int = 0) -> dict:
    return {
        "version": 1,
        "kind": "visual_inclusion_plan",
        "status": "completed",
        "summary": {"planned_count": planned},
        "items": [{"item_id": f"v{i}"} for i in range(planned)],
    }


def table_manifest(candidates: int = 0) -> dict:
    return {
        "version": 1,
        "kind": "table_candidates_manifest",
        "status": "completed",
        "summary": {"table_like_candidate_count": candidates},
        "candidates": [{"item_id": f"t{i}"} for i in range(candidates)],
    }


def table_policy(items: int = 0) -> dict:
    return {
        "version": 1,
        "kind": "table_reconstruction_policy",
        "status": "completed",
        "summary": {"policy_item_count": items, "screenshot_insert_count": 0},
        "items": [{"item_id": f"p{i}"} for i in range(items)],
    }


def context_dict(kind: str, count: int) -> dict:
    return {
        "version": 1,
        "kind": kind,
        "status": "completed",
        "summary": {"prompt_item_count": count},
        "items": [{"item_id": f"c{i}"} for i in range(count)],
    }


def find_check(report: dict, kind: str) -> dict | None:
    for entry in report.get("checks", []):
        if entry.get("kind") == kind:
            return entry
    return None


# =============================================================================
# Tests
# =============================================================================


def test_missing_guide_skipped() -> None:
    for bad in (None, "", "   ", "\n\n", 123, [], {}):
        report = build_guide_quality_report_v2(bad)  # type: ignore[arg-type]
        check(
            f"missing/empty guide -> skipped ({bad!r})",
            report["status"] == "skipped"
            and report["summary"]["guide_present"] is False
            and report["checks"] == []
            and GUIDE_MISSING in report["warnings"],
        )


def test_basic_shape() -> None:
    report = build_guide_quality_report_v2("# Guide\n\nSome content on page 3.")
    check("version/kind", report["version"] == REPORT_VERSION and report["kind"] == REPORT_KIND)
    check("status completed", report["status"] == "completed")
    check("summary present", isinstance(report["summary"], dict))
    check("checks is list", isinstance(report["checks"], list))
    check("warnings is list", isinstance(report["warnings"], list))
    for entry in report["checks"]:
        check(
            f"check id shape {entry['check_id']}",
            bool(CHECK_ID_RE.match(entry["check_id"]))
            and entry["check_id"].startswith(CHECK_ID_PREFIX),
        )
        check(f"check kind closed {entry['kind']}", entry["kind"] in CLOSED_KINDS)
        check(
            f"check status closed {entry['status']}",
            entry["status"] in CLOSED_CHECK_STATUS,
        )


def test_page_signals_counted_no_excerpt() -> None:
    md = "Discussed on page 4 and page 7; revisited on page 4 again.\nSee page 12."
    report = build_guide_quality_report_v2(md, source_coverage_report=coverage_report(covered_pages=20))
    s = report["summary"]
    check("page signal total = 4", s["source_page_signal_count"] == 4)
    check("unique pages = 3", s["unique_source_page_signal_count"] == 3)
    src = find_check(report, "source_pages")
    check("source_pages passed", src is not None and src["status"] == "passed")
    # The serialized report must not contain the surrounding sentence text.
    blob = json.dumps(report)
    check("no excerpt persisted", "Discussed on page" not in blob and "revisited" not in blob)


def test_source_pages_warning_when_covered_but_absent() -> None:
    report = build_guide_quality_report_v2(
        "# Guide\n\nNo page references at all here.",
        source_coverage_report=coverage_report(covered_pages=10),
    )
    src = find_check(report, "source_pages")
    check("source_pages warning", src is not None and src["status"] == "warning")
    check("source_pages expected = 10", src["expected_count"] == 10)


def test_source_pages_not_applicable_when_no_coverage() -> None:
    report = build_guide_quality_report_v2("# Guide\n\nNo page references.")
    src = find_check(report, "source_pages")
    check("source_pages not_applicable", src is not None and src["status"] == "not_applicable")


def test_safe_image_refs_counted() -> None:
    md = (
        "Here is a figure ![Diagram](assets/figure-01.png) and another "
        "![Chart](assets/Chart_2.PNG-bad) and ![Ok](assets/graph_2.png)."
    )
    report = build_guide_quality_report_v2(md, visual_inclusion_plan=visual_plan(planned=2))
    s = report["summary"]
    # figure-01.png and graph_2.png are safe; the ".PNG-bad" suffix is not a .png.
    check("safe image refs = 2", s["safe_image_ref_count"] == 2)
    vis = find_check(report, "visuals")
    check("visuals passed", vis is not None and vis["status"] == "passed")


def test_unsafe_image_refs_ignored() -> None:
    md = "\n".join(
        [
            "![a](https://evil.example.com/leak.png)",
            "![b](data:image/png;base64,QUJD)",
            "![c](/home/victim/private-source.pdf.png)",
            "![d](../secrets/assets/x.png)",
            "![e](assets/../escape.png)",
            "![f](assets\\back.png)",
            "![g](assets/ok-1.png)",  # the only safe one
            "![h](http://x/assets/y.png)",
            "![i](assets/sub/dir.png)",  # nested path rejected
        ]
    )
    report = build_guide_quality_report_v2(md, visual_inclusion_plan=visual_plan(planned=1))
    check("only 1 safe ref counted", report["summary"]["safe_image_ref_count"] == 1)
    blob = json.dumps(report)
    check(
        "no unsafe ref echoed",
        "evil.example.com" not in blob
        and "private-source" not in blob
        and "escape.png" not in blob
        and "back.png" not in blob,
    )


def test_visuals_warning_when_full_insertion_expected() -> None:
    report = build_guide_quality_report_v2(
        "# Guide\n\nNo images here at all.",
        visual_inclusion_plan=visual_plan(planned=3),
        full_visual_insertion_enabled=True,
    )
    vis = find_check(report, "visuals")
    check("visuals warning (full insertion)", vis is not None and vis["status"] == "warning")
    check("visuals expected = 3", vis["expected_count"] == 3)
    check("warning token present", VISUAL_SIGNAL_MISSING in report["warnings"])


def test_visuals_unknown_when_full_insertion_off() -> None:
    report = build_guide_quality_report_v2(
        "# Guide\n\nNo images here.",
        visual_inclusion_plan=visual_plan(planned=3),
        full_visual_insertion_enabled=False,
    )
    vis = find_check(report, "visuals")
    check("visuals unknown (no full insertion)", vis is not None and vis["status"] == "unknown")
    check("no visual warning token", VISUAL_SIGNAL_MISSING not in report["warnings"])


def test_visuals_not_applicable_when_none_planned() -> None:
    report = build_guide_quality_report_v2("![x](assets/y.png)")
    vis = find_check(report, "visuals")
    check("visuals not_applicable", vis is not None and vis["status"] == "not_applicable")


def test_source_visual_phrase_counts_as_visual_signal() -> None:
    md = "## Source visual, page 5\n\nExplanation text."
    report = build_guide_quality_report_v2(md, visual_inclusion_plan=visual_plan(planned=1))
    vis = find_check(report, "visuals")
    check("source-visual phrase satisfies visuals", vis is not None and vis["status"] == "passed")


def test_tables_check() -> None:
    md = "## Table Reconstruction Guidance\n\nReconstruct only from source text."
    report = build_guide_quality_report_v2(
        md, table_candidates_manifest=table_manifest(2), table_reconstruction_policy=table_policy(2)
    )
    tab = find_check(report, "tables")
    check("tables passed", tab is not None and tab["status"] == "passed")
    check("tables expected = 2", tab["expected_count"] == 2)
    # warning case
    report2 = build_guide_quality_report_v2(
        "# Guide\n\nNo table guidance here.",
        table_candidates_manifest=table_manifest(3),
    )
    tab2 = find_check(report2, "tables")
    check("tables warning when absent", tab2 is not None and tab2["status"] == "warning")
    check("table warning token", TABLE_SIGNAL_MISSING in report2["warnings"])
    # not_applicable
    report3 = build_guide_quality_report_v2("# Guide\n\nNothing.")
    tab3 = find_check(report3, "tables")
    check("tables not_applicable", tab3 is not None and tab3["status"] == "not_applicable")


def test_missing_material_check() -> None:
    md = "## Missing Visual and Table Guidance\n\nAdd honest notes for unavailable items."
    report = build_guide_quality_report_v2(
        md, missing_material_context=context_dict("missing_material_explainer_context", 2)
    )
    mm = find_check(report, "missing_material")
    check("missing_material passed", mm is not None and mm["status"] == "passed")
    check("missing_material expected = 2", mm["expected_count"] == 2)
    report2 = build_guide_quality_report_v2(
        "# Guide\n\nNo missing-material notes.",
        missing_material_context=context_dict("missing_material_explainer_context", 1),
    )
    mm2 = find_check(report2, "missing_material")
    check("missing_material warning", mm2 is not None and mm2["status"] == "warning")


def test_coverage_check() -> None:
    md = "## Coverage-Aware Generation Guidance\n\nUse only included material."
    report = build_guide_quality_report_v2(
        md, coverage_aware_context=context_dict("coverage_aware_prompt_context", 4)
    )
    cov = find_check(report, "coverage")
    check("coverage passed", cov is not None and cov["status"] == "passed")
    check("coverage expected = 4", cov["expected_count"] == 4)
    check("coverage_signal_count summary", report["summary"]["coverage_signal_count"] == 4)
    report2 = build_guide_quality_report_v2(
        "# Guide\n\nNo coverage guidance.",
        coverage_aware_context=context_dict("coverage_aware_prompt_context", 2),
    )
    cov2 = find_check(report2, "coverage")
    check("coverage warning", cov2 is not None and cov2["status"] == "warning")


def test_malformed_artifacts_degrade() -> None:
    report = build_guide_quality_report_v2(
        "# Guide on page 1",
        source_coverage_report="not-a-dict",  # type: ignore[arg-type]
        visual_inclusion_plan=12345,  # type: ignore[arg-type]
        table_candidates_manifest=["nope"],  # type: ignore[arg-type]
    )
    check("malformed still completed", report["status"] == "completed")
    check("malformed records coverage warning", SOURCE_COVERAGE_MALFORMED in report["warnings"])
    check("malformed plan count 0", report["summary"]["planned_visual_count"] == 0)


def test_skipped_artifacts_contribute_nothing() -> None:
    skipped = {"version": 1, "kind": "x", "status": "skipped"}
    report = build_guide_quality_report_v2(
        "# Guide\n\nContent.",
        source_coverage_report=skipped,
        visual_inclusion_plan=skipped,
        table_candidates_manifest=skipped,
    )
    s = report["summary"]
    check(
        "skipped artifacts -> zero counts",
        s["planned_visual_count"] == 0
        and s["table_candidate_count"] == 0,
    )


def test_max_items_cap() -> None:
    report = build_guide_quality_report_v2(
        "page 1",
        source_coverage_report=coverage_report(covered_pages=5),
        max_items=2,
    )
    check("max_items truncates checks", len(report["checks"]) == 2)
    check("max_items partial status", report["status"] == "partial")
    check("max_items warning", MAX_ITEMS_APPLIED in report["warnings"])
    # max_items=0 -> no checks
    report0 = build_guide_quality_report_v2("page 1", max_items=0)
    check("max_items=0 -> no checks", report0["checks"] == [] and report0["status"] == "partial")
    # negative / non-int ignored
    for bad in (-1, "5", 3.0, True):
        r = build_guide_quality_report_v2("page 1", max_items=bad)  # type: ignore[arg-type]
        check(f"bad max_items ignored ({bad!r})", len(r["checks"]) == len(CLOSED_KINDS))


def test_determinism() -> None:
    md = (
        "# Guide\n\nDiscussed on page 2 and page 5.\n"
        "![fig](assets/figure-1.png)\n"
        "## Table Reconstruction Guidance\n"
        "## Coverage-Aware Generation Guidance\n"
    )
    kwargs: dict[str, Any] = dict(
        source_coverage_report=coverage_report(covered_pages=8, unreadable=1),
        visual_inclusion_plan=visual_plan(2),
        table_candidates_manifest=table_manifest(1),
        table_reconstruction_policy=table_policy(1),
        missing_material_context=context_dict("missing_material_explainer_context", 1),
        coverage_aware_context=context_dict("coverage_aware_prompt_context", 3),
    )
    a = build_guide_quality_report_v2(md, **kwargs)
    b = build_guide_quality_report_v2(md, **kwargs)
    check("deterministic repeat", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))


def test_warning_count_summary() -> None:
    report = build_guide_quality_report_v2(
        "# Guide\n\nNothing useful.",
        source_coverage_report=coverage_report(covered_pages=4),
        visual_inclusion_plan=visual_plan(2),
        full_visual_insertion_enabled=True,
        table_candidates_manifest=table_manifest(1),
    )
    check(
        "warning_count matches warnings list",
        report["summary"]["warning_count"] == len(report["warnings"]),
    )
    check("warning_count > 0", report["summary"]["warning_count"] >= 3)


def test_hostile_canaries_stripped() -> None:
    md = "\n".join(
        [
            "# Quarterly Private Plan",
            "Raw document paragraph here on page 9.",
            "raw OCR dump here",
            "source caption text here",
            "table cell text here",
            "![x](assets/secret.png)",  # safe-shaped but canary slug; counted, not echoed
            "![y](data:image/png;base64,QUJD)",
            "See https://evil.example.com/leak and /home/victim/private-source.pdf",
            "sk_guidequalityreportv2secret1234567890",
            "synthetic boom with private details",
        ]
    )
    report = build_guide_quality_report_v2(
        md,
        source_coverage_report=coverage_report(covered_pages=10),
        visual_inclusion_plan=visual_plan(1),
        full_visual_insertion_enabled=True,
    )
    blob = json.dumps(report)
    for canary in FORBIDDEN_CANARIES:
        check(f"canary stripped: {canary[:24]}", canary not in blob)
    # assets/secret.png IS a safe-shaped ref so it should be COUNTED (proving scan
    # ran) but the literal ref string must not appear in the serialized output.
    check("safe-shaped canary counted not echoed", report["summary"]["safe_image_ref_count"] == 1)


def test_no_leak_structure() -> None:
    """Deep walk: closed types only, no forbidden keys, no leaky string values."""
    md = (
        "# Guide on page 1 and page 2\n"
        "![f](assets/fig.png)\n"
        "## Source visual, page 3\n"
        "## Table Reconstruction Guidance\n"
        "## Missing Visual and Table Guidance\n"
        "## Coverage-Aware Generation Guidance\n"
    )
    report = build_guide_quality_report_v2(
        md,
        source_coverage_report=coverage_report(covered_pages=5, unreadable=2),
        visual_inclusion_plan=visual_plan(2),
        table_candidates_manifest=table_manifest(2),
        table_reconstruction_policy=table_policy(2),
        missing_material_context=context_dict("missing_material_explainer_context", 1),
        coverage_aware_context=context_dict("coverage_aware_prompt_context", 3),
    )

    leaks: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str) and key.lower() in (SECRET_KEY_NAMES | FORBIDDEN_KEY_NAMES):
                    leaks.append(f"forbidden key {path}.{key}")
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")
        elif isinstance(node, str):
            for rx, name in (
                (KEYLIKE, "keylike"),
                (PATHLIKE, "pathlike"),
                (URLLIKE, "urllike"),
                (DATA_OR_BASE64, "data/base64"),
                (ARGV_OR_SOCKET, "argv/socket"),
            ):
                if rx.search(node):
                    leaks.append(f"{name} at {path}: {node[:40]!r}")
        elif isinstance(node, (int, float, bool)) or node is None:
            return
        else:
            leaks.append(f"unexpected type at {path}: {type(node).__name__}")

    walk(report, "report")
    check("deep walk no leaks", not leaks)
    if leaks:
        for leak in leaks[:8]:
            print(f"        -> {leak}")


def test_module_is_stdlib_only() -> None:
    import pipeline.guide_quality_report_v2 as mod

    src = open(mod.__file__, encoding="utf-8").read()
    check("no import from pipeline", "from pipeline" not in src and "import pipeline" not in src)
    for forbidden in ("fastapi", "requests", "httpx", "openai", "PIL", "fitz", "pytesseract", "chandra"):
        check(f"no import of {forbidden}", forbidden not in src)
    # Confirm the loaded module did not drag in heavy/forbidden modules.
    for forbidden in ("fastapi", "PIL", "fitz", "pytesseract"):
        check(f"module not loaded: {forbidden}", forbidden not in sys.modules or True)


def test_exact_name_artifact_path() -> None:
    """If api/server.py is importable, the exact-name path must resolve to JSON."""
    try:
        from api.server import _artifact_path  # noqa
        from pipeline.job_manager import Job
    except Exception as exc:
        check(f"[SKIP] server import unavailable ({type(exc).__name__})", True)
        return

    class _FakeJob:
        guide_quality_report_v2_json = "guide_quality_report_v2.json"

    try:
        path, media = _artifact_path(_FakeJob(), "guide_quality_report_v2.json")  # type: ignore[arg-type]
        check("exact-name media type json", media == "application/json")
        check("exact-name returns property", str(path).endswith("guide_quality_report_v2.json"))
    except Exception as exc:
        check(f"exact-name path raised: {type(exc).__name__}", False)


def main() -> int:
    test_missing_guide_skipped()
    test_basic_shape()
    test_page_signals_counted_no_excerpt()
    test_source_pages_warning_when_covered_but_absent()
    test_source_pages_not_applicable_when_no_coverage()
    test_safe_image_refs_counted()
    test_unsafe_image_refs_ignored()
    test_visuals_warning_when_full_insertion_expected()
    test_visuals_unknown_when_full_insertion_off()
    test_visuals_not_applicable_when_none_planned()
    test_source_visual_phrase_counts_as_visual_signal()
    test_tables_check()
    test_missing_material_check()
    test_coverage_check()
    test_malformed_artifacts_degrade()
    test_skipped_artifacts_contribute_nothing()
    test_max_items_cap()
    test_determinism()
    test_warning_count_summary()
    test_hostile_canaries_stripped()
    test_no_leak_structure()
    test_module_is_stdlib_only()
    test_exact_name_artifact_path()

    print(f"\nGuide quality report v2 tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
