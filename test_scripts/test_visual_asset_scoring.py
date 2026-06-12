#!/usr/bin/env python3
"""Focused tests for the pure visual asset scoring core (Slice 46, roadmap V3).

Run with:

    python test_scripts/test_visual_asset_scoring.py

No external APIs and no PyMuPDF/Tesseract/llama.cpp/Mistral/Gemini/Chandra-runtime
or Local-Model-Manager dependency: the scorer is a pure function of already-
sanitized, manifest-shaped asset dicts, so these tests feed it tiny *handcrafted
synthetic* asset records based on the Slice 38/40 manifest shape and the Slice 42
Chandra normalizer asset shape. No real model dumps, private documents,
screenshots, or local paths are used.
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

# Leak detectors — none of these may appear anywhere in scoring output.
KEYLIKE = re.compile(r"(sk-|sk_|pk-|rk_)[A-Za-z0-9_\-]{12,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/root/|/tmp/|/opt/|C:\\|\\\\)")
URLLIKE = re.compile(r"https?://|file://|ftp://")
AUTHLIKE = re.compile(r"Authorization|Bearer\s+\S", re.IGNORECASE)
SOCKETLIKE = re.compile(r"\.sock\b")
ARGVLIKE = re.compile(r"(?<!\S)--[A-Za-z]")
BASE64URI = re.compile(r"data:[^;]+;base64,")
GGUFLIKE = re.compile(r"\.gguf\b|mmproj", re.IGNORECASE)

from pipeline.visual_asset_scoring import (  # noqa: E402
    ASSET_TYPES,
    PRIORITIES,
    REASONS,
    RECOMMENDED_ACTION_UNKNOWN,
    REPORT_KIND,
    REPORT_VERSION,
    SOURCE_PROVIDERS,
    WARNINGS,
    score_visual_asset_candidate,
    score_visual_asset_candidates,
    score_visual_assets_manifest,
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


def _score_keys() -> set:
    return {
        "asset_id", "source_page", "source_provider", "asset_type",
        "recommended_action", "priority", "include_score", "reasons", "warnings",
    }


def _vocab_ok(score: dict) -> bool:
    return (
        score["priority"] in PRIORITIES
        and score["asset_type"] in ASSET_TYPES
        and score["source_provider"] in SOURCE_PROVIDERS
        and score["recommended_action"] == RECOMMENDED_ACTION_UNKNOWN
        and all(r in REASONS for r in score["reasons"])
        and all(w in WARNINGS for w in score["warnings"])
    )


# --- Synthetic manifest-shaped fixtures (no real data) -----------------------

def _page_visual_signal(both_signals: bool = True) -> dict:
    return {
        "asset_id": "page_0001_visual_01",
        "source_page": 1,
        "asset_type": "page_visual_signal",
        "bbox": None,
        "caption": None,
        "source_provider": "fitz_local",
        "recommended_action": "unknown",
        "dedupe_group": None,
        "scores": {},
        "signals": {
            "image_object_count": 2 if both_signals else 0,
            "drawing_object_count": 3 if both_signals else 0,
            "has_images": both_signals,
            "has_drawings": both_signals,
            "page_width": 612.0,
            "page_height": 792.0,
            "classification": "embedded_text",
            "ocr_route_action": "use_embedded_text",
        },
        "warnings": [],
    }


def _extracted_figure() -> dict:
    return {
        "asset_id": "page_0002_fig_01",
        "source_page": 2,
        "asset_type": "extracted_figure",
        "bbox": [50.0, 60.0, 500.0, 700.0],
        "caption": None,
        "source_provider": "fitz_local",
        "recommended_action": "unknown",
        "dedupe_group": None,
        "image_ref": "assets/page_0002_fig_01.png",
        "scores": {},
        "signals": {
            "page_width": 612.0,
            "page_height": 792.0,
            "image_index": 0,
            "crop_width_px": 450,
            "crop_height_px": 640,
        },
        "warnings": [],
    }


def _chandra_asset(asset_type: str, bbox=None, caption=None) -> dict:
    return {
        "asset_id": f"page_0003_chandra_01",
        "source_page": 3,
        "asset_type": asset_type,
        "bbox": bbox,
        "caption": caption,
        "source_provider": "chandra_local",
        "recommended_action": "unknown",
        "dedupe_group": None,
        "scores": {},
        "asset_ref": None,
        "signals": {"chandra_label": "Table"},
        "warnings": [],
    }


# --- 1. Minimal valid page_visual_signal -------------------------------------

def test_page_visual_signal() -> None:
    score = score_visual_asset_candidate(_page_visual_signal(both_signals=True))
    check("pvs.keys", set(score) == _score_keys(), str(set(score)))
    check("pvs.vocab", _vocab_ok(score))
    check("pvs.id", score["asset_id"] == "page_0001_visual_01")
    check("pvs.page", score["source_page"] == 1)
    check("pvs.type", score["asset_type"] == "page_visual_signal")
    check("pvs.provider", score["source_provider"] == "fitz_local")
    check("pvs.action_unknown", score["recommended_action"] == "unknown")
    check("pvs.has_image_reason", "page_has_images" in score["reasons"])
    check("pvs.has_drawing_reason", "page_has_drawings" in score["reasons"])
    check("pvs.provider_reason", "provider_fitz_local" in score["reasons"])
    # Both page signals lift a bare page signal from low to (conservatively) medium.
    check("pvs.priority_medium", score["priority"] == "medium", score["priority"])
    check("pvs.no_warnings", score["warnings"] == [])
    check("pvs.json_safe", _is_json_safe(score))

    weak = score_visual_asset_candidate(_page_visual_signal(both_signals=False))
    check("pvs.weak_low", weak["priority"] == "low", weak["priority"])
    check("pvs.weak_low_info", "low_information_signal" in weak["reasons"])


# --- 2. extracted_figure with bbox + signals ---------------------------------

def test_extracted_figure() -> None:
    score = score_visual_asset_candidate(_extracted_figure())
    check("fig.vocab", _vocab_ok(score))
    check("fig.type", score["asset_type"] == "extracted_figure")
    check("fig.type_reason", "asset_type_extracted_figure" in score["reasons"])
    check("fig.has_bbox", "has_bbox" in score["reasons"])
    # bbox covers a large fraction of a 612x792 page → large_region.
    check("fig.large_region", "large_region" in score["reasons"])
    check("fig.action_unknown", score["recommended_action"] == "unknown")
    check("fig.priority_high", score["priority"] == "high", score["priority"])
    check("fig.score_range", 0.0 <= score["include_score"] <= 1.0)


# --- 3. Chandra-style diagram / table / equation_block -----------------------

def test_chandra_assets() -> None:
    table = score_visual_asset_candidate(_chandra_asset("table", bbox=[10.0, 10.0, 200.0, 80.0]))
    check("chandra.table_reason", "asset_type_table" in table["reasons"])
    check("chandra.table_provider", "provider_chandra_local" in table["reasons"])
    check("chandra.table_high", table["priority"] == "high", table["priority"])
    check("chandra.table_action", table["recommended_action"] == "unknown")

    diagram = score_visual_asset_candidate(
        _chandra_asset("diagram", bbox=[5.0, 5.0, 90.0, 30.0], caption="A flow chart.")
    )
    check("chandra.diagram_reason", "asset_type_diagram" in diagram["reasons"])
    check("chandra.diagram_caption", "has_caption" in diagram["reasons"])
    check("chandra.diagram_priority", diagram["priority"] in ("high", "medium"))

    eq = score_visual_asset_candidate(_chandra_asset("equation_block"))
    check("chandra.eq_reason", "asset_type_equation" in eq["reasons"])
    check("chandra.eq_priority", eq["priority"] in ("high", "medium"))


# --- 4. Deterministic, sensible priority ordering ----------------------------

def test_priority_ordering() -> None:
    table = score_visual_asset_candidate(_chandra_asset("table", bbox=[10.0, 10.0, 200.0, 80.0]))
    figure = score_visual_asset_candidate(_chandra_asset("figure"))
    pvs_weak = score_visual_asset_candidate(_page_visual_signal(both_signals=False))
    check(
        "order.table_ge_figure",
        table["include_score"] >= figure["include_score"],
        f"{table['include_score']} vs {figure['include_score']}",
    )
    check(
        "order.figure_ge_pvs",
        figure["include_score"] >= pvs_weak["include_score"],
        f"{figure['include_score']} vs {pvs_weak['include_score']}",
    )
    # Determinism: identical input → byte-identical score.
    a = score_visual_asset_candidate(_extracted_figure())
    b = score_visual_asset_candidate(_extracted_figure())
    check("order.deterministic", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))


# --- 5. recommended_action stays "unknown" everywhere ------------------------

def test_action_always_unknown() -> None:
    assets = [
        _page_visual_signal(),
        _extracted_figure(),
        _chandra_asset("table", bbox=[10.0, 10.0, 200.0, 80.0]),
        _chandra_asset("diagram"),
        _chandra_asset("equation_block"),
        _chandra_asset("figure"),
        _chandra_asset("image_region"),
        _chandra_asset("unknown_region"),
    ]
    report = score_visual_assets_manifest({"assets": assets})
    check("action.all_unknown", all(s["recommended_action"] == "unknown" for s in report["scores"]))


# --- 6. Invalid / missing bbox ------------------------------------------------

def test_bbox_invalid() -> None:
    bad = _extracted_figure()
    bad["bbox"] = [500.0, 500.0, 10.0, 10.0]  # ill-ordered
    score = score_visual_asset_candidate(bad)
    check("bbox.invalid_warning", "bbox_invalid" in score["warnings"])
    check("bbox.invalid_no_has_bbox", "has_bbox" not in score["reasons"])
    check("bbox.invalid_sanitized", "input_sanitized" in score["reasons"])

    bad2 = _extracted_figure()
    bad2["bbox"] = "not a box"
    score2 = score_visual_asset_candidate(bad2)
    check("bbox.nonlist_warning", "bbox_invalid" in score2["warnings"])

    bad3 = _extracted_figure()
    bad3["bbox"] = [1.0, 2.0, 3.0]  # wrong length
    score3 = score_visual_asset_candidate(bad3)
    check("bbox.shortlist_warning", "bbox_invalid" in score3["warnings"])

    # A None bbox (legit for page_visual_signal) must NOT warn.
    ok = score_visual_asset_candidate(_page_visual_signal())
    check("bbox.none_no_warning", "bbox_invalid" not in ok["warnings"])


# --- 7. Invalid / missing asset id → safe deterministic fallback -------------

def test_asset_id_fallback() -> None:
    missing = _extracted_figure()
    del missing["asset_id"]
    score = score_visual_asset_candidate(missing)
    check("id.missing_fallback", score["asset_id"] == "asset_0001", score["asset_id"])
    check("id.missing_warning", "asset_id_missing" in score["warnings"])

    nonstr = _extracted_figure()
    nonstr["asset_id"] = 12345
    s2 = score_visual_asset_candidate(nonstr)
    check("id.nonstr_fallback", s2["asset_id"] == "asset_0001")
    check("id.nonstr_warning", "asset_id_missing" in s2["warnings"])

    unsafe = _extracted_figure()
    unsafe["asset_id"] = "../../etc/passwd"
    s3 = score_visual_asset_candidate(unsafe)
    check("id.unsafe_sanitized", re.fullmatch(r"[A-Za-z0-9_]+", s3["asset_id"]) is not None, s3["asset_id"])
    check("id.unsafe_warning", "asset_id_invalid" in s3["warnings"])
    check("id.unsafe_no_path", "/" not in s3["asset_id"] and ".." not in s3["asset_id"])

    empty = _extracted_figure()
    empty["asset_id"] = "///"
    s4 = score_visual_asset_candidate(empty)
    check("id.empty_after_sanitize", s4["asset_id"] == "asset_0001")
    check("id.empty_warning", "asset_id_invalid" in s4["warnings"])

    # List indices drive deterministic fallback ids.
    scores = score_visual_asset_candidates([{"asset_type": "table"}, {"asset_type": "figure"}])
    check("id.list_fallback_seq", [s["asset_id"] for s in scores] == ["asset_0001", "asset_0002"])


# --- 8. Malformed manifest → safe completed report ---------------------------

def test_malformed_manifest() -> None:
    for bad in (None, 123, "nope", [], object(), {"assets": "not-a-list"}, {"no_assets": 1}):
        report = score_visual_assets_manifest(bad)  # type: ignore[arg-type]
        check(f"manifest.completed[{type(bad).__name__}]", report["status"] == "completed")
        check(f"manifest.kind[{type(bad).__name__}]", report["kind"] == REPORT_KIND == "visual_asset_scoring")
        check(f"manifest.json_safe[{type(bad).__name__}]", _is_json_safe(report))
        check(f"manifest.scores_empty[{type(bad).__name__}]", report["scores"] == [])
    # Dict-but-bad-assets and non-dict should warn manifest_malformed.
    r1 = score_visual_assets_manifest({"assets": "nope"})
    check("manifest.bad_assets_warning", "manifest_malformed" in r1["warnings"])
    r2 = score_visual_assets_manifest(None)
    check("manifest.nondict_warning", "manifest_malformed" in r2["warnings"])
    # Valid empty manifest → completed, no warning.
    r3 = score_visual_assets_manifest({"assets": []})
    check("manifest.empty_ok", r3["status"] == "completed" and r3["warnings"] == [])
    check("manifest.empty_summary", r3["summary"]["asset_count"] == 0)


# --- 9. Non-list / non-dict asset inputs handled safely ----------------------

def test_non_dict_assets() -> None:
    check("nonlist.candidates", score_visual_asset_candidates("nope") == [])
    check("nonlist.candidates_none", score_visual_asset_candidates(None) == [])
    for bad in (None, 123, "x", [], object()):
        score = score_visual_asset_candidate(bad)  # type: ignore[arg-type]
        check(f"nondict.input_unrecognized[{type(bad).__name__}]", "input_unrecognized" in score["warnings"])
        check(f"nondict.unknown_priority[{type(bad).__name__}]", score["priority"] == "unknown")
        check(f"nondict.vocab[{type(bad).__name__}]", _vocab_ok(score))
    # Mixed list: bad records still produce safe scores at their index.
    scores = score_visual_asset_candidates([_extracted_figure(), None, 42])
    check("nondict.mixed_len", len(scores) == 3)
    check("nondict.mixed_ids", scores[1]["asset_id"] == "asset_0002" and scores[2]["asset_id"] == "asset_0003")


# --- 10. No mutation of input -------------------------------------------------

def test_no_mutation() -> None:
    asset = _extracted_figure()
    before = copy.deepcopy(asset)
    score_visual_asset_candidate(asset)
    check("nomut.single", asset == before)

    manifest = {"assets": [_page_visual_signal(), _extracted_figure(), _chandra_asset("table", bbox=[1.0, 1.0, 9.0, 9.0])]}
    manifest_before = copy.deepcopy(manifest)
    report = score_visual_assets_manifest(manifest)
    check("nomut.manifest", manifest == manifest_before)
    check("nomut.report_is_new", report is not manifest)
    # The manifest's own assets keep recommended_action unchanged (not scored in place).
    check("nomut.manifest_action_intact", all(a["recommended_action"] == "unknown" for a in manifest["assets"]))


# --- 11. No raw captions emitted ---------------------------------------------

def test_no_raw_caption_emitted() -> None:
    secret_caption = "CONFIDENTIAL patient John Doe MRN 12345 figure"
    asset = _chandra_asset("diagram", bbox=[1.0, 1.0, 9.0, 9.0], caption=secret_caption)
    score = score_visual_asset_candidate(asset)
    blob = json.dumps(score)
    check("caption.used_as_signal", "has_caption" in score["reasons"])
    check("caption.not_emitted", "patient" not in blob and "John Doe" not in blob and "MRN" not in blob, blob)
    check("caption.no_caption_field", "caption" not in score)


# --- 12. Smuggled secrets / paths never leak ---------------------------------

def test_smuggled_content_does_not_leak() -> None:
    hostile = {
        "asset_id": "page /home/victim/secret.pdf 01",
        "source_page": "https://evil.example.com/x",
        "asset_type": "Authorization: Bearer sk-ABCDEF0123456789ABCDEF",
        "source_provider": "/run/companion/host.sock --model /opt/models/x.gguf",
        "bbox": ["data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==", 2, 3, 4],
        "caption": "see C:\\Users\\me\\key.txt and --image-min-tokens 1024",
        "image_ref": "/home/victim/leak.png",
        "asset_ref": "/opt/models/chandra.mmproj",
        "signals": {
            "chandra_label": "sk_live_0123456789ABCDEFGHIJ",
            "page_width": "ftp://x/y",
            "page_height": "\\\\unc\\share\\z",
        },
        "warnings": ["smuggled --flag /etc/passwd"],
    }
    score = score_visual_asset_candidate(hostile)
    report = score_visual_assets_manifest({"assets": [hostile]})
    for label, obj in (("score", score), ("report", report)):
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
    # The hostile asset_type/provider are not in vocab → coerced + warned.
    check("leak.type_coerced", score["asset_type"] == "unknown")
    check("leak.provider_coerced", score["source_provider"] == "unknown")
    check("leak.type_warning", "asset_type_unrecognized" in score["warnings"])
    check("leak.provider_warning", "source_provider_unrecognized" in score["warnings"])
    check("leak.vocab_only", _vocab_ok(score))


# --- 13. Summary counts -------------------------------------------------------

def test_summary_counts() -> None:
    assets = [
        _chandra_asset("table", bbox=[10.0, 10.0, 200.0, 80.0]),  # high
        _chandra_asset("image_region"),                            # low
        _chandra_asset("unknown_region"),                          # unknown
        _page_visual_signal(both_signals=True),                    # medium
    ]
    report = score_visual_assets_manifest({"assets": assets})
    s = report["summary"]
    check("summary.count", s["asset_count"] == 4)
    total = (
        s["high_priority_count"] + s["medium_priority_count"]
        + s["low_priority_count"] + s["unknown_priority_count"]
    )
    check("summary.total_matches", total == 4, str(s))
    check("summary.has_unknown", s["unknown_priority_count"] >= 1)
    check("summary.has_high", s["high_priority_count"] >= 1)
    check("summary.report_envelope", report["version"] == REPORT_VERSION and report["source"] == "visual_assets_manifest.json")


# --- 14. source_page coercion -------------------------------------------------

def test_source_page_coercion() -> None:
    bad = _extracted_figure()
    bad["source_page"] = -3
    score = score_visual_asset_candidate(bad)
    check("page.negative_none", score["source_page"] is None)
    check("page.negative_warning", "source_page_invalid" in score["warnings"])

    bad2 = _extracted_figure()
    bad2["source_page"] = "not-a-number"
    s2 = score_visual_asset_candidate(bad2)
    check("page.nonnum_none", s2["source_page"] is None)
    check("page.nonnum_warning", "source_page_invalid" in s2["warnings"])

    missing = _extracted_figure()
    del missing["source_page"]
    s3 = score_visual_asset_candidate(missing)
    check("page.absent_none_no_warning", s3["source_page"] is None and "source_page_invalid" not in s3["warnings"])

    good = _extracted_figure()
    s4 = score_visual_asset_candidate(good)
    check("page.valid_kept", s4["source_page"] == 2)


# --- 15. No forbidden imports -------------------------------------------------

def test_no_forbidden_imports() -> None:
    path = os.path.join(os.path.dirname(__file__), "..", "pipeline", "visual_asset_scoring.py")
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    import_lines = [
        ln.strip().lower()
        for ln in src.splitlines()
        if ln.strip().startswith(("import ", "from "))
    ]
    forbidden = ["fitz", "pymupdf", "pytesseract", "tesseract", "llama_cpp",
                 "llama-cpp", "mistral", "google.generativeai", "genai", "gemini",
                 "chandra", "local_model", "companion", "requests", "httpx",
                 "urllib", "socket", "subprocess",
                 "visual_assets_manifest", "visual_asset_extractor", "extract",
                 "run_llm_job", "job_manager", "render", "server"]
    leaks = sorted({tok for ln in import_lines for tok in forbidden if tok in ln})
    check("imports.none_forbidden", not leaks, f"found in imports: {leaks}")
    # Slice 47 adds a thin degrade-not-fail artifact writer, so json/sys (stdlib)
    # are now legitimately imported. The forbidden-import guard above still rejects
    # any provider / network / extraction / job-internal import.
    allowed_prefixes = (
        "import re", "import json", "import sys",
        "from __future__", "from typing import",
    )
    unexpected = [ln for ln in import_lines if not ln.startswith(allowed_prefixes)]
    check("imports.only_expected_stdlib", not unexpected, f"unexpected: {unexpected}")


def main() -> int:
    test_page_visual_signal()
    test_extracted_figure()
    test_chandra_assets()
    test_priority_ordering()
    test_action_always_unknown()
    test_bbox_invalid()
    test_asset_id_fallback()
    test_malformed_manifest()
    test_non_dict_assets()
    test_no_mutation()
    test_no_raw_caption_emitted()
    test_smuggled_content_does_not_leak()
    test_summary_counts()
    test_source_page_coercion()
    test_no_forbidden_imports()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
