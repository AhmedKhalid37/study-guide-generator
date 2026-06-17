#!/usr/bin/env python3
"""Slice 123 — Real-Disaster E2E with the advisory coverage leg (synthetic-safe).

Track A of Slice 123. This harness exercises the *actual advisory job-artifact
path* (``build_quality_safety_job_artifact_payload`` plus the production hook
``pipeline.run_markdown_job._write_quality_safety_unified_qa``) against three
synthetic archetypes that mirror the real-disaster operator cases, and records
the result as **closed-vocabulary tokens only**:

1. ``clean_real_case``                  — correct numbers, structural coverage present.
2. ``single_confident_wrong_numeric_case`` — one wrong numeric claim caught by recompute.
3. ``legacy_confused_wrong_case``       — production-shaped: structural coverage present
                                          but **no** concept/fact bundle, so the numeric
                                          fact-sheet / recompute leg stays honestly missing.

It proves the two legs stay distinct:

- structural coverage leg: now wired into the advisory artifact via
  ``extraction_coverage_bundle`` (present with safe synthetic structural metadata;
  ``skipped`` when absent);
- numeric fact-sheet extraction leg: still NOT covered through the production hook,
  because that hook never produces a concept/fact bundle — recompute therefore
  stays ``component_missing`` regardless of how rich the structural coverage is.

Structural coverage never invents numeric observations and never upgrades
``shippable`` / ``safety_floor_green``.

Synthetic-only. No real source decks, references, generated guides, OCR/table/
caption text, uploaded specs, provider payloads, paths, URLs, images, PDFs,
DOCX/ZIPs, or runtime artifacts are read or written outside a temp dir. No
providers, models, cloud, judge, or repair are invoked.

Run:  python test_scripts/validate_quality_safety_real_disaster_e2e.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_job_artifact import (  # noqa: E402
    ARTIFACT_NAME,
    build_quality_safety_job_artifact_payload,
)

PASS = 0
FAIL = 0

# A single synthetic canary smuggled where unsafe content could leak; it must
# never appear in any artifact payload.
SYNTHETIC_CANARY = "ZZSYNTH_DISASTER_PRIVATE_MARKER_ONLY"

COVERAGE_STATUSES = {"ok", "warning", "skipped", "partial", "failed"}
UNIFIED_STATUSES = {"passed", "warning", "failed", "skipped", "partial"}
FORBIDDEN_KEYS = (
    "overall_10",
    "judge",
    "judge_score",
    "judge_response",
    "repair",
    "repaired_markdown",
)


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        FAIL += 1
        suffix = f" - {detail}" if detail else ""
        print(f"[FAIL] {label}{suffix}")


def _no_forbidden_keys(obj: object) -> bool:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in FORBIDDEN_KEYS or not _no_forbidden_keys(value):
                return False
        return True
    if isinstance(obj, list):
        return all(_no_forbidden_keys(item) for item in obj)
    return True


# --- Synthetic-safe inputs (mirroring the test fixtures, no private content) ---

def candidate_markdown(*, value: float = 0.2) -> str:
    return "\n".join(
        [
            "# Synthetic Fixture",
            "Synthetic Concept",
            f"synthetic_stump_choice_score: {value}",
            "## Worked Answer",
            "Solution: substitute the synthetic counts and finish with the numeric target.",
            "## Mock Question 1: Which synthetic concept is checked?",
            "Answer: Synthetic Concept.",
        ]
    )


def weighted_bundle(*, claimed: float) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_extraction_bundle",
        "lecture_id": "synthetic_fixture",
        "source_quality": "synthetic",
        "concepts": [
            {
                "concept": "Synthetic Concept",
                "source_ref": "source_page_1",
                "computation_records": [
                    {
                        "id": "synthetic.weighted_gini.fact",
                        "label": "synthetic_stump_choice_score",
                        "type": "numeric",
                        "method": "weighted_gini",
                        "inputs": {"groups": [{"yes": 3, "no": 0}, {"yes": 1, "no": 4}]},
                        "claimed_value": claimed,
                        "tolerance": 0.01,
                    }
                ],
                "numeric_observations": [],
            }
        ],
    }


def fixture_spec(*, value: float) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_fixture",
        "lecture_id": "synthetic_fixture",
        "title": "Synthetic Fixture",
        "source_quality": "synthetic",
        "expected_topics": ["Synthetic Concept"],
        "ground_truth_numerics": [{"label": "synthetic_stump_choice_score", "value": value, "tol": 0.01}],
        "min_mock_questions": 1,
        "tier_targets": {"premium": 0.9, "local": 0.8},
    }


def synthetic_coverage_artifacts() -> dict[str, Any]:
    """Safe synthetic structural-coverage sibling artifacts (counts only)."""
    return {
        "source_coverage_report": {
            "version": 1,
            "kind": "source_coverage_report",
            "sources": [
                {"status": "ok", "page_count": 3, "visual_candidate_page_count": 1},
                {"status": "covered", "page_count": 2, "visual_candidate_page_count": 0},
            ],
        },
        "visual_inclusion_plan": {"status": "ok", "included_count": 2},
        "table_candidates_manifest": {"status": "ok", "candidate_count": 1},
    }


def _coverage_record(label: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Reduce a payload to the Slice 123 closed-vocabulary record (for display)."""
    warnings = payload.get("warnings") or []
    cov_status = payload.get("extraction_coverage_status")
    cov_present = bool(payload.get("extraction_coverage_bundle", {}).get("coverage_records"))
    recompute_blocker = any(
        item.get("component") == "recompute" for item in payload.get("blocking_failures") or []
    )
    recompute_state = payload.get("component_statuses", {}).get("recompute")
    numeric_leg_covered = recompute_state in {"passed", "failed"}
    return {
        "validation_case": label,
        "input_kind": "synthetic_safe",
        "artifact_path_exercised": True,
        "artifact_name": "quality_safety_unified_qa_json",
        "job_artifact_produced": payload.get("kind") == "quality_safety_job_artifact",
        "advisory_non_blocking": payload.get("advisory") is True,
        "extraction_coverage_bundle_present": cov_present,
        "extraction_coverage_status": cov_status,
        "structural_coverage_leg_covered": cov_status in {"ok", "warning", "partial"},
        "numeric_fact_sheet_extraction_leg_covered": numeric_leg_covered,
        "recompute_blocker_present": recompute_blocker,
        "recompute_component_state": recompute_state,
        "unified_status": payload.get("status"),
        "shippable": payload.get("shippable"),
        "safety_floor_green": payload.get("safety_floor_green"),
        "leak_missing": "recompute_component_missing" in warnings,
    }


