#!/usr/bin/env python3
"""Focused tests for the pure visual replacement planner core (Slice 48, roadmap V3).

Run with:

    python test_scripts/test_visual_replacement_planner.py

No external APIs and no PyMuPDF/Tesseract/llama.cpp/Mistral/Gemini/Chandra-runtime
or Local-Model-Manager dependency: the planner is a pure function of already-
sanitized ``visual_asset_scoring.json``-shaped score items (optionally cross-checked
against a ``visual_assets_manifest.json``-shaped manifest for presence only), so
these tests feed it tiny *handcrafted synthetic* records. No real model dumps,
private documents, screenshots, or local paths are used.
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

# Leak detectors — none of these may appear anywhere in planner output.
KEYLIKE = re.compile(r"(sk-|sk_|pk-|rk_)[A-Za-z0-9_\-]{12,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/root/|/tmp/|/opt/|C:\\|\\\\)")
URLLIKE = re.compile(r"https?://|file://|ftp://")
AUTHLIKE = re.compile(r"Authorization|Bearer\s+\S", re.IGNORECASE)
SOCKETLIKE = re.compile(r"\.sock\b")
ARGVLIKE = re.compile(r"(?<!\S)--[A-Za-z]")
BASE64URI = re.compile(r"data:[^;]+;base64,")
GGUFLIKE = re.compile(r"\.gguf\b|mmproj", re.IGNORECASE)

from pipeline.visual_replacement_planner import (  # noqa: E402
    ASSET_TYPES,
    CANDIDATE_ACTIONS,
    PLACEMENTS,
    PRIORITIES,
    REASONS,
    REPORT_KIND,
    REPORT_VERSION,
    SOURCE_PROVIDERS,
    WARNINGS,
    build_visual_replacement_plan,
    plan_visual_replacement_candidate,
    plan_visual_replacement_candidates,
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


def _is_json_safe(obj) -> bool:
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


def _item_keys() -> set:
    return {
        "asset_id", "source_page", "source_provider", "asset_type",
        "priority", "candidate_action", "placement", "reasons", "warnings",
    }


def _vocab_ok(item: dict) -> bool:
    return (
        item["priority"] in PRIORITIES
        and item["asset_type"] in ASSET_TYPES
        and item["source_provider"] in SOURCE_PROVIDERS
        and item["candidate_action"] in CANDIDATE_ACTIONS
        and item["placement"] in PLACEMENTS
        and all(r in REASONS for r in item["reasons"])
        and all(w in WARNINGS for w in item["warnings"])
    )


# --- Synthetic scoring-report-shaped fixtures (no real data) -----------------

def _score(asset_type: str, priority: str, *, asset_id: str = "page_0001_visual_01",
           source_page: int = 1, provider: str = "fitz_local") -> dict:
    return {
        "asset_id": asset_id,
        "source_page": source_page,
        "source_provider": provider,
        "asset_type": asset_type,
        "recommended_action": "unknown",
        "priority": priority,
        "include_score": 0.7,
        "reasons": ["asset_type_table"],
        "warnings": [],
    }


def _scoring_report(scores: list) -> dict:
    return {
        "version": 1,
        "kind": "visual_asset_scoring",
        "status": "completed",
        "source": "visual_assets_manifest.json",
        "scores": scores,
        "summary": {"asset_count": len(scores)},
        "warnings": [],
    }


# --- 1. High-priority visual figure types → include_as_figure ----------------

def test_include_as_figure() -> None:
    for atype in ("diagram", "extracted_figure", "figure", "image_region", "cropped_region"):
        item = plan_visual_replacement_candidate(_score(atype, "high", source_page=2))
        check(f"fig.keys[{atype}]", set(item) == _item_keys(), str(set(item)))
        check(f"fig.vocab[{atype}]", _vocab_ok(item))
        check(f"fig.action[{atype}]", item["candidate_action"] == "candidate_include_as_figure", item["candidate_action"])
        check(f"fig.placement[{atype}]", item["placement"] == "source_page_reference", item["placement"])
        check(f"fig.score_high[{atype}]", "score_high" in item["reasons"])
        check(f"fig.page[{atype}]", item["source_page"] == 2)
        check(f"fig.json_safe[{atype}]", _is_json_safe(item))


# --- 2. Medium-priority table → convert_to_table -----------------------------

def test_convert_to_table() -> None:
    for atype in ("table", "table_region"):
        item = plan_visual_replacement_candidate(_score(atype, "medium"))
        check(f"tbl.action[{atype}]", item["candidate_action"] == "candidate_convert_to_table", item["candidate_action"])
        check(f"tbl.reason[{atype}]", "asset_type_table" in item["reasons"])
        check(f"tbl.score_medium[{atype}]", "score_medium" in item["reasons"])
        check(f"tbl.placement[{atype}]", item["placement"] == "source_page_reference")
    # High-priority table also converts.
    high = plan_visual_replacement_candidate(_score("table", "high"))
    check("tbl.high_action", high["candidate_action"] == "candidate_convert_to_table")


# --- 3. Equation block (high/medium) → summarize_as_text ---------------------

def test_summarize_as_text() -> None:
    for prio in ("high", "medium"):
        item = plan_visual_replacement_candidate(_score("equation_block", prio))
        check(f"eq.action[{prio}]", item["candidate_action"] == "candidate_summarize_as_text", item["candidate_action"])
        check(f"eq.reason[{prio}]", "asset_type_equation" in item["reasons"])
    # A legitimately-unknown visual block (token, not coerced) → summarize when high/medium.
    blk = plan_visual_replacement_candidate(_score("unknown_region", "high"))
    check("eq.unknown_block_summarize", blk["candidate_action"] == "candidate_summarize_as_text", blk["candidate_action"])
    check("eq.unknown_block_reason", "unknown_asset_type" in blk["reasons"])


# --- 4. Low-priority / page signal → review_only -----------------------------

def test_review_only() -> None:
    item = plan_visual_replacement_candidate(_score("page_visual_signal", "low"))
    check("rev.action", item["candidate_action"] == "review_only", item["candidate_action"])
    check("rev.review_required", "review_required" in item["reasons"])
    check("rev.page_signal", "asset_type_page_signal" in item["reasons"])
    check("rev.low_info", "low_information_signal" in item["reasons"])
    check("rev.score_low", "score_low" in item["reasons"])
    check("rev.placement_unknown", item["placement"] == "unknown")

    # A page_visual_signal even at medium priority is not embeddable → review_only.
    med = plan_visual_replacement_candidate(_score("page_visual_signal", "medium"))
    check("rev.page_signal_medium", med["candidate_action"] == "review_only")

    # Any low-priority figure type → review_only too.
    low_fig = plan_visual_replacement_candidate(_score("diagram", "low"))
    check("rev.low_figure", low_fig["candidate_action"] == "review_only")


# --- 5. Malformed score item → safe fallback with unknown --------------------

def test_malformed_score_item() -> None:
    for bad in (None, 123, "x", [], object()):
        item = plan_visual_replacement_candidate(bad)  # type: ignore[arg-type]
        check(f"mal.action[{type(bad).__name__}]", item["candidate_action"] == "unknown")
        check(f"mal.warning[{type(bad).__name__}]", "score_item_malformed" in item["warnings"])
        check(f"mal.vocab[{type(bad).__name__}]", _vocab_ok(item))
        check(f"mal.fallback_id[{type(bad).__name__}]", item["asset_id"] == "asset_0001", item["asset_id"])
        check(f"mal.placement[{type(bad).__name__}]", item["placement"] == "unknown")
    # Mixed list keeps positional fallback ids.
    items = plan_visual_replacement_candidates([_score("table", "high"), None, 42])
    check("mal.mixed_len", len(items) == 3)
    check("mal.mixed_ids", items[1]["asset_id"] == "asset_0002" and items[2]["asset_id"] == "asset_0003")


# --- 6. Malformed scoring report → safe completed report ---------------------

def test_malformed_scoring_report() -> None:
    for bad in (None, 123, "nope", [], object(), {"scores": "not-a-list"}, {"no_scores": 1}):
        report = build_visual_replacement_plan(bad)  # type: ignore[arg-type]
        check(f"report.completed[{type(bad).__name__}]", report["status"] == "completed")
        check(f"report.kind[{type(bad).__name__}]", report["kind"] == REPORT_KIND == "visual_replacement_plan")
        check(f"report.items_empty[{type(bad).__name__}]", report["items"] == [])
        check(f"report.json_safe[{type(bad).__name__}]", _is_json_safe(report))
    r1 = build_visual_replacement_plan({"scores": "nope"})
    check("report.bad_scores_warning", "scoring_report_malformed" in r1["warnings"])
    r2 = build_visual_replacement_plan(None)
    check("report.nondict_warning", "scoring_report_malformed" in r2["warnings"])
    # Valid empty report → completed, no warning.
    r3 = build_visual_replacement_plan(_scoring_report([]))
    check("report.empty_ok", r3["status"] == "completed" and r3["warnings"] == [])
    check("report.empty_summary", r3["summary"]["item_count"] == 0)
    check("report.envelope", r3["version"] == REPORT_VERSION and r3["source"] == "visual_asset_scoring.json")


# --- 7. Manifest cross-reference (presence only, no field leak) --------------

def _manifest(asset_ids: list, *, secret_caption: str = "") -> dict:
    return {
        "version": 1,
        "kind": "visual_assets_manifest",
        "status": "completed",
        "assets": [
            {
                "asset_id": aid,
                "source_page": 1,
                "asset_type": "table",
                "caption": secret_caption,
                "image_ref": "/home/victim/leak.png",
                "signals": {"chandra_label": secret_caption},
            }
            for aid in asset_ids
        ],
    }


def test_manifest_match() -> None:
    report = _scoring_report([_score("table", "high", asset_id="page_0002_fig_01", source_page=2)])
    manifest = _manifest(["page_0002_fig_01"], secret_caption="CONFIDENTIAL patient John Doe MRN 12345")
    plan = build_visual_replacement_plan(report, manifest=manifest)
    item = plan["items"][0]
    check("match.has_match", "has_manifest_match" in item["reasons"])
    check("match.no_lookup_warning", "asset_lookup_missing" not in item["warnings"])
    blob = json.dumps(plan)
    check("match.no_caption_leak", "patient" not in blob and "John Doe" not in blob and "MRN" not in blob, blob)
    check("match.no_image_ref_leak", "leak.png" not in blob and "/home/" not in blob, blob)
    check("match.no_caption_field", "caption" not in item and "image_ref" not in item and "signals" not in item)


# --- 8. Missing manifest match → missing_manifest_match + asset_lookup_missing -

def test_manifest_missing() -> None:
    report = _scoring_report([_score("table", "high", asset_id="page_0009_orphan_01")])
    manifest = _manifest(["page_0002_fig_01"])
    plan = build_visual_replacement_plan(report, manifest=manifest)
    item = plan["items"][0]
    check("miss.reason", "missing_manifest_match" in item["reasons"])
    check("miss.warning", "asset_lookup_missing" in item["warnings"])
    # Without a manifest, neither match reason nor lookup warning appears.
    plan_none = build_visual_replacement_plan(report)
    item_none = plan_none["items"][0]
    check("miss.no_manifest_no_reason", "missing_manifest_match" not in item_none["reasons"]
          and "has_manifest_match" not in item_none["reasons"])
    check("miss.no_manifest_no_warning", "asset_lookup_missing" not in item_none["warnings"])


# --- 9. Chandra-local item is advisory only + chandra_blocked ----------------

def test_chandra_blocked() -> None:
    item = plan_visual_replacement_candidate(_score("table", "high", provider="chandra_local"))
    check("chandra.blocked_reason", "chandra_blocked" in item["reasons"])
    check("chandra.provider", item["source_provider"] == "chandra_local")
    # Still advisory: a candidate_* action, never a binding include/omit.
    check("chandra.advisory_action", item["candidate_action"] in CANDIDATE_ACTIONS)
    check("chandra.is_candidate", item["candidate_action"].startswith("candidate_")
          or item["candidate_action"] in ("review_only", "unknown"))
    check("chandra.vocab", _vocab_ok(item))


# --- 10. No mutation of scoring report or manifest ---------------------------

def test_no_mutation() -> None:
    report = _scoring_report([
        _score("table", "high", asset_id="page_0002_fig_01"),
        _score("equation_block", "medium", asset_id="page_0003_eq_01"),
        _score("page_visual_signal", "low", asset_id="page_0001_visual_01"),
    ])
    manifest = _manifest(["page_0002_fig_01"], secret_caption="secret")
    report_before = copy.deepcopy(report)
    manifest_before = copy.deepcopy(manifest)
    plan = build_visual_replacement_plan(report, manifest=manifest)
    check("nomut.report", report == report_before)
    check("nomut.manifest", manifest == manifest_before)
    check("nomut.plan_is_new", plan is not report and plan is not manifest)
    check("nomut.summary", plan["summary"]["item_count"] == 3)


# --- 11. Smuggled secrets / paths never leak ---------------------------------

def test_smuggled_content_does_not_leak() -> None:
    hostile = {
        "asset_id": "page /home/victim/secret.pdf 01",
        "source_page": "https://evil.example.com/x",
        "asset_type": "Authorization: Bearer sk-ABCDEF0123456789ABCDEF",
        "source_provider": "/run/companion/host.sock --model /opt/models/x.gguf",
        "priority": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==",
        "caption": "see C:\\Users\\me\\key.txt and --image-min-tokens 1024",
        "image_ref": "/home/victim/leak.png",
        "asset_ref": "/opt/models/chandra.mmproj",
        "include_score": "sk_live_0123456789ABCDEFGHIJ",
        "reasons": ["smuggled --flag /etc/passwd"],
        "warnings": ["ftp://x/y"],
    }
    item = plan_visual_replacement_candidate(hostile)
    report = build_visual_replacement_plan(_scoring_report([hostile]), manifest=_manifest(["x"]))
    for label, obj in (("item", item), ("report", report)):
        blob = json.dumps(obj)
        check(f"leak.no_url[{label}]", not URLLIKE.search(blob), blob)
        check(f"leak.no_path[{label}]", not PATHLIKE.search(blob), blob)
        check(f"leak.no_auth[{label}]", not AUTHLIKE.search(blob), blob)
        check(f"leak.no_socket[{label}]", not SOCKETLIKE.search(blob), blob)
        check(f"leak.no_argv[{label}]", not ARGVLIKE.search(blob), blob)
        check(f"leak.no_keylike[{label}]", not KEYLIKE.search(blob), blob)
        check(f"leak.no_base64uri[{label}]", not BASE64URI.search(blob), blob)
        check(f"leak.no_gguf_mmproj[{label}]", not GGUFLIKE.search(blob), blob)
        check(f"leak.json_safe[{label}]", _is_json_safe(obj))
    # Hostile type/provider/priority are coerced + warned, never echoed.
    check("leak.type_coerced", item["asset_type"] == "unknown")
    check("leak.provider_coerced", item["source_provider"] == "unknown")
    check("leak.priority_coerced", item["priority"] == "unknown")
    check("leak.type_warning", "asset_type_unrecognized" in item["warnings"])
    check("leak.provider_warning", "source_provider_unrecognized" in item["warnings"])
    check("leak.priority_warning", "priority_unrecognized" in item["warnings"])
    check("leak.vocab_only", _vocab_ok(item))
    # No raw fields survive onto the item.
    for forbidden in ("caption", "image_ref", "asset_ref", "include_score", "recommended_action"):
        check(f"leak.no_field[{forbidden}]", forbidden not in item)


# --- 12. Invalid asset ids → deterministic safe fallback / sanitized ---------

def test_asset_id_fallback() -> None:
    missing = _score("table", "high")
    del missing["asset_id"]
    item = plan_visual_replacement_candidate(missing)
    check("id.missing_fallback", item["asset_id"] == "asset_0001", item["asset_id"])
    check("id.missing_warning", "asset_id_missing" in item["warnings"])

    nonstr = _score("table", "high", asset_id="")
    nonstr["asset_id"] = 12345
    s2 = plan_visual_replacement_candidate(nonstr)
    check("id.nonstr_fallback", s2["asset_id"] == "asset_0001")
    check("id.nonstr_warning", "asset_id_missing" in s2["warnings"])

    unsafe = _score("table", "high", asset_id="../../etc/passwd")
    s3 = plan_visual_replacement_candidate(unsafe)
    check("id.unsafe_sanitized", re.fullmatch(r"[A-Za-z0-9_]+", s3["asset_id"]) is not None, s3["asset_id"])
    check("id.unsafe_warning", "asset_id_invalid" in s3["warnings"])
    check("id.unsafe_no_path", "/" not in s3["asset_id"] and ".." not in s3["asset_id"])

    empty = _score("table", "high", asset_id="///")
    s4 = plan_visual_replacement_candidate(empty)
    check("id.empty_after_sanitize", s4["asset_id"] == "asset_0001")
    check("id.empty_warning", "asset_id_invalid" in s4["warnings"])

    # List indices drive deterministic fallback ids when missing.
    items = plan_visual_replacement_candidates([{"asset_type": "table", "priority": "high"},
                                                {"asset_type": "figure", "priority": "high"}])
    check("id.list_fallback_seq", [s["asset_id"] for s in items] == ["asset_0001", "asset_0002"])


# --- 13. Summary counts -------------------------------------------------------

def test_summary_counts() -> None:
    report = _scoring_report([
        _score("table", "high", asset_id="a1"),                 # convert_to_table
        _score("diagram", "high", asset_id="a2"),               # include_as_figure
        _score("equation_block", "medium", asset_id="a3"),      # summarize_as_text
        _score("page_visual_signal", "low", asset_id="a4"),     # review_only
        _score("table", "unknown", asset_id="a5"),              # unknown
    ])
    plan = build_visual_replacement_plan(report)
    s = plan["summary"]
    check("summary.count", s["item_count"] == 5)
    check("summary.fig", s["candidate_include_as_figure_count"] == 1, str(s))
    check("summary.table", s["candidate_convert_to_table_count"] == 1, str(s))
    check("summary.text", s["candidate_summarize_as_text_count"] == 1, str(s))
    check("summary.review", s["review_only_count"] == 1, str(s))
    check("summary.unknown", s["unknown_count"] == 1, str(s))
    total = (s["candidate_include_as_figure_count"] + s["candidate_convert_to_table_count"]
             + s["candidate_summarize_as_text_count"] + s["review_only_count"] + s["unknown_count"])
    check("summary.total_matches", total == 5)


# --- 14. Determinism ----------------------------------------------------------

def test_determinism() -> None:
    report = _scoring_report([_score("diagram", "high"), _score("table", "medium", asset_id="t1")])
    a = build_visual_replacement_plan(report)
    b = build_visual_replacement_plan(report)
    check("det.identical", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))


# --- 15. No forbidden imports -------------------------------------------------

def test_no_forbidden_imports() -> None:
    path = os.path.join(os.path.dirname(__file__), "..", "pipeline", "visual_replacement_planner.py")
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    import_lines = [
        ln.strip().lower()
        for ln in src.splitlines()
        if ln.strip().startswith(("import ", "from "))
    ]
    # Slice 49 added an advisory artifact writer, so ``json`` (safe serializer) and
    # ``sys`` (stderr note) are now legitimate stdlib imports. The dangerous imports
    # (network / filesystem / model runtimes / cross-module pipeline code) stay
    # forbidden — the writer takes a duck-typed ``job`` and never imports job_manager.
    forbidden = ["fitz", "pymupdf", "pytesseract", "tesseract", "llama_cpp",
                 "llama-cpp", "mistral", "google.generativeai", "genai", "gemini",
                 "chandra", "local_model", "companion", "requests", "httpx",
                 "urllib", "socket", "subprocess",
                 "visual_assets_manifest", "visual_asset_scoring", "visual_asset_extractor",
                 "extract", "run_llm_job", "job_manager", "render", "server"]
    leaks = sorted({tok for ln in import_lines for tok in forbidden if tok in ln})
    check("imports.none_forbidden", not leaks, f"found in imports: {leaks}")
    allowed_prefixes = ("import json", "import re", "import sys",
                        "from __future__", "from typing import")
    unexpected = [ln for ln in import_lines if not ln.startswith(allowed_prefixes)]
    check("imports.only_expected_stdlib", not unexpected, f"unexpected: {unexpected}")


def main() -> int:
    test_include_as_figure()
    test_convert_to_table()
    test_summarize_as_text()
    test_review_only()
    test_malformed_score_item()
    test_malformed_scoring_report()
    test_manifest_match()
    test_manifest_missing()
    test_chandra_blocked()
    test_no_mutation()
    test_smuggled_content_does_not_leak()
    test_asset_id_fallback()
    test_summary_counts()
    test_determinism()
    test_no_forbidden_imports()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
