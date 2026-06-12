#!/usr/bin/env python3
"""Focused tests for the Slice 49 ``visual_replacement_plan.json`` advisory artifact.

Run with:

    python test_scripts/test_visual_replacement_plan_artifact.py

No external APIs and no PyMuPDF/Tesseract/Mistral/Gemini/Chandra dependency: the
replacement planner and its artifact writer are pure functions of an already-
sanitized ``visual_asset_scoring.json``-shaped report (with an optional presence-only
``visual_assets_manifest.json`` cross-check), so these tests feed plain dicts and
write through a temp-dir Job.

The artifact is DERIVED from ``visual_asset_scoring.json``, advisory-only, never
mutates the source scoring report or manifest, never changes guide output, makes no
production include/omit decision, and is reached ONLY by its exact filename
(deliberately NOT in the generic ARTIFACTS list / export bundles / UI rows). The
endpoint-mapping section is skipped automatically when FastAPI is not importable in
host Python (run in Docker for full coverage).
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

from pipeline.visual_asset_scoring import (  # noqa: E402
    score_visual_assets_manifest,
    write_visual_asset_scoring_report,
)
from pipeline.visual_assets_manifest import build_visual_assets_manifest  # noqa: E402
from pipeline.visual_replacement_planner import (  # noqa: E402
    ARTIFACT_NAME,
    REPORT_KIND,
    REPORT_SOURCE,
    REPORT_VERSION,
    SKIP_REASON_PLANNING_UNAVAILABLE,
    SKIP_REASON_SCORING_UNAVAILABLE,
    SKIP_REASON_WRITE_FAILED,
    build_visual_replacement_plan,
    write_skipped_visual_replacement_plan_report,
    write_visual_replacement_plan_report,
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


def _make_job(root: str, job_id: str = "job-vrp") -> Job:
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
            # The replacement plan must never carry an image ref / caption / source.
            if str(key).lower() in {"image_ref", "caption", "source_text"}:
                return f"{path}.{key} (forbidden field in replacement plan)"
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
    """A completed manifest with a page-signal candidate + a hostile-ish figure."""
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
    for asset in manifest["assets"]:
        asset["caption"] = "Figure 1: secret /home/op/private.pdf caption text"
    return manifest


def _scoring_report_from_manifest(manifest: dict) -> dict:
    """Produce a real ``visual_asset_scoring.json``-shaped report from a manifest."""
    return score_visual_assets_manifest(manifest)


def _hostile_scoring_report() -> dict:
    """A completed scoring report whose items smuggle forbidden fields + a chandra item."""
    return {
        "version": 1,
        "kind": "visual_asset_scoring",
        "status": "completed",
        "source": "visual_assets_manifest.json",
        "scores": [
            {
                "asset_id": "fig_p001_01",
                "source_page": 1,
                "source_provider": "fitz_local",
                "asset_type": "extracted_figure",
                "recommended_action": "unknown",
                "priority": "high",
                "include_score": 0.8,
                # forbidden smuggled fields the plan must NOT echo:
                "caption": "secret /home/op/private.pdf caption",
                "image_ref": "assets/fig_p001_01.png",
                "source_text": "raw OCR body text https://evil.example/x",
                "reasons": [],
                "warnings": [],
            },
            {
                "asset_id": "chandra_p002_01",
                "source_page": 2,
                "source_provider": "chandra_local",
                "asset_type": "table",
                "recommended_action": "unknown",
                "priority": "medium",
                "include_score": 0.55,
                "reasons": [],
                "warnings": [],
            },
        ],
        "summary": {},
        "warnings": [],
    }


# --- completed write ---------------------------------------------------------


def test_writes_completed_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        manifest = _rich_manifest()
        scoring = _scoring_report_from_manifest(manifest)
        report = write_visual_replacement_plan_report(job, scoring, manifest=manifest)

        check("returns a dict", isinstance(report, dict))
        check("status completed", report.get("status") == "completed")
        check("version constant", report.get("version") == REPORT_VERSION)
        check("kind constant", report.get("kind") == REPORT_KIND)
        check("source is the scoring report", report.get("source") == REPORT_SOURCE)
        check("source equals visual_asset_scoring.json",
              report.get("source") == "visual_asset_scoring.json")
        check("artifact name constant", ARTIFACT_NAME == "visual_replacement_plan.json")

        path = job.visual_replacement_plan_json
        check("artifact file written", path.exists() and path.is_file())
        check("artifact filename exact", path.name == "visual_replacement_plan.json")

        on_disk = json.loads(path.read_text(encoding="utf-8"))
        check("on-disk equals returned report", on_disk == report)

        items = on_disk.get("items")
        check("items is a list", isinstance(items, list))
        check("one item per scoring score",
              len(items) == len(scoring["scores"]) == 3)


def test_completed_shape_and_summary_counts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        report = write_visual_replacement_plan_report(job, _hostile_scoring_report())
        items = report["items"]
        summary = report["summary"]
        check("summary item_count matches", summary.get("item_count") == len(items))
        total = (summary.get("candidate_include_as_figure_count", 0)
                 + summary.get("candidate_convert_to_table_count", 0)
                 + summary.get("candidate_summarize_as_text_count", 0)
                 + summary.get("review_only_count", 0)
                 + summary.get("unknown_count", 0))
        check("summary action counts sum to item_count", total == len(items))
        # The high-priority figure → candidate_include_as_figure.
        fig = next(i for i in items if i["asset_id"] == "fig_p001_01")
        check("figure item is include_as_figure",
              fig["candidate_action"] == "candidate_include_as_figure")


def test_candidate_actions_are_advisory_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        report = write_visual_replacement_plan_report(job, _hostile_scoring_report())
        allowed = {
            "candidate_include_as_figure",
            "candidate_convert_to_table",
            "candidate_summarize_as_text",
            "review_only",
            "unknown",
        }
        actions = {i.get("candidate_action") for i in report["items"]}
        check("every candidate_action is advisory only", actions <= allowed,
              str(actions - allowed))


def test_chandra_item_blocked_and_advisory() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        report = write_visual_replacement_plan_report(job, _hostile_scoring_report())
        chandra = next(i for i in report["items"] if i["asset_id"] == "chandra_p002_01")
        check("chandra item carries chandra_blocked reason",
              "chandra_blocked" in chandra.get("reasons", []))
        check("chandra item stays advisory (candidate_*/review_only/unknown)",
              chandra["candidate_action"].startswith("candidate_")
              or chandra["candidate_action"] in {"review_only", "unknown"})


# --- no-leak -----------------------------------------------------------------


def test_no_leak_in_artifact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        manifest = _rich_manifest()
        write_visual_replacement_plan_report(
            job, _hostile_scoring_report(), manifest=manifest)
        on_disk = json.loads(job.visual_replacement_plan_json.read_text(encoding="utf-8"))
        leak = _scan_for_leak(on_disk)
        check("no caption/image_ref/path/url/base64 leak in artifact", leak is None,
              leak or "")
        raw = job.visual_replacement_plan_json.read_text(encoding="utf-8")
        check("raw caption text absent from artifact bytes", "secret" not in raw)
        check("image_ref string absent from artifact bytes", "assets/" not in raw)
        check("raw source/OCR text absent from artifact bytes", "OCR body" not in raw)


def test_no_image_ref_field_in_items() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        report = write_visual_replacement_plan_report(job, _hostile_scoring_report())
        for item in report["items"]:
            check(f"item {item['asset_id']} has no image_ref",
                  "image_ref" not in item)
            check(f"item {item['asset_id']} has no caption", "caption" not in item)


# --- inputs are not mutated --------------------------------------------------


def test_does_not_mutate_scoring_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        scoring = _hostile_scoring_report()
        before = json.dumps(scoring, sort_keys=True)
        write_visual_replacement_plan_report(job, scoring)
        after = json.dumps(scoring, sort_keys=True)
        check("scoring report dict unchanged in memory", before == after)


def test_does_not_mutate_scoring_or_manifest_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        manifest = _rich_manifest()
        scoring = _scoring_report_from_manifest(manifest)
        # Persist both upstream artifacts first (as run_llm_job does).
        job.save_text(job.visual_assets_manifest_json,
                      json.dumps(manifest, indent=2) + "\n")
        job.save_text(job.visual_asset_scoring_json,
                      json.dumps(scoring, indent=2, sort_keys=True) + "\n")
        manifest_before = job.visual_assets_manifest_json.read_bytes()
        scoring_before = job.visual_asset_scoring_json.read_bytes()

        write_visual_replacement_plan_report(
            job,
            json.loads(scoring_before.decode("utf-8")),
            manifest=json.loads(manifest_before.decode("utf-8")),
        )

        check("manifest file bytes unchanged",
              manifest_before == job.visual_assets_manifest_json.read_bytes())
        check("scoring file bytes unchanged",
              scoring_before == job.visual_asset_scoring_json.read_bytes())


def test_integration_manifest_then_scoring_then_plan() -> None:
    """Mirror the run_llm_job sequence: manifest → scoring → replacement plan."""
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        manifest = _rich_manifest()
        job.save_text(job.visual_assets_manifest_json,
                      json.dumps(manifest, indent=2) + "\n")
        loaded_manifest = json.loads(
            job.visual_assets_manifest_json.read_text(encoding="utf-8"))
        scoring = write_visual_asset_scoring_report(job, loaded_manifest)
        plan = write_visual_replacement_plan_report(
            job, scoring, manifest=loaded_manifest)

        check("all three artifacts present after sequence",
              job.visual_assets_manifest_json.exists()
              and job.visual_asset_scoring_json.exists()
              and job.visual_replacement_plan_json.exists())
        check("plan derived from scoring is completed",
              plan.get("status") == "completed")
        check("plan item count matches scoring score count",
              len(plan["items"]) == len(scoring["scores"]))
        # Presence-only manifest cross-check should mark the matched figure.
        fig = next(i for i in plan["items"] if i["asset_id"] == "fig_p001_01")
        check("matched figure carries has_manifest_match reason",
              "has_manifest_match" in fig.get("reasons", []))


# --- degrade-not-fail --------------------------------------------------------


def test_skipped_on_unavailable_scoring() -> None:
    cases = {
        "none": None,
        "empty_dict": {},
        "skipped_scoring": {"status": "skipped", "reason": "visual_manifest_unavailable",
                            "scores": []},
        "scores_not_list": {"status": "completed", "scores": {}},
        "not_a_dict": [1, 2, 3],
    }
    for label, scoring in cases.items():
        with tempfile.TemporaryDirectory() as tmp:
            job = _make_job(tmp)
            report = write_visual_replacement_plan_report(job, scoring)
            check(f"skipped status for {label}", report.get("status") == "skipped")
            check(f"skipped reason scoring_unavailable for {label}",
                  report.get("reason") == SKIP_REASON_SCORING_UNAVAILABLE)
            on_disk = json.loads(
                job.visual_replacement_plan_json.read_text(encoding="utf-8"))
            check(f"skipped artifact persisted for {label}", on_disk == report)
            check(f"skipped items empty for {label}", on_disk.get("items") == [])
            check(f"skipped no leak for {label}", _scan_for_leak(on_disk) is None)


class _FailingJob(Job):
    """A Job whose save_text always raises — to exercise the degrade path."""

    def save_text(self, path, text):  # type: ignore[override]
        raise OSError("simulated write failure")


def test_skipped_on_write_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _FailingJob(id="job-fail", root=Path(tmp))
        job.input_dir.mkdir(parents=True, exist_ok=True)
        job.logs_dir.mkdir(parents=True, exist_ok=True)

        report = write_visual_replacement_plan_report(job, _hostile_scoring_report())
        check("write failure degrades to skipped", report.get("status") == "skipped")
        check("write failure reason write_failed",
              report.get("reason") == SKIP_REASON_WRITE_FAILED)
        check("write failure report carries no raw exception text",
              "simulated write failure" not in json.dumps(report))
        check("no artifact left on disk after write failure",
              not job.visual_replacement_plan_json.exists())


def test_explicit_skipped_writer_defaults() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        report = write_skipped_visual_replacement_plan_report(job)
        check("explicit skipped status", report.get("status") == "skipped")
        check("explicit skipped default reason",
              report.get("reason") == SKIP_REASON_PLANNING_UNAVAILABLE)
        check("explicit skipped persisted",
              json.loads(job.visual_replacement_plan_json.read_text(encoding="utf-8"))
              == report)
        # An out-of-vocabulary reason coerces to the safe default.
        report2 = write_skipped_visual_replacement_plan_report(
            job, reason="something_raw_and_unsafe", safe_message="x")
        check("unknown reason coerced to closed default",
              report2.get("reason") == SKIP_REASON_PLANNING_UNAVAILABLE)


def test_malformed_scoring_plans_safely() -> None:
    # build_visual_replacement_plan itself must never raise on a malformed dict.
    report = build_visual_replacement_plan({"status": "completed", "scores": "nope"})
    check("malformed scoring plans to completed", report.get("status") == "completed")
    check("malformed scoring has scoring_report_malformed warning",
          "scoring_report_malformed" in report.get("warnings", []))


# --- exact-name route mapping + no generic exposure --------------------------


def test_artifact_route_mapping_and_no_generic_exposure() -> None:
    try:
        from api import server  # noqa: WPS433
    except Exception as exc:  # FastAPI / deps not importable in host python
        print(f"[SKIP] api.server endpoint section ({type(exc).__name__})")
        return

    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)

        # Exact-name path resolves to the job's replacement-plan artifact path.
        path, media = server._artifact_path(job, "visual_replacement_plan.json")
        check("exact-name path resolves", path == job.visual_replacement_plan_json)
        check("exact-name media type json", media == "application/json")

        # NOT in the generic ARTIFACTS registry.
        check("not in ARTIFACTS", "visual_replacement_plan.json" not in server.ARTIFACTS)
        check("not in EXPORT_ARTIFACTS",
              "visual_replacement_plan.json" not in server.EXPORT_ARTIFACTS)

        # NOT surfaced by the generic URL / details builders.
        availability = server._artifact_availability(job)
        urls = server._artifact_urls(job, availability)
        check("not in _artifact_urls", "visual_replacement_plan.json" not in urls)
        details_names = {
            d.get("name") for d in server._artifact_details(job, availability)
        }
        check("not in _artifact_details",
              "visual_replacement_plan.json" not in details_names)

        # Graceful behaviour when the artifact is absent: the path maps but the file
        # does not exist, so the get_artifact route returns its standard 404.
        check("artifact absent before any write",
              not job.visual_replacement_plan_json.exists())


def main() -> int:
    test_writes_completed_report()
    test_completed_shape_and_summary_counts()
    test_candidate_actions_are_advisory_only()
    test_chandra_item_blocked_and_advisory()
    test_no_leak_in_artifact()
    test_no_image_ref_field_in_items()
    test_does_not_mutate_scoring_report()
    test_does_not_mutate_scoring_or_manifest_files()
    test_integration_manifest_then_scoring_then_plan()
    test_skipped_on_unavailable_scoring()
    test_skipped_on_write_failure()
    test_explicit_skipped_writer_defaults()
    test_malformed_scoring_plans_safely()
    test_artifact_route_mapping_and_no_generic_exposure()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
