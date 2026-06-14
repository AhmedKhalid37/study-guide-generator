#!/usr/bin/env python3
"""Focused tests for the ``table_reconstruction_policy.json`` artifact writer (Slice 92).

Run with:

    python test_scripts/test_table_reconstruction_policy_artifact.py

Synthetic dictionaries and temp job directories only. No PDFs, images, providers,
renderers, OCR engines, or model calls are required. The writer feeds the Slice 92
sanitized table-candidate manifest into the pure Slice 85 policy core
(``pipeline.table_reconstruction_policy.build_table_reconstruction_policy``) and
persists the result as a safe exact-name artifact. A table is never inserted as a
screenshot: ``screenshot_insert_count`` is always ``0``.
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
    "sk_tablepolicyartifact1234567890",
    "synthetic boom with private details",
]

from pipeline.job_manager import Job  # noqa: E402
from pipeline.table_reconstruction_policy_artifact import (  # noqa: E402
    TABLE_RECONSTRUCTION_POLICY_FILENAME,
    write_table_reconstruction_policy,
)
from pipeline.table_candidate_manifest import build_table_candidates_manifest  # noqa: E402


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


def _make_job(root: str, job_id: str = "job-table-policy") -> Job:
    job = Job(id=job_id, root=Path(root))
    job.input_dir.mkdir(parents=True, exist_ok=True)
    job.logs_dir.mkdir(parents=True, exist_ok=True)
    job._write_manifest({"id": job.id, "status": "created"})
    return job


def _leaky_fields() -> dict[str, Any]:
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
        "api_key": "sk_tablepolicyartifact1234567890",
        "asset_id": "page_0004_visual_01",
    }


def _table_record(source_index: int, source_page: Any, asset_type: str, signals: dict[str, Any] | None,
                  *, confidence: Any = None, leaky: bool = True) -> dict[str, Any]:
    rec: dict[str, Any] = dict(_leaky_fields()) if leaky else {}
    rec.update({"asset_type": asset_type, "source_index": source_index})
    if source_page is not None:
        rec["source_page"] = source_page
    if signals is not None:
        rec["signals"] = dict(signals)
    if confidence is not None:
        rec["confidence"] = confidence
    return rec


def _manifest(assets: list[Any], status: str = "completed") -> dict[str, Any]:
    return {"version": 1, "kind": "visual_assets_manifest", "status": status, "assets": assets}


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


def _read_policy(job: Job) -> dict[str, Any]:
    return json.loads(job.table_reconstruction_policy_json.read_text(encoding="utf-8"))


def test_writes_policy_from_manifest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        vm = _manifest(
            [
                _table_record(0, 4, "grid_table",
                              {"has_text_layer": True, "rows": 5, "columns": 3,
                               "cell_text_count": 12, "numeric_cell_count": 6, "header_cell_count": 3},
                              confidence="high"),
                _table_record(0, 7, "dense_table",
                              {"has_text_layer": False, "rows": 9, "columns": 4, "cell_text_count": 30}),
            ]
        )
        policy = write_table_reconstruction_policy(job, vm)
        path = job.table_reconstruction_policy_json
        check("filename constant", TABLE_RECONSTRUCTION_POLICY_FILENAME == "table_reconstruction_policy.json")
        check("file written", path.exists() and path.is_file())
        check("filename exact", path.name == TABLE_RECONSTRUCTION_POLICY_FILENAME)
        check("under job dir", path.resolve().is_relative_to(job.dir.resolve()))
        check("policy kind", policy.get("kind") == "table_reconstruction_policy", str(policy))
        check("policy status completed", policy.get("status") == "completed", str(policy))
        on_disk = _read_policy(job)
        check("on-disk equals returned", on_disk == policy)
        check("two policy items", on_disk["summary"]["policy_item_count"] == 2, str(on_disk["summary"]))
        check("screenshot_insert_count == 0", on_disk["summary"]["screenshot_insert_count"] == 0)
        actions = [i["action"] for i in on_disk["items"]]
        check("grid w/ text → reconstruct_with_original", actions[0] == "reconstruct_with_original", str(actions))
        check("dense no text → simplify_only", actions[1] == "simplify_only", str(actions))
        check("no clean.md written", not job.clean_md.exists())
        check("no leak in policy artifact", _scan_for_leak(on_disk) is None, _scan_for_leak(on_disk) or "")


def test_accepts_prebuilt_candidate_manifest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        vm = _manifest([_table_record(0, 3, "table", {"rows": 2, "columns": 2, "cell_text_count": 4}, leaky=False)])
        prebuilt = build_table_candidates_manifest(vm)
        policy = write_table_reconstruction_policy(job, table_candidates_manifest=prebuilt)
        check("policy from prebuilt", policy["status"] in {"completed", "partial"})
        check("one item", policy["summary"]["policy_item_count"] == 1, str(policy["summary"]))
        check("screenshot count 0 (prebuilt)", policy["summary"]["screenshot_insert_count"] == 0)


def test_missing_and_skipped_inputs_degrade() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        policy = write_table_reconstruction_policy(job, None)
        check("missing manifest → skipped", policy["status"] == "skipped", str(policy))
        check("skipped persisted", _read_policy(job)["status"] == "skipped")
        check("skipped screenshot count 0", _read_policy(job)["summary"]["screenshot_insert_count"] == 0)
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        policy = write_table_reconstruction_policy(job, {"status": "skipped"})
        check("skipped manifest → skipped policy", policy["status"] == "skipped")
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        policy = write_table_reconstruction_policy(job, 12345)
        check("malformed manifest → skipped policy", policy["status"] == "skipped")
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        # Empty assets → no candidates → completed policy with zero items.
        policy = write_table_reconstruction_policy(job, _manifest([]))
        check("empty assets → completed, 0 items", policy["status"] == "completed" and policy["summary"]["policy_item_count"] == 0, str(policy["summary"]))


def test_non_table_only_manifest_no_items() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        vm = _manifest(
            [
                {"asset_type": "page_visual_signal", "source_index": 0, "source_page": 1, "signals": {}},
                {"asset_type": "extracted_figure", "source_index": 0, "source_page": 2, "signals": {}},
            ]
        )
        policy = write_table_reconstruction_policy(job, vm)
        check("no table candidates → 0 policy items", policy["summary"]["policy_item_count"] == 0, str(policy["summary"]))
        check("status completed", policy["status"] == "completed")
        check("screenshot count 0", policy["summary"]["screenshot_insert_count"] == 0)


def test_writer_degrades_on_write_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)

        def _boom(*_a: Any, **_k: Any) -> Any:
            raise OSError("synthetic boom with private details")

        object.__setattr__(job, "save_text", _boom)  # frozen dataclass: bypass guard
        vm = _manifest([_table_record(0, 4, "grid_table", {"rows": 3, "columns": 3, "cell_text_count": 9}, leaky=False)])
        policy = write_table_reconstruction_policy(job, vm)
        check("write failure still returns policy", isinstance(policy, dict) and policy["kind"] == "table_reconstruction_policy")
        check("write failure no file", not job.table_reconstruction_policy_json.exists())
        check("write failure screenshot count 0", policy["summary"]["screenshot_insert_count"] == 0)


def test_full_leaky_manifest_no_leak() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        vm = _manifest(
            [
                _table_record(0, 4, "grid_table",
                              {"has_text_layer": True, "rows": 5, "columns": 3,
                               "cell_text_count": 12, "numeric_cell_count": 6, "header_cell_count": 3},
                              confidence="high"),
                _table_record(1, 8, "table", {"rows": 2, "columns": 2}),
            ]
        )
        write_table_reconstruction_policy(job, vm)
        on_disk = _read_policy(job)
        leak = _scan_for_leak(on_disk)
        check("no leak in full policy artifact", leak is None, leak or "")
        serialized = json.dumps(on_disk)
        check("no .pdf in serialized", ".pdf" not in serialized)
        check("no base64 marker", "base64" not in serialized)


def test_no_provider_or_network_imports() -> None:
    src = Path(__file__).resolve().parents[1] / "pipeline" / "table_reconstruction_policy_artifact.py"
    text = src.read_text(encoding="utf-8")
    for forbidden in ("mistralai", "google.generativeai", "openai", "requests",
                      "urllib.request", "httpx", "socket", "chandra"):
        check(f"no import of {forbidden}", f"import {forbidden}" not in text and f"from {forbidden}" not in text)


def main() -> int:
    test_writes_policy_from_manifest()
    test_accepts_prebuilt_candidate_manifest()
    test_missing_and_skipped_inputs_degrade()
    test_non_table_only_manifest_no_items()
    test_writer_degrades_on_write_failure()
    test_full_leaky_manifest_no_leak()
    test_no_provider_or_network_imports()
    print(f"\nTable reconstruction policy artifact tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
