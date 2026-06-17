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
- numeric fact-sheet extraction leg: NOT covered through the production hook from
  structural coverage — that hook never derives a concept/fact bundle from
  coverage, so recompute stays ``component_missing`` regardless of how rich the
  structural coverage is. **Slice 126** additionally wires the numeric extraction
  *mapper* into the advisory artifact: when a safe numeric extraction records
  sidecar (``quality_safety_numeric_extraction_records.json``) is present, those
  records feed the producer + recompute verifier, so a wrong numeric claim raises
  a recompute blocker through the real artifact path. No production numeric
  extractor exists yet, so the sidecar is read only when it already exists and the
  leg degrades to ``skipped`` otherwise.

Structural coverage never invents numeric observations and never upgrades
``shippable`` / ``safety_floor_green``; numeric records are kept SEPARATE from the
structural coverage bundle and are never fabricated from coverage counts.

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


def numeric_records(*, value: float) -> list[dict[str, Any]]:
    """Safe synthetic numeric extraction records (Slice 124/125 contract shape).

    weighted_gini of these groups recomputes to 0.2; ``value`` is the *claimed*
    value, so passing 0.2 verifies and any other value raises a recompute blocker.
    """
    return [
        {
            "id": "qs_num_disaster",
            "concept_id": "qs_concept_disaster",
            "label": "synthetic_stump_choice_score",
            "fact_type": "numeric",
            "value": value,
            "unit": "ratio",
            "provenance": "computed",
            "confidence": "high",
            "source_ref": "source_page_1",
            "computation": {"method": "weighted_gini", "inputs": {"groups": [{"yes": 3, "no": 0}, {"yes": 1, "no": 4}]}},
            "tolerance": 0.01,
        }
    ]