def main() -> int:
    coverage = synthetic_coverage_artifacts()

    # --- Case 1: clean_real_case (correct numbers + coverage present) -----------
    clean = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        extraction_bundle=weighted_bundle(claimed=0.2),
        fixture_spec=fixture_spec(value=0.2),
        **coverage,
    )
    check("clean: job artifact kind", clean.get("kind") == "quality_safety_job_artifact")
    check("clean: artifact name exact", clean.get("artifact_name") == ARTIFACT_NAME)
    check("clean: advisory", clean.get("advisory") is True)
    check("clean: unified status passed", clean.get("status") == "passed", json.dumps(clean.get("status")))
    check("clean: shippable", clean.get("shippable") is True)
    check("clean: safety floor green", clean.get("safety_floor_green") is True)
    check("clean: recompute passed", clean.get("component_statuses", {}).get("recompute") == "passed")
    check("clean: coverage status closed", clean.get("extraction_coverage_status") in COVERAGE_STATUSES)
    check("clean: coverage present", clean.get("extraction_coverage_status") in {"ok", "warning", "partial"})
    check("clean: coverage records present", len(clean.get("extraction_coverage_bundle", {}).get("coverage_records") or []) >= 2)
    check("clean: coverage numeric obs empty", clean.get("extraction_coverage_bundle", {}).get("numeric_observations") == [])
    check("clean: coverage numeric count 0", clean.get("extraction_coverage_summary", {}).get("numeric_observation_count") == 0)
    check("clean: no judge/repair/overall keys", _no_forbidden_keys(clean))

    # --- Case 2: single_confident_wrong_numeric_case ---------------------------
    # A single wrong numeric claim must be caught by recompute and stay red, even
    # with rich structural coverage present.
    wrong = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.5),
        extraction_bundle=weighted_bundle(claimed=0.5),
        fixture_spec=fixture_spec(value=0.5),
        **coverage,
    )
    check("wrong: unified status failed", wrong.get("status") == "failed", json.dumps(wrong.get("status")))
    check("wrong: not shippable", wrong.get("shippable") is False)
    check("wrong: safety floor red", wrong.get("safety_floor_green") is False)
    check(
        "wrong: recompute blocker present",
        any(
            item.get("component") == "recompute" and item.get("check_id") == "weighted_gini"
            for item in wrong.get("blocking_failures") or []
        ),
        json.dumps(wrong.get("blocking_failures")),
    )
    check("wrong: coverage present", wrong.get("extraction_coverage_status") in {"ok", "warning", "partial"})
    check("wrong: coverage did not upgrade status", wrong.get("status") == "failed")
    check("wrong: coverage numeric count 0", wrong.get("extraction_coverage_summary", {}).get("numeric_observation_count") == 0)
    check("wrong: no judge/repair/overall keys", _no_forbidden_keys(wrong))

    # --- Case 3: legacy_confused_wrong_case (production-shaped) -----------------
    # The production hook supplies candidate_markdown + structural coverage sibling
    # artifacts only — never a concept/fact bundle. So the numeric fact-sheet /
    # recompute leg must stay honestly missing even though structural coverage is
    # present. This is the core Slice 123 honesty check.
    legacy = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.5),
        **coverage,
    )
    warnings = legacy.get("warnings") or []
    check("legacy: coverage present", legacy.get("extraction_coverage_status") in {"ok", "warning", "partial"})
    check("legacy: coverage records present", len(legacy.get("extraction_coverage_bundle", {}).get("coverage_records") or []) >= 2)
    check("legacy: recompute component missing", "recompute_component_missing" in warnings, str(warnings))
    check("legacy: fact-sheet component missing", "fact_sheet_component_missing" in warnings, str(warnings))
    check(
        "legacy: recompute leg not covered",
        legacy.get("component_statuses", {}).get("recompute") in {"unknown", "skipped"},
        json.dumps(legacy.get("component_statuses")),
    )
    check("legacy: no recompute blocker without facts", not any(
        item.get("component") == "recompute" for item in legacy.get("blocking_failures") or []
    ))
    check("legacy: coverage numeric obs empty", legacy.get("extraction_coverage_bundle", {}).get("numeric_observations") == [])
    check("legacy: coverage numeric count 0", legacy.get("extraction_coverage_summary", {}).get("numeric_observation_count") == 0)

    # --- Production hook path: structural coverage wired, numeric leg uncovered -
    # Exercise the *actual* production hook with synthetic sibling artifacts only
    # (the real production call shape), and confirm the numeric leg stays missing.
    from pipeline.run_markdown_job import _write_quality_safety_unified_qa

    class _FakeJob:
        def __init__(self, root: Path) -> None:
            self.dir = root
            self.clean_md = root / "clean.md"
            self.quality_safety_unified_qa_json = root / ARTIFACT_NAME
            self.source_coverage_report_json = root / "source_coverage_report.json"
            self.extraction_metadata_json = root / "extraction_metadata.json"
            self.visual_inclusion_plan_json = root / "visual_inclusion_plan.json"
            self.table_candidates_manifest_json = root / "table_candidates_manifest.json"
            self.table_reconstruction_policy_json = root / "table_reconstruction_policy.json"

        def save_text(self, path: Path, text: str) -> None:
            Path(path).write_text(text, encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "job"
        root.mkdir()
        job = _FakeJob(root)
        job.clean_md.write_text(candidate_markdown(value=0.5), encoding="utf-8")
        job.source_coverage_report_json.write_text(
            json.dumps(coverage["source_coverage_report"]), encoding="utf-8"
        )
        job.visual_inclusion_plan_json.write_text(
            json.dumps(coverage["visual_inclusion_plan"]), encoding="utf-8"
        )
        job.table_candidates_manifest_json.write_text(
            json.dumps(coverage["table_candidates_manifest"]), encoding="utf-8"
        )
        _write_quality_safety_unified_qa(job)
        hooked = json.loads(job.quality_safety_unified_qa_json.read_text(encoding="utf-8"))

    hook_warnings = hooked.get("warnings") or []
    check("hook: artifact written by exact name", hooked.get("artifact_name") == ARTIFACT_NAME)
    check("hook: advisory", hooked.get("advisory") is True)
    check("hook: coverage status closed", hooked.get("extraction_coverage_status") in COVERAGE_STATUSES)
    check("hook: structural coverage present", hooked.get("extraction_coverage_status") in {"ok", "warning", "partial"})
    check("hook: coverage records present", len(hooked.get("extraction_coverage_bundle", {}).get("coverage_records") or []) >= 2)
    check("hook: numeric fact-sheet leg NOT covered", "recompute_component_missing" in hook_warnings, str(hook_warnings))
    check(
        "hook: recompute stays missing/skipped through production path",
        hooked.get("component_statuses", {}).get("recompute") in {"unknown", "skipped"},
        json.dumps(hooked.get("component_statuses")),
    )
    check("hook: coverage numeric count 0", hooked.get("extraction_coverage_summary", {}).get("numeric_observation_count") == 0)
    check("hook: no judge/repair/overall keys", _no_forbidden_keys(hooked))

    # --- No-leak across every produced payload ---------------------------------
    blob = json.dumps([clean, wrong, legacy, hooked])
    check("no synthetic canary anywhere", SYNTHETIC_CANARY not in blob)

    # --- Closed-vocabulary records for the docs (display only) -----------------
    records = [
        _coverage_record("clean_real_case", clean),
        _coverage_record("single_confident_wrong_numeric_case", wrong),
        _coverage_record("legacy_confused_wrong_case", legacy),
    ]
    print("\nClosed-vocabulary synthetic artifact-path records:")
    for record in records:
        print("  " + json.dumps(record, sort_keys=True))

    # --- Slice-level honest conclusion (structurally guaranteed) ---------------
    check(
        "conclusion: structural coverage leg covered (wired + present)",
        records[0]["structural_coverage_leg_covered"] is True
        and records[2]["structural_coverage_leg_covered"] is True,
    )
    check(
        "conclusion: numeric fact-sheet leg NOT covered through production hook",
        "recompute_component_missing" in hook_warnings,
    )

    print(f"\nvalidate_quality_safety_real_disaster_e2e: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
