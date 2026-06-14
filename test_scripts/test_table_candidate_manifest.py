#!/usr/bin/env python3
"""Focused tests for the ``table_candidates_manifest.json`` core + writer (Slice 92).

Run with:

    python test_scripts/test_table_candidate_manifest.py

Synthetic dictionaries and temp job directories only. No PDFs, images, providers,
renderers, OCR engines, or model calls are required. The module derives sanitized
table-candidate records from an already-sanitized ``visual_assets_manifest.json``-
shaped dict and persists them as a safe exact-name artifact. It reconstructs no
table and inspects no PDF/image.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
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
FORBIDDEN_CANARIES = [
    "private-source.pdf",
    "Quarterly Private Plan",
    "raw document paragraph",
    "raw OCR dump",
    "source caption text",
    "table cell text",
    "assets/secret.png",
    "sk_tablecandidatemanifest1234567890",
    "synthetic boom with private details",
]

from pipeline.job_manager import Job  # noqa: E402
from pipeline.table_candidate_manifest import (  # noqa: E402
    CANDIDATE_ID_PREFIX,
    TABLE_CANDIDATES_MANIFEST_FILENAME,
    build_table_candidates_manifest,
    table_policy_candidates,
    write_table_candidates_manifest,
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


def _make_job(root: str, job_id: str = "job-table-candidate") -> Job:
    job = Job(id=job_id, root=Path(root))
    job.input_dir.mkdir(parents=True, exist_ok=True)
    job.logs_dir.mkdir(parents=True, exist_ok=True)
    job._write_manifest({"id": job.id, "status": "created"})
    return job


def _leaky_fields() -> dict[str, Any]:
    """Hostile fields a manifest record might carry; the builder must NOT echo them."""
    return {
        "filename": "private-source.pdf",
        "title": "Quarterly Private Plan",
        "path": "/home/example/private-source.pdf",
        "text": "raw document paragraph",
        "ocr_text": "raw OCR dump",
        "caption": "source caption text",
        "table_text": "table cell text",
        "image_ref": "assets/secret.png",
        "asset_ref": "assets/secret.png",
        "url": "https://example.invalid/private-source.pdf",
        "argv": "--model /home/example/model.gguf --mmproj /home/example/mmproj.gguf",
        "socket": "/tmp/private.sock",
        "bytes": "data:image/png;base64,AAAA",
        "api_key": "sk_tablecandidatemanifest1234567890",
        "asset_id": "page_0004_visual_01",
    }


def _table_record(
    source_index: int,
    source_page: Any,
    *,
    asset_type: str = "grid_table",
    signals: dict[str, Any] | None = None,
    confidence: Any = None,
    leaky: bool = True,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = dict(_leaky_fields()) if leaky else {}
    rec.update({"asset_type": asset_type, "source_index": source_index})
    if source_page is not None:
        rec["source_page"] = source_page
    if signals is not None:
        # nest the structural signals UNDER a `signals` dict (and add leaky text there too)
        rec["signals"] = dict(signals)
        if leaky:
            rec["signals"].update({"caption": "source caption text", "table_text": "table cell text"})
    if confidence is not None:
        rec["confidence"] = confidence
    if extra:
        rec.update(extra)
    return rec


def _nontable_record(source_index: int, source_page: int) -> dict[str, Any]:
    rec = dict(_leaky_fields())
    rec.update(
        {
            "asset_type": "page_visual_signal",
            "source_index": source_index,
            "source_page": source_page,
        }
    )
    return rec


def _manifest(assets: list[Any], status: str = "completed") -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "visual_assets_manifest",
        "status": status,
        "assets": assets,
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


# --- Builder: degenerate inputs ----------------------------------------------


def test_missing_and_malformed_inputs() -> None:
    check("None → skipped", build_table_candidates_manifest(None)["status"] == "skipped")
    check("int → skipped", build_table_candidates_manifest(123)["status"] == "skipped")
    check("list → skipped", build_table_candidates_manifest([])["status"] == "skipped")
    skipped_status = build_table_candidates_manifest({"status": "skipped"})
    check("skipped manifest → skipped", skipped_status["status"] == "skipped")
    bad_assets = build_table_candidates_manifest({"status": "completed", "assets": 5})
    check("non-list assets → skipped", bad_assets["status"] == "skipped")
    # Shape of a skipped manifest stays exact + safe.
    m = build_table_candidates_manifest(None)
    check("skipped kind", m["kind"] == "table_candidates_manifest")
    check("skipped version", m["version"] == 1)
    check("skipped candidates empty", m["candidates"] == [])
    check("skipped summary zeros", m["summary"]["table_like_candidate_count"] == 0)
    check("skipped warning is closed token", m["warnings"] and isinstance(m["warnings"][0], str))
    check("skipped no leak", _scan_for_leak(m) is None, _scan_for_leak(m) or "")


def test_empty_assets_completed_empty() -> None:
    m = build_table_candidates_manifest(_manifest([]))
    check("empty assets → completed", m["status"] == "completed")
    check("empty assets → 0 candidates", m["summary"]["table_like_candidate_count"] == 0)
    check("empty assets → 0 records", m["summary"]["candidate_count"] == 0)
    check("empty assets → no candidates list", m["candidates"] == [])
    check("empty assets no leak", _scan_for_leak(m) is None)


# --- Builder: table-like records become sanitized candidates -----------------


def test_table_like_records_become_candidates() -> None:
    vm = _manifest(
        [
            _table_record(
                0, 4, asset_type="grid_table",
                signals={"has_text_layer": True, "rows": 5, "columns": 3,
                         "cell_text_count": 12, "numeric_cell_count": 6, "header_cell_count": 3},
                confidence="high",
            ),
            _table_record(
                0, 7, asset_type="dense_table",
                signals={"has_text_layer": False, "rows": 9, "columns": 4},
                confidence="medium",
            ),
            _table_record(1, 2, asset_type="table_region", signals={}),
        ]
    )
    m = build_table_candidates_manifest(vm)
    check("3 table candidates", m["summary"]["table_like_candidate_count"] == 3, str(m["summary"]))
    check("records counted", m["summary"]["candidate_count"] == 3)
    check("source_count", m["summary"]["source_count"] == 2)
    check("pages_with_candidates", m["summary"]["page_count_with_table_candidates"] == 3)
    cands = m["candidates"]
    check("kind grid mapped", cands[0]["table_kind"] == "grid_table")
    check("kind dense mapped", cands[1]["table_kind"] == "dense_table")
    check("kind region mapped", cands[2]["table_kind"] == "table_region")
    check("confidence high preserved", cands[0]["confidence"] == "high")
    check("confidence medium preserved", cands[1]["confidence"] == "medium")
    check("confidence defaults unknown", cands[2]["confidence"] == "unknown")
    check("signals counts preserved", cands[0]["signals"]["rows"] == 5 and cands[0]["signals"]["columns"] == 3)
    check("has_text_layer bool true", cands[0]["signals"]["has_text_layer"] is True)
    check("has_text_layer bool false", cands[1]["signals"]["has_text_layer"] is False)
    check("missing signals → zeros", cands[2]["signals"]["rows"] == 0 and cands[2]["signals"]["cell_text_count"] == 0)
    check("missing signals → has_text_layer false", cands[2]["signals"]["has_text_layer"] is False)
    check("status completed", m["status"] == "completed")
    check("no leak across candidates", _scan_for_leak(m) is None, _scan_for_leak(m) or "")


def test_table_token_variants_all_recognized() -> None:
    for token, expected in [
        ("grid_table", "grid_table"),
        ("dense_table", "dense_table"),
        ("table_region", "table_region"),
        ("table_image", "table_image"),
        ("table_like", "table_like"),
        ("tabular", "table_like"),
        ("table", "table_like"),
        ("GRID_TABLE", "grid_table"),
        ("  Table  ", "table_like"),
    ]:
        m = build_table_candidates_manifest(_manifest([_table_record(0, 3, asset_type=token, leaky=False)]))
        ok = m["summary"]["table_like_candidate_count"] == 1 and m["candidates"][0]["table_kind"] == expected
        check(f"token {token!r} → {expected}", ok, str(m["summary"]))
    # Token can arrive via an alternate type field, not just asset_type.
    rec = {"source_index": 0, "source_page": 3, "asset_type": "page_visual_signal", "visual_type": "table"}
    m = build_table_candidates_manifest(_manifest([rec]))
    check("token via visual_type field", m["summary"]["table_like_candidate_count"] == 1)


# --- Builder: skips ----------------------------------------------------------


def test_non_table_records_skipped_and_counted() -> None:
    vm = _manifest([_nontable_record(0, 1), _nontable_record(0, 2), _table_record(0, 5, leaky=False)])
    m = build_table_candidates_manifest(vm)
    check("only 1 table candidate", m["summary"]["table_like_candidate_count"] == 1)
    check("2 non-table skipped", m["summary"]["skipped_non_table_count"] == 2, str(m["summary"]))
    check("not_table_like warning", "not_table_like" in m["warnings"])


def test_missing_or_invalid_source_page_skipped() -> None:
    vm = _manifest(
        [
            _table_record(0, None, leaky=False),       # missing page
            _table_record(0, 0, leaky=False),          # invalid (<=0)
            _table_record(0, "4", leaky=False),        # invalid (str)
            _table_record(0, 1.5, leaky=False),        # invalid (float)
            _table_record(0, 6, leaky=False),          # valid
        ]
    )
    m = build_table_candidates_manifest(vm)
    check("only valid page kept", m["summary"]["table_like_candidate_count"] == 1, str(m["summary"]))
    check("4 unsafe/incomplete skipped", m["summary"]["unsafe_or_incomplete_skipped_count"] == 4, str(m["summary"]))
    check("page-missing warning", "source_page_missing" in m["warnings"])
    check("page-invalid warning", "source_page_invalid" in m["warnings"])
    check("kept candidate page", m["candidates"][0]["source_page"] == 6)


def test_unsafe_records_skipped() -> None:
    vm = _manifest(
        [
            _table_record(0, 3, leaky=False, extra={"unsafe": True}),
            _table_record(0, 4, leaky=False, extra={"safe": False}),
            _table_record(0, 5, leaky=False, extra={"warnings": ["visual_record_unsafe"]}),
            _table_record(0, 6, leaky=False),
        ]
    )
    m = build_table_candidates_manifest(vm)
    check("only safe kept", m["summary"]["table_like_candidate_count"] == 1, str(m["summary"]))
    check("3 unsafe skipped", m["summary"]["unsafe_or_incomplete_skipped_count"] == 3)
    check("unsafe warning", "record_unsafe" in m["warnings"])


def test_malformed_record_skipped() -> None:
    vm = _manifest([None, 5, "x", _table_record(0, 2, leaky=False)])
    m = build_table_candidates_manifest(vm)
    check("malformed skipped, 1 kept", m["summary"]["table_like_candidate_count"] == 1)
    check("record_malformed warning", "record_malformed" in m["warnings"])


# --- Candidate id determinism + sanitization ---------------------------------


def test_candidate_ids_deterministic_and_safe() -> None:
    vm = _manifest([_table_record(0, p, leaky=False) for p in (3, 4, 5)])
    m1 = build_table_candidates_manifest(vm)
    m2 = build_table_candidates_manifest(vm)
    ids = [c["candidate_id"] for c in m1["candidates"]]
    check("id prefix", CANDIDATE_ID_PREFIX == "table_candidate_")
    check("ids sequential", ids == ["table_candidate_0001", "table_candidate_0002", "table_candidate_0003"], str(ids))
    check("ids deterministic", ids == [c["candidate_id"] for c in m2["candidates"]])
    check("id carries no path/slug", all(_scan_for_leak(i) is None for i in ids))


def test_hostile_signal_values_coerced() -> None:
    rec = _table_record(
        0, 3, leaky=False,
        signals={
            "has_text_layer": "yes",        # non-bool → False
            "rows": "lots",                  # non-int → 0
            "columns": -4,                   # negative → 0
            "cell_text_count": 1.9,          # float → int(1)
            "numeric_cell_count": None,      # None → 0
            "header_cell_count": True,       # bool → 0 (not a count)
        },
    )
    m = build_table_candidates_manifest(_manifest([rec]))
    s = m["candidates"][0]["signals"]
    check("non-bool text layer → False", s["has_text_layer"] is False)
    check("non-int rows → 0", s["rows"] == 0)
    check("negative columns → 0", s["columns"] == 0)
    check("float cell_text → int floor", s["cell_text_count"] == 1)
    check("None numeric → 0", s["numeric_cell_count"] == 0)
    check("bool header → 0", s["header_cell_count"] == 0)
    check("confidence garbage → unknown",
          build_table_candidates_manifest(_manifest([_table_record(0, 3, leaky=False, confidence="bogus")]))
          ["candidates"][0]["confidence"] == "unknown")


def test_full_leaky_record_no_leak() -> None:
    # Every record carries the full hostile field set, in record + signals.
    vm = _manifest(
        [
            _table_record(0, 4, asset_type="grid_table",
                          signals={"has_text_layer": True, "rows": 3, "columns": 3,
                                   "cell_text_count": 9, "numeric_cell_count": 4, "header_cell_count": 3}),
            _table_record(1, 8, asset_type="table"),
            _nontable_record(2, 1),
        ]
    )
    m = build_table_candidates_manifest(vm)
    leak = _scan_for_leak(m)
    check("no leak in full manifest", leak is None, leak or "")
    serialized = json.dumps(m)
    check("no .pdf in serialized", ".pdf" not in serialized)
    check("no base64 marker", "base64" not in serialized)


# --- Defensive ceiling -------------------------------------------------------


def test_defensive_ceiling_partial() -> None:
    vm = _manifest([_table_record(0, 2, leaky=False) for _ in range(6)])
    m = build_table_candidates_manifest(vm, limit=2)
    check("ceiling truncates", m["summary"]["table_like_candidate_count"] == 2)
    check("ceiling → partial", m["status"] == "partial")
    check("max_items_applied warning", "max_items_applied" in m["warnings"])
    # default None keeps all (still bounded by internal hard ceiling, far above 6)
    m2 = build_table_candidates_manifest(vm)
    check("default keeps all", m2["summary"]["table_like_candidate_count"] == 6)
    check("default completed", m2["status"] == "completed")


# --- Policy bridge -----------------------------------------------------------


def test_policy_candidate_bridge() -> None:
    vm = _manifest(
        [
            _table_record(0, 4, asset_type="grid_table",
                          signals={"has_text_layer": True, "rows": 5, "columns": 3,
                                   "cell_text_count": 12, "numeric_cell_count": 6, "header_cell_count": 3},
                          confidence="high"),
        ]
    )
    m = build_table_candidates_manifest(vm)
    pol_cands = table_policy_candidates(m)
    check("one policy candidate", len(pol_cands) == 1)
    pc = pol_cands[0]
    check("policy candidate has kind token", pc["kind"] == "grid_table")
    check("policy candidate flat rows", pc["rows"] == 5)
    check("policy candidate has_text_layer", pc["has_text_layer"] is True)
    check("policy candidate page", pc["source_page"] == 4)
    check("policy candidate no leak", _scan_for_leak(pc) is None)
    check("bridge on non-dict → []", table_policy_candidates(None) == [])
    check("bridge on no-candidates → []", table_policy_candidates({"candidates": "x"}) == [])


# --- Writer ------------------------------------------------------------------


def test_writer_persists_exact_name() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        vm = _manifest([_table_record(0, 4, leaky=False, signals={"rows": 3, "columns": 3, "cell_text_count": 9})])
        manifest = write_table_candidates_manifest(job, vm)
        path = job.table_candidates_manifest_json
        check("filename constant", TABLE_CANDIDATES_MANIFEST_FILENAME == "table_candidates_manifest.json")
        check("file written", path.exists() and path.is_file())
        check("filename exact", path.name == TABLE_CANDIDATES_MANIFEST_FILENAME)
        check("under job dir", path.resolve().is_relative_to(job.dir.resolve()))
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        check("on-disk equals returned", on_disk == manifest)
        check("on-disk kind", on_disk["kind"] == "table_candidates_manifest")
        check("on-disk no leak", _scan_for_leak(on_disk) is None)
        # No clean.md was written by the artifact.
        check("no clean.md written", not job.clean_md.exists())


def test_writer_degrades_on_write_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)

        def _boom(*_a: Any, **_k: Any) -> Any:
            raise OSError("synthetic boom with private details")

        object.__setattr__(job, "save_text", _boom)  # frozen dataclass: bypass guard
        # Returns a manifest dict and never raises even though the disk write fails.
        m = write_table_candidates_manifest(job, _manifest([_table_record(0, 4, leaky=False)]))
        check("write failure still returns manifest", isinstance(m, dict) and m["kind"] == "table_candidates_manifest")
        check("write failure status completed", m["status"] == "completed")
        check("write failure no file", not job.table_candidates_manifest_json.exists())


def test_writer_handles_missing_manifest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        m = write_table_candidates_manifest(job, None)
        check("missing manifest → skipped artifact", m["status"] == "skipped")
        on_disk = json.loads(job.table_candidates_manifest_json.read_text(encoding="utf-8"))
        check("skipped persisted", on_disk["status"] == "skipped")
        check("skipped no leak", _scan_for_leak(on_disk) is None)


# --- Import hygiene (no provider/model/cloud) --------------------------------


def test_no_provider_or_network_imports() -> None:
    src = Path(__file__).resolve().parents[1] / "pipeline" / "table_candidate_manifest.py"
    text = src.read_text(encoding="utf-8")
    for forbidden in ("mistralai", "google.generativeai", "openai", "requests",
                      "urllib.request", "httpx", "socket", "chandra"):
        check(f"no import of {forbidden}", f"import {forbidden}" not in text and f"from {forbidden}" not in text)


def main() -> int:
    test_missing_and_malformed_inputs()
    test_empty_assets_completed_empty()
    test_table_like_records_become_candidates()
    test_table_token_variants_all_recognized()
    test_non_table_records_skipped_and_counted()
    test_missing_or_invalid_source_page_skipped()
    test_unsafe_records_skipped()
    test_malformed_record_skipped()
    test_candidate_ids_deterministic_and_safe()
    test_hostile_signal_values_coerced()
    test_full_leaky_record_no_leak()
    test_defensive_ceiling_partial()
    test_policy_candidate_bridge()
    test_writer_persists_exact_name()
    test_writer_degrades_on_write_failure()
    test_writer_handles_missing_manifest()
    test_no_provider_or_network_imports()
    print(f"\nTable candidate manifest tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
