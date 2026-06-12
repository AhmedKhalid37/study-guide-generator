#!/usr/bin/env python3
"""Focused tests for the Slice 47 ``visual_asset_scoring.json`` advisory artifact.

Run with:

    python test_scripts/test_visual_asset_scoring_artifact.py

No external APIs and no PyMuPDF/Tesseract/Mistral/Gemini/Chandra dependency: the
scoring core and its artifact writer are pure functions of an already-sanitized
manifest dict, so these tests feed plain dicts and write through a temp-dir Job.

The artifact is DERIVED from ``visual_assets_manifest.json``, advisory-only, never
mutates the source manifest, never changes guide output, and is reached ONLY by its
exact filename (deliberately NOT in the generic ARTIFACTS list / export bundles /
UI rows). The endpoint-mapping section is skipped automatically when FastAPI is not
importable in host Python (run in Docker for full coverage).
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|C:\\\\|\\\\\\\\)")
URLLIKE = re.compile(r"https?://")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z])")
DATAURI = re.compile(r"data:[a-z]+/[a-z0-9.+-]+;base64,", re.IGNORECASE)

from pipeline.visual_assets_manifest import build_visual_assets_manifest  # noqa: E402
from pipeline.visual_asset_scoring import (  # noqa: E402
    ARTIFACT_NAME,
    REPORT_KIND,
    REPORT_SOURCE,
    REPORT_VERSION,
    SKIP_REASON_MANIFEST_UNAVAILABLE,
    SKIP_REASON_SCORING_UNAVAILABLE,
    SKIP_REASON_WRITE_FAILED,
    score_visual_assets_manifest,
    write_skipped_visual_asset_scoring_report,
    write_visual_asset_scoring_report,
)
from pipeline.job_manager import Job  # noqa: E402


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


def _make_job(root: str, job_id: str = "job-vas") -> Job:
    job = Job(id=job_id, root=Path(root))
    job.input_dir.mkdir(parents=True, exist_ok=True)
    job.logs_dir.mkdir(parents=True, exist_ok=True)
    job._write_manifest({"id": job.id, "status": "created"})
    return job


def _scan_for_leak(node, path: str = "") -> str | None:
    """Recursively reject secret-like keys and path/url/credential/argv/base64 values."""
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in SECRET_KEY_NAMES:
                return f"{path}.{key} (secret-like field name)"
            # The scoring report must never carry an image reference at all.
            if str(key).lower() in {"image_ref", "caption", "source_text"}:
                return f"{path}.{key} (forbidden field in scoring report)"
            found = _scan_for_leak(value, f"{path}.{key}")
            if found:
                return found
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found = _scan_for_leak(value, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(node, str):
        if KEYLIKE.search(node):
            return f"{path} (value looks like a credential)"
        if PATHLIKE.search(node):
            return f"{path} (value looks like a filesystem path)"
        if URLLIKE.search(node):
            return f"{path} (value looks like a URL)"
        if ARGV_OR_SOCKET.search(node):
            return f"{path} (value looks like argv/socket)"
        if DATAURI.search(node):
            return f"{path} (value looks like a data URI / base64)"
    return None


def _rich_manifest() -> dict:
    """A completed manifest with a page-signal candidate + a hostile-ish figure.

    The figure record smuggles a caption / image_ref to prove they never survive
    into the scoring report.
    """
    sources = [{
        "filename": "lecture.pdf",
        "content_type": "application/pdf",
        "pages": [
            {"page": 1, "has_images": True, "image_object_count": 2,
             "page_width": 612, "page_height": 792, "classification": "mixed"},
            {"page": 2, "has_drawings": True, "drawing_object_count": 5,
             "page_width": 612, "page_height": 792, "classification": "embedded_text"},
        ],
    }]
    extracted = [{
        "asset_id": "fig_p001_01",
        "image_ref": "assets/fig_p001_01.png",
        "source_page": 1,
        "bbox": [10, 10, 400, 600],
        "signals": {"page_width": 612, "page_height": 792, "image_index": 0,
                    "crop_width_px": 390, "crop_height_px": 590},
    }]
    manifest = build_visual_assets_manifest(sources, extracted)
    # Inject forbidden fields onto the manifest assets to ensure they are dropped.
    for asset in manifest["assets"]:
        asset["caption"] = "Figure 1: secret /home/op/private.pdf caption text"
    return manifest


# --- completed write ---------------------------------------------------------


def test_writes_completed_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        manifest = _rich_manifest()
        report = write_visual_asset_scoring_report(job, manifest)

        check("returns a dict", isinstance(report, dict))
        check("status completed", report.get("status") == "completed")
        check("version constant", report.get("version") == REPORT_VERSION)
        check("kind constant", report.get("kind") == REPORT_KIND)
        check("source is the manifest", report.get("source") == REPORT_SOURCE)
        check("artifact name constant", ARTIFACT_NAME == "visual_asset_scoring.json")

        path = job.visual_asset_scoring_json
        check("artifact file written", path.exists() and path.is_file())
        check("artifact filename exact", path.name == "visual_asset_scoring.json")

        on_disk = json.loads(path.read_text(encoding="utf-8"))
        check("on-disk equals returned report", on_disk == report)

        scores = on_disk.get("scores")
        check("scores is a list", isinstance(scores, list))
        check("one score per manifest asset",
              len(scores) == len(manifest["assets"]) == 3)

        summary = on_disk.get("summary", {})
        check("summary asset_count matches", summary.get("asset_count") == len(scores))
        total = (summary.get("high_priority_count", 0)
                 + summary.get("medium_priority_count", 0)
                 + summary.get("low_priority_count", 0)
                 + summary.get("unknown_priority_count", 0))
        check("summary priority counts sum to asset_count", total == len(scores))

        check("warnings is a list", isinstance(on_disk.get("warnings"), list))


def test_recommended_action_stays_unknown() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        report = write_visual_asset_scoring_report(job, _rich_manifest())
        actions = {s.get("recommended_action") for s in report["scores"]}
        check("every recommended_action is unknown", actions == {"unknown"})


# --- no-leak -----------------------------------------------------------------


def test_no_leak_in_artifact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        write_visual_asset_scoring_report(job, _rich_manifest())
        on_disk = json.loads(job.visual_asset_scoring_json.read_text(encoding="utf-8"))
        leak = _scan_for_leak(on_disk)
        check("no caption/image_ref/path/url/base64 leak in artifact", leak is None, leak or "")
        raw = job.visual_asset_scoring_json.read_text(encoding="utf-8")
        check("raw caption text absent from artifact bytes", "secret" not in raw)
        check("image_ref string absent from artifact bytes", "assets/" not in raw)


# --- manifest is not mutated -------------------------------------------------


def test_does_not_mutate_manifest_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        manifest = _rich_manifest()
        # Persist the manifest first (as run_llm_job does), capture exact bytes.
        manifest_path = job.visual_assets_manifest_json
        job.save_text(manifest_path, json.dumps(manifest, indent=2) + "\n")
        before = manifest_path.read_bytes()
        before_obj = json.loads(before.decode("utf-8"))

        write_visual_asset_scoring_report(job, before_obj)

        after = manifest_path.read_bytes()
        check("manifest file bytes unchanged", before == after)
        check("manifest dict unchanged in memory", json.loads(after.decode("utf-8")) == before_obj)


def test_integration_manifest_then_scoring() -> None:
    """Mirror the run_llm_job sequence: write manifest, read it back, score it."""
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        manifest = _rich_manifest()
        job.save_text(job.visual_assets_manifest_json,
                      json.dumps(manifest, indent=2) + "\n")
        # Read back the persisted (sanitized) manifest, exactly like run_llm_job.
        loaded = json.loads(job.visual_assets_manifest_json.read_text(encoding="utf-8"))
        report = write_visual_asset_scoring_report(job, loaded)

        check("both artifacts present after sequence",
              job.visual_assets_manifest_json.exists()
              and job.visual_asset_scoring_json.exists())
        check("scoring derived from persisted manifest is completed",
              report.get("status") == "completed")
        check("scoring score count matches manifest assets",
              len(report["scores"]) == len(loaded["assets"]))


# --- degrade-not-fail --------------------------------------------------------


def test_skipped_on_unavailable_manifest() -> None:
    cases = {
        "none": None,
        "empty_dict": {},
        "skipped_manifest": {"status": "skipped", "reason": "manifest_unavailable"},
        "assets_not_list": {"status": "completed", "assets": {}},
        "not_a_dict": [1, 2, 3],
    }
    for label, manifest in cases.items():
        with tempfile.TemporaryDirectory() as tmp:
            job = _make_job(tmp)
            report = write_visual_asset_scoring_report(job, manifest)
            check(f"skipped status for {label}", report.get("status") == "skipped")
            check(f"skipped reason manifest_unavailable for {label}",
                  report.get("reason") == SKIP_REASON_MANIFEST_UNAVAILABLE)
            on_disk = json.loads(job.visual_asset_scoring_json.read_text(encoding="utf-8"))
            check(f"skipped artifact persisted for {label}", on_disk == report)
            check(f"skipped scores empty for {label}", on_disk.get("scores") == [])
            check(f"skipped no leak for {label}", _scan_for_leak(on_disk) is None)


class _FailingJob(Job):
    """A Job whose save_text always raises — to exercise the degrade path.

    ``Job`` is a frozen dataclass, so we cannot rebind ``save_text`` on an
    instance; overriding it on a subclass is the clean, non-brittle way to force
    a write failure without touching the real filesystem behaviour.
    """

    def save_text(self, path, text):  # type: ignore[override]
        raise OSError("simulated write failure")


def test_skipped_on_write_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _FailingJob(id="job-fail", root=Path(tmp))
        job.input_dir.mkdir(parents=True, exist_ok=True)
        job.logs_dir.mkdir(parents=True, exist_ok=True)

        report = write_visual_asset_scoring_report(job, _rich_manifest())
        check("write failure degrades to skipped", report.get("status") == "skipped")
        check("write failure reason write_failed",
              report.get("reason") == SKIP_REASON_WRITE_FAILED)
        check("write failure report carries no raw exception text",
              "simulated write failure" not in json.dumps(report))
        check("no artifact left on disk after write failure",
              not job.visual_asset_scoring_json.exists())


def test_explicit_skipped_writer_defaults() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        report = write_skipped_visual_asset_scoring_report(job)
        check("explicit skipped status", report.get("status") == "skipped")
        check("explicit skipped default reason",
              report.get("reason") == SKIP_REASON_SCORING_UNAVAILABLE)
        check("explicit skipped persisted",
              json.loads(job.visual_asset_scoring_json.read_text(encoding="utf-8")) == report)
        # An out-of-vocabulary reason coerces to the safe default.
        report2 = write_skipped_visual_asset_scoring_report(
            job, reason="something_raw_and_unsafe", safe_message="x")
        check("unknown reason coerced to closed default",
              report2.get("reason") == SKIP_REASON_SCORING_UNAVAILABLE)


def test_malformed_manifest_scores_safely() -> None:
    # score_visual_assets_manifest itself must never raise on a malformed dict.
    report = score_visual_assets_manifest({"status": "completed", "assets": "nope"})
    check("malformed manifest scores to completed", report.get("status") == "completed")
    check("malformed manifest has manifest_malformed warning",
          "manifest_malformed" in report.get("warnings", []))


# --- exact-name route mapping + no generic exposure --------------------------


def test_artifact_route_mapping_and_no_generic_exposure() -> None:
    try:
        from api import server  # noqa: WPS433
    except Exception as exc:  # FastAPI / deps not importable in host python
        print(f"[SKIP] api.server endpoint section ({type(exc).__name__})")
        return

    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)

        # Exact-name path resolves to the job's scoring artifact path.
        path, media = server._artifact_path(job, "visual_asset_scoring.json")
        check("exact-name path resolves", path == job.visual_asset_scoring_json)
        check("exact-name media type json", media == "application/json")

        # NOT in the generic ARTIFACTS registry.
        check("not in ARTIFACTS", "visual_asset_scoring.json" not in server.ARTIFACTS)
        check("not in EXPORT_ARTIFACTS",
              "visual_asset_scoring.json" not in server.EXPORT_ARTIFACTS)

        # NOT surfaced by the generic URL / details builders.
        availability = server._artifact_availability(job)
        urls = server._artifact_urls(job, availability)
        check("not in _artifact_urls", "visual_asset_scoring.json" not in urls)
        details_names = {
            d.get("name") for d in server._artifact_details(job, availability)
        }
        check("not in _artifact_details", "visual_asset_scoring.json" not in details_names)

        # Graceful behaviour when the artifact is absent: the path maps but the file
        # does not exist, so the get_artifact route returns its standard 404.
        check("artifact absent before any write",
              not job.visual_asset_scoring_json.exists())


def main() -> int:
    test_writes_completed_report()
    test_recommended_action_stays_unknown()
    test_no_leak_in_artifact()
    test_does_not_mutate_manifest_file()
    test_integration_manifest_then_scoring()
    test_skipped_on_unavailable_manifest()
    test_skipped_on_write_failure()
    test_explicit_skipped_writer_defaults()
    test_malformed_manifest_scores_safely()
    test_artifact_route_mapping_and_no_generic_exposure()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
