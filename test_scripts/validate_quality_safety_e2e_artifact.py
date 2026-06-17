#!/usr/bin/env python3
"""Slice 120 — Advisory Quality Safety artifact E2E validation (synthetic-safe).

This harness exercises the *visible advisory path* of the Quality Safety unified
QA artifact end to end at the function/artifact level, deterministically and
without Docker, providers, models, or any private material. It proves:

1. A synthetic-safe candidate produces the exact-name artifact
   ``quality_safety_unified_qa.json`` (production-equivalent call shape).
2. The artifact can be written and read back by its exact filename.
3. Missing extraction-bundle state degrades to closed component-missing /
   skipped tokens (never a crash, never invented facts).
4. The artifact is advisory-only: the payload carries ``advisory=True`` and no
   blocking gate / judge / repair structure.
5. Hostile ``job_metadata`` canaries never survive into the artifact.

Synthetic-only. No real source decks, references, generated guides, OCR/table/
caption text, uploaded specs, provider payloads, paths, URLs, images, PDFs,
DOCX/ZIPs, or runtime artifacts are read or written outside a temp dir.

It is a *validation harness*, not a production code change: it imports the
existing advisory writer and asserts its observable, closed-vocabulary contract.

Run:  python test_scripts/validate_quality_safety_e2e_artifact.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_job_artifact import (  # noqa: E402
    ARTIFACT_NAME,
    build_quality_safety_job_artifact_payload,
    write_quality_safety_job_artifact,
)

PASS = 0
FAIL = 0

# Synthetic placeholder body only — no private/source/generated content.
SYNTHETIC_CANDIDATE = (
    "# Synthetic Heading\n\n"
    "Synthetic placeholder body text used only for advisory artifact validation.\n\n"
    "- synthetic bullet one\n- synthetic bullet two\n"
)

# A single synthetic canary smuggled through job_metadata; it must never appear
# in the artifact (the writer drops unsafe metadata wholesale).
SYNTHETIC_CANARY = "ZZSYNTH_E2E_PRIVATE_MARKER_ONLY"

# Closed expectations.
EXPECTED_KIND = "quality_safety_job_artifact"
EXPECTED_NESTED_KIND = "quality_safety_unified_qa"
COMPONENT_KEYS = ("layer1", "recompute", "canonical", "leak")
# Quality Safety must not introduce any judge/repair/score-gate structure. Note:
# the existing advisory report legitimately carries a *descriptive* ``blocking``
# boolean and ``blocking_failures`` rows (closed-vocabulary diagnostics that never
# change job status) — those are NOT forbidden. The forbidden keys below are the
# ones this unit must never add: judge scoring, a 0-10 overall score, or repair.
FORBIDDEN_KEYS = (
    "overall_10",
    "judge",
    "judge_score",
    "judge_response",
    "repair",
    "repaired_markdown",
)


def check(label: str, ok: bool) -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        FAIL += 1
        print(f"[FAIL] {label}")


def _no_forbidden_keys(obj: object) -> bool:
    """Recursively assert no judge/repair/overall-score keys exist anywhere."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in FORBIDDEN_KEYS:
                return False
            if not _no_forbidden_keys(value):
                return False
        return True
    if isinstance(obj, list):
        return all(_no_forbidden_keys(item) for item in obj)
    return True


