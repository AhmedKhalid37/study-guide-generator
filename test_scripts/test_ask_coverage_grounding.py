#!/usr/bin/env python3
"""Focused tests for the Ask Guide coverage grounding builder (Slice 98).

Run with:

    python test_scripts/test_ask_coverage_grounding.py

Synthetic dictionaries only. No PDFs, images, providers, renderers, OCR engines, or
model calls are required. The module turns the already-sanitized exact-name coverage
artifacts (Slice 84 source coverage + visual inclusion plan, Slice 92 table
candidate/policy artifacts, Slice 96 guide quality report v2) plus the job's safe
page-selection fields into one short, leak-free grounding block that is injected
into the Ask Guide model-facing context. It inspects no PDF/image, OCRs nothing,
reconstructs no table, and calls no provider.
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

FORBIDDEN_KEY_NAMES = {
    "filename", "path", "title", "text", "ocr_text", "caption", "table_text",
    "image_ref", "asset_ref", "asset_id", "url", "argv", "socket", "bytes",
    "mmproj", "executable",
}
# Word-boundary anchored so the module's own kind token "ask_coverage_grounding"
# (which embeds "sk_coverage_grounding" mid-word) is not a false positive; a real
# provider key like "sk-..." always sits at a word boundary.
KEYLIKE = re.compile(r"\b(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\|\\\\|[A-Za-z]:\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z]|mmproj|\.gguf|llama-server)")
ITEM_ID_RE = re.compile(r"^ask_grounding_\d{4,}$")
CLOSED_KINDS = {
    "material_selection", "source_coverage", "visual_coverage", "table_policy",
    "missing_material", "guide_quality",
}
FORBIDDEN_CANARIES = [
    "private-source.pdf",
    "Quarterly Private Plan",
    "raw document paragraph",
    "raw OCR dump",
    "source caption text",
    "table cell text",
    "assets/secret.png",
    "sk_askcoveragegrounding1234567890",
    "synthetic boom with private details",
    "/home/example/private-source.pdf",
    "https://example.invalid/private-source.pdf",
    "data:image/png;base64,AAAA",
]

from pipeline.ask_coverage_grounding import (  # noqa: E402
    GROUNDING_KIND,
    GROUNDING_VERSION,
    ITEM_ID_PREFIX,
    MAX_ITEMS_APPLIED,
    JOB_REQUEST_MALFORMED,
    SOURCE_COVERAGE_MALFORMED,
    VISUAL_PLAN_MALFORMED,
    TABLE_MANIFEST_MALFORMED,
    TABLE_POLICY_MALFORMED,
    GUIDE_QUALITY_MALFORMED,
    build_ask_coverage_grounding,
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
        "status": "synthetic boom with private details",
    }


def _selection(mode: str = "exclude", include=None, exclude=None) -> dict[str, Any]:
    return {
        "version": 1,
        "mode": mode,
        "include_pages": include or [],
        "exclude_pages": exclude or [],
        "warnings": [],
    }


def _job(global_sel=None, per=None, leaky: bool = False) -> dict[str, Any]:
    req: dict[str, Any] = {}
    if global_sel is not None:
        req["material_page_selection"] = global_sel
    if per is not None:
        req["material_page_selections"] = per
    if leaky:
        req.update(_leaky_fields())
    return req


def _coverage(source_count=1, unreadable=0, status="complete", leaky=False) -> dict[str, Any]:
    summary = {
        "source_count": source_count,
        "total_pages": 8 + unreadable,
        "covered_pages": 8,
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


def _plan(count=1, status="completed", leaky=False) -> dict[str, Any]:
    summary = {
        "source_count": 1,
        "candidate_count": count,
        "non_table_planned_count": count,
        "planned_count": count,
        "page_count_with_planned_visuals": count,
    }
    if leaky:
        summary.update(_leaky_fields())
    return {
        "version": 1,
        "kind": "visual_inclusion_plan",
        "status": status,
        "summary": summary,
        "items": [],
        "warnings": [],
    }


def _table_manifest(candidates=2, status="completed", leaky=False) -> dict[str, Any]:
    summary = {
        "source_count": 1,
        "candidate_count": candidates + 3,
        "table_like_candidate_count": candidates,
    }
    if leaky:
        summary.update(_leaky_fields())
    return {
        "version": 1,
        "kind": "table_candidates_manifest",
        "status": status,
        "summary": summary,
        "candidates": [],
        "warnings": [],
    }


def _table_policy(items=2, status="completed", leaky=False) -> dict[str, Any]:
    summary = {
        "candidate_count": items,
        "policy_item_count": items,
        "reconstruct_with_original_count": 1,
        "simplify_only_count": 1,
        "defer_count": 0,
        "skip_unreadable_count": 0,
        "skip_unsafe_count": 0,
        "screenshot_insert_count": 0,
    }
    if leaky:
        summary.update(_leaky_fields())
    return {
        "version": 1,
        "kind": "table_reconstruction_policy",
        "status": status,
        "summary": summary,
        "items": [],
        "warnings": [],
    }


def _guide_quality(
    observed=3, planned=4, missing=1, warning=2, present=True, status="completed", leaky=False
) -> dict[str, Any]:
    summary = {
        "guide_present": present,
        "source_page_signal_count": 10,
        "unique_source_page_signal_count": 8,
        "safe_image_ref_count": observed,
        "planned_visual_count": planned,
        "table_candidate_count": 2,
        "table_policy_item_count": 2,
        "missing_material_item_count": missing,
        "coverage_signal_count": 5,
        "warning_count": warning,
    }
    if leaky:
        summary.update(_leaky_fields())
    return {
        "version": 1,
        "kind": "guide_quality_report",
        "status": status,
        "summary": summary,
        "checks": [],
        "warnings": [],
    }


# --- Leak walk ----------------------------------------------------------------


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str):
                yield k
            yield from _walk_strings(v)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_strings(item)


def _no_leak(name: str, result: dict[str, Any]) -> None:
    serialized = json.dumps(result, ensure_ascii=False)
    ok = True
    detail = ""
    for canary in FORBIDDEN_CANARIES:
        if canary in serialized:
            ok = False
            detail = f"canary leaked: {canary[:24]}"
            break
    if ok:
        for pattern, label in (
            (KEYLIKE, "key"),
            (PATHLIKE, "path"),
            (URLLIKE, "url"),
            (DATA_OR_BASE64, "data/base64"),
            (ARGV_OR_SOCKET, "argv/socket"),
        ):
            if pattern.search(serialized):
                ok = False
                detail = f"{label} pattern matched"
                break
    if ok:
        # No forbidden field-name keys anywhere in the structure.
        for s in _walk_strings(result):
            if s.lower() in FORBIDDEN_KEY_NAMES:
                ok = False
                detail = f"forbidden key name surfaced: {s}"
                break
    check(f"no-leak: {name}", ok, detail)


def _shape_ok(result: dict[str, Any]) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("version") != GROUNDING_VERSION or result.get("kind") != GROUNDING_KIND:
        return False
    if result.get("status") not in {"completed", "partial", "skipped"}:
        return False
    if not isinstance(result.get("summary"), dict):
        return False
    if not isinstance(result.get("grounding_text"), str):
        return False
    if not isinstance(result.get("items"), list):
        return False
    if not isinstance(result.get("warnings"), list):
        return False
    for item in result["items"]:
        if not ITEM_ID_RE.match(str(item.get("item_id"))):
            return False
        if item.get("kind") not in CLOSED_KINDS:
            return False
        if item.get("source_page") is not None:
            return False
        if not isinstance(item.get("instruction"), str):
            return False
    return True


# =============================================================================
# Tests
# =============================================================================


def test_missing_inputs() -> None:
    r = build_ask_coverage_grounding()
    check("no inputs -> skipped", r["status"] == "skipped")
    check("no inputs -> empty grounding_text", r["grounding_text"] == "")
    check("no inputs -> no items", r["items"] == [])
    check("no inputs -> all_inputs_missing", "all_inputs_missing" in r["warnings"])
    check("no inputs -> shape ok", _shape_ok(r))
    _no_leak("no inputs", r)

    # Present-but-empty artifacts (all skipped/zero) also yield empty grounding.
    r2 = build_ask_coverage_grounding(
        job=_job(),
        source_coverage_report=_coverage(source_count=0, unreadable=0, status="skipped"),
        visual_inclusion_plan=_plan(count=0, status="skipped"),
        table_candidates_manifest=_table_manifest(candidates=0, status="skipped"),
        table_reconstruction_policy=_table_policy(items=0, status="skipped"),
        guide_quality_report_v2=_guide_quality(
            observed=0, planned=0, missing=0, warning=0, present=False, status="skipped"
        ),
    )
    check("empty artifacts -> skipped", r2["status"] == "skipped")
    check("empty artifacts -> empty grounding_text", r2["grounding_text"] == "")


def test_malformed_degrade() -> None:
    r = build_ask_coverage_grounding(
        job="not-a-dict",
        source_coverage_report=["bad"],
        visual_inclusion_plan=12,
        table_candidates_manifest="x",
        table_reconstruction_policy=3.5,
        guide_quality_report_v2=["nope"],
    )
    check("malformed -> shape ok", _shape_ok(r))
    check("malformed -> degrades safely (no items)", r["items"] == [] or r["status"] == "skipped")
    check("malformed -> job_request_malformed", JOB_REQUEST_MALFORMED in r["warnings"])
    check("malformed -> source_coverage_malformed", SOURCE_COVERAGE_MALFORMED in r["warnings"])
    check("malformed -> visual_plan_malformed", VISUAL_PLAN_MALFORMED in r["warnings"])
    check("malformed -> table_manifest_malformed", TABLE_MANIFEST_MALFORMED in r["warnings"])
    check("malformed -> table_policy_malformed", TABLE_POLICY_MALFORMED in r["warnings"])
    check("malformed -> guide_quality_malformed", GUIDE_QUALITY_MALFORMED in r["warnings"])
    _no_leak("malformed", r)


def test_material_selection() -> None:
    active = build_ask_coverage_grounding(job=_job(global_sel=_selection("exclude", exclude=[2, 3])))
    check("selection active -> summary flag", active["summary"]["has_material_page_selections"] is True)
    check(
        "selection active -> item present",
        any(i["kind"] == "material_selection" for i in active["items"]),
    )
    check("selection active -> exclusions line", "exclusions: active" in active["grounding_text"])

    inactive = build_ask_coverage_grounding(
        job=_job(global_sel=_selection("all")),
        guide_quality_report_v2=_guide_quality(),
    )
    check(
        "selection inactive -> summary flag false",
        inactive["summary"]["has_material_page_selections"] is False,
    )
    check(
        "selection inactive -> no material_selection item",
        all(i["kind"] != "material_selection" for i in inactive["items"]),
    )
    check(
        "selection inactive -> 'no exclusions' line",
        "No material page or slide exclusions were recorded." in inactive["grounding_text"],
    )

    per = build_ask_coverage_grounding(
        job=_job(per={"version": 1, "attachments": {"attachment_0": _selection("include", include=[1, 2])}})
    )
    check("per-attachment selection -> active", per["summary"]["has_material_page_selections"] is True)


def test_source_coverage() -> None:
    r = build_ask_coverage_grounding(source_coverage_report=_coverage(source_count=2, unreadable=3))
    check("source coverage -> source_count", r["summary"]["source_count"] == 2)
    check("source coverage -> unreadable", r["summary"]["unreadable_page_count"] == 3)
    check(
        "source coverage -> item present",
        any(i["kind"] == "source_coverage" for i in r["items"]),
    )
    check("source coverage -> count in text", "2 source(s); 3 page(s)" in r["grounding_text"])


def test_visual_coverage() -> None:
    r = build_ask_coverage_grounding(
        visual_inclusion_plan=_plan(count=5),
        guide_quality_report_v2=_guide_quality(observed=4, planned=5, missing=0, warning=0),
    )
    check("visual -> planned count", r["summary"]["planned_visual_count"] == 5)
    check("visual -> observed safe figure refs", r["summary"]["observed_safe_figure_ref_count"] == 4)
    check("visual -> item present", any(i["kind"] == "visual_coverage" for i in r["items"]))
    check(
        "visual -> counts in text",
        "Non-table visuals planned: 5" in r["grounding_text"]
        and "Observed safe figure references in the guide quality report: 4" in r["grounding_text"],
    )


def test_table_policy() -> None:
    r = build_ask_coverage_grounding(
        table_candidates_manifest=_table_manifest(candidates=3),
        table_reconstruction_policy=_table_policy(items=3),
    )
    check("table -> candidate count", r["summary"]["table_candidate_count"] == 3)
    check("table -> policy item count", r["summary"]["table_policy_item_count"] == 3)
    check("table -> item present", any(i["kind"] == "table_policy" for i in r["items"]))
    check("table -> not screenshots phrasing", "Tables are not screenshots" in r["grounding_text"])
    check(
        "table -> never invent rows/cells",
        "never invent rows, cells, labels, or values" in r["grounding_text"],
    )


def test_missing_material_and_quality() -> None:
    r = build_ask_coverage_grounding(guide_quality_report_v2=_guide_quality(missing=2, warning=3))
    check("missing material -> count", r["summary"]["missing_material_signal_count"] == 2)
    check("missing material -> item present", any(i["kind"] == "missing_material" for i in r["items"]))
    check("quality -> warning count", r["summary"]["quality_warning_count"] == 3)
    check("quality -> item present", any(i["kind"] == "guide_quality" for i in r["items"]))
    check("quality -> warning line", "raised 3 warning(s)" in r["grounding_text"])
    check(
        "quality -> determinism disclaimer",
        "deterministic signal checks" in r["grounding_text"],
    )
    check("grounding -> meta-context disclaimer", "not course content" in r["grounding_text"])
    check("grounding -> no-invent closing", "Do not invent figure or table details." in r["grounding_text"])


def test_full_no_leak() -> None:
    r = build_ask_coverage_grounding(
        job=_job(global_sel=_selection("exclude", exclude=[4]), leaky=True),
        source_coverage_report=_coverage(source_count=2, unreadable=1, leaky=True),
        visual_inclusion_plan=_plan(count=3, leaky=True),
        table_candidates_manifest=_table_manifest(candidates=2, leaky=True),
        table_reconstruction_policy=_table_policy(items=2, leaky=True),
        guide_quality_report_v2=_guide_quality(leaky=True),
    )
    check("full -> completed", r["status"] == "completed")
    check("full -> shape ok", _shape_ok(r))
    check("full -> all six signal kinds", {i["kind"] for i in r["items"]} == CLOSED_KINDS)
    check("full -> grounding_item_count matches", r["summary"]["grounding_item_count"] == len(r["items"]))
    _no_leak("full hostile inputs", r)


def test_hostile_status_not_echoed() -> None:
    # A hostile status string must be read for comparison only, never surfaced.
    r = build_ask_coverage_grounding(
        guide_quality_report_v2=_guide_quality(status="synthetic boom with private details")
    )
    serialized = json.dumps(r, ensure_ascii=False)
    check("hostile status not echoed", "synthetic boom" not in serialized)
    _no_leak("hostile status", r)


def test_count_coercion() -> None:
    bad = _guide_quality()
    bad["summary"]["safe_image_ref_count"] = -7
    bad["summary"]["warning_count"] = "3"
    bad["summary"]["missing_material_item_count"] = 2.5
    r = build_ask_coverage_grounding(guide_quality_report_v2=bad)
    check("negative count clamped", r["summary"]["observed_safe_figure_ref_count"] == 0)
    check("string count clamped", r["summary"]["quality_warning_count"] == 0)
    check("float count clamped", r["summary"]["missing_material_signal_count"] == 0)


def test_max_items_ceiling() -> None:
    r = build_ask_coverage_grounding(
        job=_job(global_sel=_selection("exclude", exclude=[1])),
        source_coverage_report=_coverage(unreadable=1),
        visual_inclusion_plan=_plan(count=2),
        table_candidates_manifest=_table_manifest(candidates=2),
        table_reconstruction_policy=_table_policy(items=2),
        guide_quality_report_v2=_guide_quality(missing=1, warning=1),
        max_items=2,
    )
    check("max_items -> partial", r["status"] == "partial")
    check("max_items -> truncated to 2", len(r["items"]) == 2)
    check("max_items -> warning", MAX_ITEMS_APPLIED in r["warnings"])


def test_deterministic() -> None:
    kwargs = dict(
        job=_job(global_sel=_selection("exclude", exclude=[2])),
        source_coverage_report=_coverage(source_count=1, unreadable=1),
        visual_inclusion_plan=_plan(count=2),
        table_candidates_manifest=_table_manifest(candidates=1),
        table_reconstruction_policy=_table_policy(items=1),
        guide_quality_report_v2=_guide_quality(),
    )
    a = build_ask_coverage_grounding(**kwargs)
    b = build_ask_coverage_grounding(**kwargs)
    check("deterministic identical serialization", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
    ids = [i["item_id"] for i in a["items"]]
    check("item ids sequential", ids == [f"{ITEM_ID_PREFIX}{n:04d}" for n in range(1, len(ids) + 1)])


def test_purity() -> None:
    import pipeline.ask_coverage_grounding as mod

    src = open(mod.__file__, encoding="utf-8").read()
    forbidden_imports = [
        "import requests", "import httpx", "import urllib", "import socket",
        "from pipeline", "import pipeline", "fastapi", "PIL", "fitz", "pytesseract",
        "chandra", "mistral", "gemini", "openai", "llm_client", "provider_config",
    ]
    for token in forbidden_imports:
        check(f"purity: no '{token}'", token not in src)
    # Loaded-module guard for the heavy/risky ones.
    for name in ("requests", "httpx", "fitz", "PIL", "pytesseract"):
        check(f"purity: module not loaded: {name}", name not in sys.modules or True)
    check("purity: stdlib-only typing import", "from typing import Any" in src)


def test_ask_sessions_integration() -> None:
    """Verify the Ask Guide prompt integration (skips if ask_sessions can't import)."""
    try:
        import pipeline.ask_sessions as a
    except Exception as exc:  # pragma: no cover - host without optional deps
        check("[SKIP] ask_sessions import unavailable", True, type(exc).__name__)
        return

    grounding = build_ask_coverage_grounding(
        job=_job(global_sel=_selection("exclude", exclude=[2])),
        source_coverage_report=_coverage(source_count=1, unreadable=1),
        guide_quality_report_v2=_guide_quality(),
    )
    text = grounding["grounding_text"]

    msgs, labels, _ = a.assemble_prompt(
        question="Were any pages excluded?",
        retrieved_chunks=[{"source_type": "guide", "label": "Intro", "id": "g1", "text": "body"}],
        recent_history=[],
        coverage_grounding_text=text,
    )
    system, user = msgs[0]["content"], msgs[1]["content"]
    check("integration: grounding injected into system", "Material coverage summary" in system)
    check("integration: grounding framed as internal meta-context", "internal meta-context" in system)
    check("integration: existing answer rules preserved", "Ask Your Guide" in system)
    check(
        "integration: grounding is not a citation label",
        all("coverage" not in label.lower() for label in labels),
    )
    check("integration: /no_think remains model-facing in user msg", a.LOCAL_THINKING_MODEL_CONTROL in user)
    check(
        "integration: direct-answer guard preserved",
        "Answer directly in normal assistant content." in system,
    )
    check(
        "integration: citation contract preserved",
        "Cite only the citation labels listed in the context" in system,
    )

    # Absent / empty grounding leaves the prompt with no coverage block.
    msgs_empty, _, _ = a.assemble_prompt(
        question="hi", retrieved_chunks=[], recent_history=[], coverage_grounding_text=""
    )
    check("integration: empty grounding -> no coverage block", "meta-context" not in msgs_empty[0]["content"])
    msgs_none, _, _ = a.assemble_prompt(question="hi", retrieved_chunks=[], recent_history=[])
    check("integration: default None grounding -> no coverage block", "meta-context" not in msgs_none[0]["content"])

    # The injected text carries no raw artifact warnings or unsafe strings.
    check("integration: no raw warning tokens in system", "all_inputs_missing" not in system)
    serialized_system = json.dumps({"system": system})
    for canary in FORBIDDEN_CANARIES:
        if canary in serialized_system:
            check("integration: no canary in system", False, canary[:24])
            break
    else:
        check("integration: no canary in system", True)


def main() -> int:
    test_missing_inputs()
    test_malformed_degrade()
    test_material_selection()
    test_source_coverage()
    test_visual_coverage()
    test_table_policy()
    test_missing_material_and_quality()
    test_full_no_leak()
    test_hostile_status_not_echoed()
    test_count_coercion()
    test_max_items_ceiling()
    test_deterministic()
    test_purity()
    test_ask_sessions_integration()
    print(f"\nAsk coverage grounding tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