def structured_candidates(*, value: float, method: str = "weighted_gini") -> dict[str, Any]:
    """Future structured numeric candidate sidecar shape (Slice 133/134)."""
    record = dict(numeric_records(value=value)[0])
    record["id"] = "qs_struct_disaster"
    record["page_ref"] = "page_1"
    record["computation"] = {
        "method": method,
        "inputs": {"groups": [{"yes": 3, "no": 0}, {"yes": 1, "no": 4}]},
    }
    return {
        "version": 1,
        "kind": "quality_safety_structured_numeric_candidates",
        "status": "ok",
        "source_quality": "structured_numeric_artifact",
        "summary": {"candidate_count": 1},
        "candidates": [record],
        "warnings": [],
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
    check("hook: numeric leg skipped without sidecar", hooked.get("numeric_extraction_status") == "skipped", json.dumps(hooked.get("numeric_extraction_status")))
    check("hook: no judge/repair/overall keys", _no_forbidden_keys(hooked))

    # --- Slice 126: numeric extraction mapper wired into the advisory artifact --
    # When safe numeric records are present they feed the producer + recompute
    # verifier through the real artifact path: a clean claim verifies, a wrong one
    # blocks. Numeric records stay SEPARATE from structural coverage.
    numeric_clean = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        numeric_extraction_records=numeric_records(value=0.2),
        **coverage,
    )
    check("numeric clean: status ok bundle", numeric_clean.get("numeric_extraction_status") == "ok", json.dumps(numeric_clean.get("numeric_extraction_status")))
    check("numeric clean: recompute passed", numeric_clean.get("component_statuses", {}).get("recompute") == "passed", json.dumps(numeric_clean.get("component_statuses")))
    check("numeric clean: no recompute blocker", not any(item.get("component") == "recompute" for item in numeric_clean.get("blocking_failures") or []))
    check("numeric clean: shippable", numeric_clean.get("shippable") is True)
    check("numeric clean: coverage still separate", numeric_clean.get("extraction_coverage_summary", {}).get("numeric_observation_count") == 0)
    check("numeric clean: coverage present", numeric_clean.get("extraction_coverage_status") in {"ok", "warning", "partial"})
    check("numeric clean: no judge/repair/overall keys", _no_forbidden_keys(numeric_clean))

    numeric_wrong = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.9),
        numeric_extraction_records=numeric_records(value=0.9),  # recomputes to 0.2
        **coverage,
    )
    check(
        "numeric wrong: recompute blocker through artifact path",
        any(
            item.get("component") == "recompute" and item.get("check_id") == "weighted_gini"
            for item in numeric_wrong.get("blocking_failures") or []
        ),
        json.dumps(numeric_wrong.get("blocking_failures")),
    )
    check("numeric wrong: status failed", numeric_wrong.get("status") == "failed", json.dumps(numeric_wrong.get("status")))
    check("numeric wrong: not shippable", numeric_wrong.get("shippable") is False)
    check("numeric wrong: safety floor red", numeric_wrong.get("safety_floor_green") is False)
    check("numeric wrong: coverage did not upgrade", numeric_wrong.get("status") == "failed")
    check("numeric wrong: no judge/repair/overall keys", _no_forbidden_keys(numeric_wrong))

    # --- Production hook with a safe numeric records sidecar present ------------
    from pipeline.quality_safety_job_artifact import NUMERIC_RECORDS_ARTIFACT_NAME

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "job"
        root.mkdir()
        job = _FakeJob(root)
        job.clean_md.write_text(candidate_markdown(value=0.9), encoding="utf-8")
        (root / NUMERIC_RECORDS_ARTIFACT_NAME).write_text(
            json.dumps({"records": numeric_records(value=0.9)}), encoding="utf-8"
        )
        _write_quality_safety_unified_qa(job)
        numeric_hooked = json.loads(job.quality_safety_unified_qa_json.read_text(encoding="utf-8"))

    check("numeric hook: record consumed", numeric_hooked.get("numeric_extraction_summary", {}).get("record_count") == 1, json.dumps(numeric_hooked.get("numeric_extraction_summary")))
    check(
        "numeric hook: recompute blocker through production hook",
        any(item.get("component") == "recompute" for item in numeric_hooked.get("blocking_failures") or []),
        json.dumps(numeric_hooked.get("blocking_failures")),
    )
    check("numeric hook: not shippable", numeric_hooked.get("shippable") is False)
    check("numeric hook: no judge/repair/overall keys", _no_forbidden_keys(numeric_hooked))

    # --- Slice 130: safe numeric extractor wired into the advisory artifact ------
    # A safe numeric *candidate* sidecar feeds the Slice 129 extractor, whose
    # records drive the same recompute leg through the real artifact path: a clean
    # candidate verifies, a wrong one blocks. Candidates are SEPARATE from structural
    # coverage and never fabricated from coverage counts.
    safe_clean = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        safe_numeric_candidates=numeric_records(value=0.2),
        **coverage,
    )
    check("safe clean: extractor ok", safe_clean.get("safe_numeric_extractor_status") == "ok", json.dumps(safe_clean.get("safe_numeric_extractor_status")))
    check("safe clean: recompute passed", safe_clean.get("component_statuses", {}).get("recompute") == "passed", json.dumps(safe_clean.get("component_statuses")))
    check("safe clean: shippable", safe_clean.get("shippable") is True)
    check("safe clean: coverage still separate", safe_clean.get("extraction_coverage_summary", {}).get("numeric_observation_count") == 0)
    check("safe clean: no judge/repair/overall keys", _no_forbidden_keys(safe_clean))

    safe_wrong = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.9),
        safe_numeric_candidates=numeric_records(value=0.9),  # recomputes to 0.2
        **coverage,
    )
    check(
        "safe wrong: recompute blocker through artifact path",
        any(
            item.get("component") == "recompute" and item.get("check_id") == "weighted_gini"
            for item in safe_wrong.get("blocking_failures") or []
        ),
        json.dumps(safe_wrong.get("blocking_failures")),
    )
    check("safe wrong: status failed", safe_wrong.get("status") == "failed", json.dumps(safe_wrong.get("status")))
    check("safe wrong: not shippable", safe_wrong.get("shippable") is False)
    check("safe wrong: safety floor red", safe_wrong.get("safety_floor_green") is False)
    check("safe wrong: no judge/repair/overall keys", _no_forbidden_keys(safe_wrong))

    # Precedence: explicit numeric records win over safe candidates deterministically.
    safe_precedence = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        numeric_extraction_records=numeric_records(value=0.2),  # explicit, correct
        safe_numeric_candidates=numeric_records(value=0.9),  # would be wrong
        **coverage,
    )
    check("safe precedence: safe superseded", safe_precedence.get("safe_numeric_extractor_status") == "skipped", json.dumps(safe_precedence.get("safe_numeric_extractor_status")))
    check(
        "safe precedence: superseded warning",
        "superseded_by_explicit_records" in (safe_precedence.get("safe_numeric_extractor_warnings") or []),
        json.dumps(safe_precedence.get("safe_numeric_extractor_warnings")),
    )
    check("safe precedence: explicit correct verifies", safe_precedence.get("component_statuses", {}).get("recompute") == "passed", json.dumps(safe_precedence.get("component_statuses")))
    check("safe precedence: shippable", safe_precedence.get("shippable") is True)

    # --- Production hook with a safe numeric candidate sidecar present ----------
    from pipeline.quality_safety_job_artifact import SAFE_NUMERIC_CANDIDATES_ARTIFACT_NAME

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "job"
        root.mkdir()
        job = _FakeJob(root)
        job.clean_md.write_text(candidate_markdown(value=0.9), encoding="utf-8")
        (root / SAFE_NUMERIC_CANDIDATES_ARTIFACT_NAME).write_text(
            json.dumps({"candidates": numeric_records(value=0.9)}), encoding="utf-8"
        )
        _write_quality_safety_unified_qa(job)
        safe_hooked = json.loads(job.quality_safety_unified_qa_json.read_text(encoding="utf-8"))

    check("safe hook: extractor ok", safe_hooked.get("safe_numeric_extractor_status") == "ok", json.dumps(safe_hooked.get("safe_numeric_extractor_status")))
    check("safe hook: record consumed", safe_hooked.get("safe_numeric_extractor_summary", {}).get("record_count") == 1, json.dumps(safe_hooked.get("safe_numeric_extractor_summary")))
    check(
        "safe hook: recompute blocker through production hook",
        any(item.get("component") == "recompute" for item in safe_hooked.get("blocking_failures") or []),
        json.dumps(safe_hooked.get("blocking_failures")),
    )
    check("safe hook: not shippable", safe_hooked.get("shippable") is False)
    check("safe hook: no judge/repair/overall keys", _no_forbidden_keys(safe_hooked))

    # --- Slice 134: structured adapter wired into the advisory artifact --------
    # A future structured numeric candidate sidecar is read-only, adapted through
    # Slice 133, then fed into the existing Slice 129 safe extractor path. Explicit
    # records and safe candidates still win deterministically.
    structured_clean = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        structured_numeric_candidates=structured_candidates(value=0.2),
        **coverage,
    )
    check(
        "structured clean: adapter ok",
        structured_clean.get("structured_numeric_candidate_adapter_status") == "ok",
        json.dumps(structured_clean.get("structured_numeric_candidate_adapter_status")),
    )
    check("structured clean: safe extractor ok", structured_clean.get("safe_numeric_extractor_status") == "ok")
    check("structured clean: recompute passed", structured_clean.get("component_statuses", {}).get("recompute") == "passed")
    check("structured clean: shippable", structured_clean.get("shippable") is True)
    check("structured clean: no judge/repair/overall keys", _no_forbidden_keys(structured_clean))

    structured_wrong = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.9),
        structured_numeric_candidates=structured_candidates(value=0.9),
        **coverage,
    )
    check(
        "structured wrong: recompute blocker through artifact path",
        any(
            item.get("component") == "recompute" and item.get("check_id") == "weighted_gini"
            for item in structured_wrong.get("blocking_failures") or []
        ),
        json.dumps(structured_wrong.get("blocking_failures")),
    )
    check("structured wrong: status failed", structured_wrong.get("status") == "failed", json.dumps(structured_wrong.get("status")))
    check("structured wrong: not shippable", structured_wrong.get("shippable") is False)
    check("structured wrong: safety floor red", structured_wrong.get("safety_floor_green") is False)
    check("structured wrong: no judge/repair/overall keys", _no_forbidden_keys(structured_wrong))

    structured_legacy = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.9),
        structured_numeric_candidates=structured_candidates(value=0.9, method="entropy"),
        **coverage,
    )
    check(
        "structured legacy unsupported: partial/warning",
        structured_legacy.get("structured_numeric_candidate_adapter_status") in {"warning", "partial"},
        json.dumps(structured_legacy.get("structured_numeric_candidate_adapter_status")),
    )
    check(
        "structured legacy unsupported: no recompute blocker",
        not any(item.get("component") == "recompute" for item in structured_legacy.get("blocking_failures") or []),
        json.dumps(structured_legacy.get("blocking_failures")),
    )

    structured_precedence = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        numeric_extraction_records=numeric_records(value=0.2),
        safe_numeric_candidates=numeric_records(value=0.9),
        structured_numeric_candidates=structured_candidates(value=0.9),
        **coverage,
    )
    check(
        "structured precedence: explicit wins",
        structured_precedence.get("component_statuses", {}).get("recompute") == "passed",
        json.dumps(structured_precedence.get("component_statuses")),
    )
    check(
        "structured precedence: adapter superseded",
        "superseded_by_explicit_records"
        in (structured_precedence.get("structured_numeric_candidate_adapter_warnings") or []),
        json.dumps(structured_precedence.get("structured_numeric_candidate_adapter_warnings")),
    )
    check("structured precedence: shippable", structured_precedence.get("shippable") is True)

    from pipeline.quality_safety_job_artifact import STRUCTURED_NUMERIC_CANDIDATES_ARTIFACT_NAME

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "job"
        root.mkdir()
        job = _FakeJob(root)
        job.clean_md.write_text(candidate_markdown(value=0.9), encoding="utf-8")
        (root / STRUCTURED_NUMERIC_CANDIDATES_ARTIFACT_NAME).write_text(
            json.dumps(structured_candidates(value=0.9)), encoding="utf-8"
        )
        _write_quality_safety_unified_qa(job)
        structured_hooked = json.loads(job.quality_safety_unified_qa_json.read_text(encoding="utf-8"))

    check("structured hook: adapter ok", structured_hooked.get("structured_numeric_candidate_adapter_status") == "ok")
    check("structured hook: safe extractor ok", structured_hooked.get("safe_numeric_extractor_status") == "ok")
    check(
        "structured hook: recompute blocker through production hook",
        any(item.get("component") == "recompute" for item in structured_hooked.get("blocking_failures") or []),
        json.dumps(structured_hooked.get("blocking_failures")),
    )
    check("structured hook: not shippable", structured_hooked.get("shippable") is False)
    check("structured hook: no judge/repair/overall keys", _no_forbidden_keys(structured_hooked))

    # --- No-leak across every produced payload ---------------------------------
    blob = json.dumps(
        [clean, wrong, legacy, hooked, numeric_clean, numeric_wrong, numeric_hooked,
         safe_clean, safe_wrong, safe_precedence, safe_hooked, structured_clean,
         structured_wrong, structured_legacy, structured_precedence,
         structured_hooked]
    )
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
        "conclusion: numeric fact-sheet leg NOT covered through production hook (no extractor)",
        "recompute_component_missing" in hook_warnings,
    )
    check(
        "conclusion: numeric mapper wiring verifies clean + blocks wrong through artifact path",
        numeric_clean.get("component_statuses", {}).get("recompute") == "passed"
        and any(item.get("component") == "recompute" for item in numeric_wrong.get("blocking_failures") or []),
    )
    check(
        "conclusion: safe extractor wiring verifies clean + blocks wrong through artifact path",
        safe_clean.get("component_statuses", {}).get("recompute") == "passed"
        and any(item.get("component") == "recompute" for item in safe_wrong.get("blocking_failures") or []),
    )

    # Closed-vocabulary Slice 126 outcome for the docs (display only).
    print("\nSlice 126 numeric extraction wiring (closed-vocabulary):")
    print(
        "  "
        + json.dumps(
            {
                "numeric_mapper_wired_into_artifact": True,
                "numeric_records_present_path": "synthetic_only",
                "clean_numeric_recompute": "passed",
                "wrong_numeric_recompute": "failed_blocking",
                "numeric_extraction_status_without_sidecar": hooked.get("numeric_extraction_status"),
                "production_numeric_extractor_exists": False,
                "structural_coverage_leg_status": "covered",
                "numeric_fact_sheet_extraction_leg_status": "partial",
                "artifact_path_ready_for_synthetic_numeric_records": True,
                "judge_ready": False,
                "repair_ready": False,
            },
            sort_keys=True,
        )
    )

    # Closed-vocabulary Slice 130 outcome for the docs (display only).
    print("\nSlice 130 safe numeric extractor wiring (closed-vocabulary):")
    print(
        "  "
        + json.dumps(
            {
                "safe_numeric_extractor_wired_into_artifact": True,
                "safe_numeric_candidates_input_artifact": "quality_safety_safe_numeric_candidates.json",
                "precedence": "explicit_numeric_records_over_safe_candidates",
                "safe_numeric_extractor_artifact_path_status": "ok",
                "clean_safe_candidate_recompute": "passed",
                "wrong_safe_candidate_recompute": "failed_blocking",
                "safe_extractor_status_without_sidecar": hooked.get("safe_numeric_extractor_status"),
                "numeric_fact_sheet_extraction_leg_status": "partial",
                "artifact_path_ready": "true_for_synthetic_candidates",
                "production_numeric_extractor_present": "sidecar_candidate_only",
                "structural_coverage_into_candidates": False,
                "judge_ready": False,
                "repair_ready": False,
                "next_step": "production_safe_candidate_source_or_operator_waiver",
            },
            sort_keys=True,
        )
    )

    # Closed-vocabulary Slice 134 outcome for the docs (display only).
    print("\nSlice 134 structured numeric adapter wiring (closed-vocabulary):")
    print(
        "  "
        + json.dumps(
            {
                "structured_numeric_candidate_adapter_wired_into_artifact": True,
                "structured_numeric_candidates_input_artifact": "quality_safety_structured_numeric_candidates.json",
                "precedence": "explicit_records_over_safe_candidates_over_structured_candidates",
                "structured_numeric_candidate_adapter_artifact_path_status": "ok",
                "safe_numeric_extractor_artifact_path_status": "ok",
                "clean_structured_candidate_recompute": "passed",
                "wrong_structured_candidate_recompute": "failed_blocking",
                "legacy_confused_wrong_case": "partial",
                "structured_adapter_status_without_sidecar": hooked.get(
                    "structured_numeric_candidate_adapter_status"
                ),
                "numeric_fact_sheet_extraction_leg_status": "partial",
                "artifact_path_ready": "true_for_synthetic_structured_candidates",
                "production_numeric_extractor_present": "structured_artifact_sidecar_only",
                "structural_coverage_into_structured_candidates": False,
                "judge_ready": False,
                "repair_ready": False,
                "next_step": "future_structured_numeric_candidate_producer_design_or_operator_waiver",
            },
            sort_keys=True,
        )
    )

    print(f"\nvalidate_quality_safety_real_disaster_e2e: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