def main() -> int:
    # 1. Production-equivalent build: candidate_markdown only (no extraction
    #    bundle), exactly as pipeline.run_markdown_job calls it today.
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=SYNTHETIC_CANDIDATE,
        job_metadata={"smuggled": SYNTHETIC_CANARY},
    )
    check("artifact produced", isinstance(payload, dict))
    check("artifact kind is job artifact", payload.get("kind") == EXPECTED_KIND)
    check("exact artifact name is unified qa json", payload.get("artifact_name") == ARTIFACT_NAME)
    check("artifact name string is exact", ARTIFACT_NAME == "quality_safety_unified_qa.json")
    check("artifact is advisory", payload.get("advisory") is True)
    check("status is a closed token", payload.get("status") in {"passed", "warning", "failed", "skipped", "partial"})

    nested = payload.get("quality_safety_unified_qa")
    check("nested unified report present", isinstance(nested, dict) and nested.get("kind") == EXPECTED_NESTED_KIND)

    components = payload.get("component_statuses")
    check("component statuses present", isinstance(components, dict) and all(k in components for k in COMPONENT_KEYS))

    # 2. Missing extraction-bundle state degrades to closed component-missing /
    #    skipped tokens (no crash, no invented facts).
    warnings = payload.get("warnings") or []
    check("extraction bundle missing recorded", "extraction_bundle_missing" in warnings)
    check("fact-sheet component missing recorded", "fact_sheet_component_missing" in warnings)
    check("recompute component missing recorded", "recompute_component_missing" in warnings)
    check("canonical component missing recorded", "canonical_component_missing" in warnings)
    check(
        "extraction-dependent components are unknown/skipped",
        components.get("recompute") in {"unknown", "skipped"}
        and components.get("canonical") in {"unknown", "skipped"},
    )
    check("no blocking failures invented without extraction", payload.get("blocking_failures") == [])

    # 3. Advisory-only: no judge/repair/overall-score structure anywhere. (The
    #    descriptive ``blocking`` boolean and ``blocking_failures`` rows are
    #    pre-existing closed diagnostics and are intentionally allowed.)
    check("no judge/repair/overall-score keys anywhere", _no_forbidden_keys(payload))

    # 4. No-leak: the smuggled metadata canary is dropped wholesale.
    flat = json.dumps(payload)
    check("unsafe metadata dropped warning recorded", "unsafe_metadata_dropped" in warnings)
    check("smuggled metadata canary absent from artifact", SYNTHETIC_CANARY not in flat)

    # 5. Exact-name write + read-back round trip.
    with tempfile.TemporaryDirectory() as tmp:
        write_quality_safety_job_artifact(tmp, candidate_markdown=SYNTHETIC_CANDIDATE)
        artifact_path = Path(tmp) / ARTIFACT_NAME
        check("exact-name artifact file written", artifact_path.is_file())
        roundtrip = json.loads(artifact_path.read_text(encoding="utf-8"))
        check("round-trip kind preserved", roundtrip.get("kind") == EXPECTED_KIND)
        check("round-trip advisory preserved", roundtrip.get("advisory") is True)
        check("round-trip no judge/repair/overall-score keys", _no_forbidden_keys(roundtrip))

    # 6. Slice 122: the advisory structural extraction-coverage leg is absent
    #    (skipped) in the production-equivalent build above, and present when safe
    #    synthetic structural metadata is supplied — without inventing numerics or
    #    upgrading shippable / safety_floor_green.
    check("coverage status closed (absent)", payload.get("extraction_coverage_status") in {"ok", "warning", "skipped", "partial", "failed"})
    check("coverage skipped without metadata", payload.get("extraction_coverage_status") == "skipped")
    check("coverage missing warning recorded", "extraction_coverage_missing" in warnings)
    absent_bundle = payload.get("extraction_coverage_bundle") or {}
    check("coverage bundle kind", absent_bundle.get("kind") == "quality_safety_extraction_coverage_bundle")
    check("coverage numeric observations empty (absent)", absent_bundle.get("numeric_observations") == [])

    with_coverage = build_quality_safety_job_artifact_payload(
        candidate_markdown=SYNTHETIC_CANDIDATE,
        source_coverage_report={
            "sources": [
                {"status": "ok", "page_count": 2, "visual_candidate_page_count": 1},
                {"status": "covered", "page_count": 1, "visual_candidate_page_count": 0},
            ]
        },
        visual_inclusion_plan={"status": "ok", "included_count": 1},
        table_candidates_manifest={"status": "ok", "candidate_count": 1},
    )
    cov_bundle = with_coverage.get("extraction_coverage_bundle") or {}
    cov_summary = with_coverage.get("extraction_coverage_summary") or {}
    check("coverage present kind", cov_bundle.get("kind") == "quality_safety_extraction_coverage_bundle")
    check("coverage present records", len(cov_bundle.get("coverage_records") or []) >= 2)
    check("coverage present numeric observations empty", cov_bundle.get("numeric_observations") == [])
    check("coverage present numeric count 0", cov_summary.get("numeric_observation_count") == 0)
    # Structural coverage must not change shippability / safety-floor versus the
    # same candidate without any structural metadata.
    baseline = build_quality_safety_job_artifact_payload(candidate_markdown=SYNTHETIC_CANDIDATE)
    check("coverage does not change shippable", with_coverage.get("shippable") == baseline.get("shippable"))
    check("coverage does not change safety floor", with_coverage.get("safety_floor_green") == baseline.get("safety_floor_green"))
    check("coverage keeps recompute honest", "recompute_component_missing" in (with_coverage.get("warnings") or []))
    check("coverage no judge/repair/overall keys", _no_forbidden_keys(with_coverage))
    check("coverage no smuggled canary", SYNTHETIC_CANARY not in json.dumps(with_coverage))

    # 7. Determinism: identical inputs yield identical serialized payloads.
    again = build_quality_safety_job_artifact_payload(
        candidate_markdown=SYNTHETIC_CANDIDATE,
        job_metadata={"smuggled": SYNTHETIC_CANARY},
    )
    check("deterministic payload on repeat", json.dumps(payload, sort_keys=True) == json.dumps(again, sort_keys=True))

    print(f"\nvalidate_quality_safety_e2e_artifact: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
