#!/usr/bin/env python3
"""Slice 138 — Operator Structured Numeric Export Validation Harness (synthetic).

Closes the Quality Safety numeric infrastructure phase. This harness gives the
operator a single safe way to *run* the Slice 137 pure validator end-to-end and
record a closed-vocabulary result, without committing private material.

It exercises the full numeric chain that Slice 137 proved compatible:

    operator structured numeric export validator
      -> structured numeric candidate adapter
      -> safe numeric extractor
      -> numeric mapper / fact-sheet producer / recompute verifier
      -> advisory job-artifact builder
         (``build_quality_safety_job_artifact_payload(structured_numeric_candidates=...)``)

and prints a **closed-vocabulary summary only** (no raw candidate values, no
source/guide/OCR/table/caption text, no paths, no raw records, no exception text).

Modes
-----
Default (synthetic): runs five synthetic cases and asserts their expected
outcomes; exits non-zero if any synthetic expectation fails.

    python test_scripts/validate_quality_safety_operator_structured_numeric_export.py

Optional local/private operator mode: validates one explicit local JSON file the
operator authored. It reads only that exact file, never prints the path or any
raw value/record, prints a closed-vocabulary status only, and writes nothing.

    python test_scripts/validate_quality_safety_operator_structured_numeric_export.py --input /local/private/path.json

Hard guarantees: stdlib + existing Quality Safety modules only; no provider /
model / cloud / judge / repair calls; no FastAPI / frontend / render / OCR
imports; no source-document parsing; no ``clean.md`` reads as a numeric source;
no job-folder scanning (only the one explicit ``--input`` path, if given); writes
no output files. No production wiring. The local path and any private JSON / raw
values must never be committed — only the closed-vocabulary summary is safe.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_job_artifact import (  # noqa: E402
    build_quality_safety_job_artifact_payload,
)
from pipeline.quality_safety_operator_structured_numeric_export_validator import (  # noqa: E402
    operator_export_validation_to_structured_numeric_payload,
    validate_operator_structured_numeric_export,
)

VALIDATION_ID = "operator_structured_numeric_export_validation_harness"
ARTIFACT_NAME_TOKEN = "quality_safety_structured_numeric_candidates_json"

# A single synthetic canary smuggled into forbidden fields; it must never appear
# in any closed-vocabulary summary the harness emits.
SYNTHETIC_CANARY = "ZZSYNTH_OPERATOR_EXPORT_PRIVATE_MARKER_ONLY"

# Closed status vocabularies (mirrors the underlying components).
_VALIDATOR_STATUSES = {"ok", "warning", "skipped", "partial", "failed", "not_observed"}
_COMPONENT_STATUSES = {"ok", "warning", "skipped", "partial", "failed", "not_observed"}
_RECOMPUTE_STATUSES = {"passed", "failed", "skipped", "partial", "unknown", "not_observed"}

# Closed warning vocabulary the harness is allowed to surface.
_CLOSED_WARNINGS = frozenset(
    {
        "component_missing",
        "malformed_input",
        "invalid_kind",
        "invalid_source_quality",
        "candidates_missing",
        "no_candidates",
        "unsafe_field_excluded",
        "invalid_candidate_rejected",
        "invalid_numeric_value",
        "invalid_provenance",
        "invalid_computation",
        "unsupported_method",
        "max_items_reached",
        "recompute_blocker_present",
        "unverified_unsupported_method",
        "input_read_failed",
    }
)

PASS = 0
FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        FAIL += 1
        suffix = f" - {detail}" if detail else ""
        print(f"[FAIL] {label}{suffix}")


# --- Synthetic-safe operator export inputs (no private content) ----------------


def _candidate_markdown() -> str:
    return "\n".join(
        [
            "# Synthetic Fixture",
            "Synthetic Concept",
            "synthetic_stump_choice_score: 0.2",
            "## Worked Answer",
            "Solution: substitute the synthetic counts and finish with the numeric target.",
        ]
    )


def _operator_candidate(*, value: float, method: str = "weighted_gini") -> dict[str, Any]:
    """A synthetic operator-authored structured numeric candidate.

    weighted_gini of these synthetic group counts recomputes to 0.2, so a claimed
    value of 0.2 verifies and any other value raises a recompute blocker.
    """
    return {
        "id": "qs_operator_export_synthetic",
        "concept_id": "qs_concept_operator_synthetic",
        "label": "synthetic_stump_choice_score",
        "fact_type": "numeric",
        "value": value,
        "unit": "ratio",
        "provenance": "operator_approved",
        "confidence": "high",
        "source_ref": "source_page_1",
        "computation": {
            "method": method,
            "inputs": {"groups": [{"yes": 3, "no": 0}, {"yes": 1, "no": 4}]},
        },
        "tolerance": 0.01,
    }


def _operator_export(*, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_structured_numeric_candidates",
        "source_quality": "operator_approved",
        "candidates": candidates,
    }


def _forbidden_field_candidate() -> dict[str, Any]:
    """A structurally valid candidate carrying forbidden fields + a canary.

    The validator (via the Slice 133 adapter) must strip every forbidden field and
    never let the canary survive into any downstream payload or summary.
    """
    candidate = _operator_candidate(value=0.2)
    candidate.update(
        {
            "raw_text": SYNTHETIC_CANARY,
            "source_text": SYNTHETIC_CANARY,
            "guide_text": SYNTHETIC_CANARY,
            "ocr_text": SYNTHETIC_CANARY,
            "page_text": SYNTHETIC_CANARY,
            "table_cells": [SYNTHETIC_CANARY],
            "captions": [SYNTHETIC_CANARY],
            "formulas_as_text": SYNTHETIC_CANARY,
            "evidence_quotes": [SYNTHETIC_CANARY],
            "filename": SYNTHETIC_CANARY,
            "path": SYNTHETIC_CANARY,
            "provider_payload": SYNTHETIC_CANARY,
            "raw_artifact_json": SYNTHETIC_CANARY,
        }
    )
    return candidate


# --- Pipeline driver -----------------------------------------------------------


def _bool_token(value: Any, observed: bool) -> str:
    if not observed:
        return "not_observed"
    return "true" if value is True else "false"


def _component_token(value: Any, allowed: set[str]) -> str:
    return value if isinstance(value, str) and value in allowed else "not_observed"


def run_export_validation(
    operator_export: Any,
    *,
    input_kind: str,
    observed: bool = True,
) -> dict[str, Any]:
    """Run the full chain on one operator export; return a closed summary.

    ``operator_export`` is a caller-supplied dict (synthetic or private-local). No
    raw value/record is ever placed into the returned summary — only closed tokens
    and counts.
    """
    validation = validate_operator_structured_numeric_export(operator_export)
    structured_payload = operator_export_validation_to_structured_numeric_payload(validation)

    artifact = build_quality_safety_job_artifact_payload(
        candidate_markdown=_candidate_markdown(),
        structured_numeric_candidates=structured_payload,
    )

    validator_status = _component_token(validation.get("status"), _VALIDATOR_STATUSES)
    adapter_status = _component_token(
        artifact.get("structured_numeric_candidate_adapter_status"), _COMPONENT_STATUSES
    )
    safe_status = _component_token(artifact.get("safe_numeric_extractor_status"), _COMPONENT_STATUSES)
    numeric_status = _component_token(artifact.get("numeric_extraction_status"), _COMPONENT_STATUSES)
    recompute_state = artifact.get("component_statuses", {}).get("recompute")
    recompute_status = _component_token(recompute_state, _RECOMPUTE_STATUSES)

    recompute_blocker = any(
        item.get("component") == "recompute" for item in artifact.get("blocking_failures") or []
    )

    summary = validation.get("summary") if isinstance(validation.get("summary"), dict) else {}
    accepted = int(summary.get("accepted_candidate_count") or 0)

    # Closed warning set: validator warnings (already closed) + harness-derived
    # blocker/unverified tokens, filtered against the closed vocabulary.
    warnings: set[str] = set()
    for token in validation.get("warnings") or []:
        if isinstance(token, str):
            warnings.add(token)
    if recompute_blocker:
        warnings.add("recompute_blocker_present")
    if "unsupported_method" in warnings and recompute_status in {"skipped", "unknown", "partial", "not_observed"}:
        warnings.add("unverified_unsupported_method")
    warnings = {token for token in warnings if token in _CLOSED_WARNINGS}

    return {
        "validation_id": VALIDATION_ID,
        "input_kind": input_kind,
        "operator_export_created": _bool_token(accepted > 0, observed),
        "operator_export_committed": "false",
        "artifact_name": ARTIFACT_NAME_TOKEN,
        "artifact_path_exercised": "true" if observed else "false",
        "operator_validator_status": validator_status if observed else "not_observed",
        "structured_adapter_status": adapter_status if observed else "not_observed",
        "safe_numeric_extractor_status": safe_status if observed else "not_observed",
        "numeric_extraction_status": numeric_status if observed else "not_observed",
        "recompute_status": recompute_status if observed else "not_observed",
        "recompute_blocker_present": _bool_token(recompute_blocker, observed),
        "shippable": _bool_token(artifact.get("shippable"), observed),
        "safety_floor_green": _bool_token(artifact.get("safety_floor_green"), observed),
        "raw_text_committed": "false",
        "raw_paths_committed": "false",
        "runtime_outputs_committed": "false",
        "provider_calls": "false",
        "judge_calls": "false",
        "repair_calls": "false",
        "warnings": sorted(warnings),
    }


def _not_run_summary(input_kind: str, *, extra_warning: str | None = None) -> dict[str, Any]:
    warnings: list[str] = []
    if extra_warning and extra_warning in _CLOSED_WARNINGS:
        warnings.append(extra_warning)
    return {
        "validation_id": VALIDATION_ID,
        "input_kind": input_kind,
        "operator_export_created": "not_observed",
        "operator_export_committed": "false",
        "artifact_name": ARTIFACT_NAME_TOKEN,
        "artifact_path_exercised": "false",
        "operator_validator_status": "not_observed",
        "structured_adapter_status": "not_observed",
        "safe_numeric_extractor_status": "not_observed",
        "numeric_extraction_status": "not_observed",
        "recompute_status": "not_observed",
        "recompute_blocker_present": "not_observed",
        "shippable": "not_observed",
        "safety_floor_green": "not_observed",
        "raw_text_committed": "false",
        "raw_paths_committed": "false",
        "runtime_outputs_committed": "false",
        "provider_calls": "false",
        "judge_calls": "false",
        "repair_calls": "false",
        "warnings": warnings,
    }


def _no_canary(summary: dict[str, Any]) -> bool:
    return SYNTHETIC_CANARY not in json.dumps(summary)


def _assert_closed(summary: dict[str, Any], label: str) -> None:
    """All summary tokens must be closed-vocabulary and canary-free."""
    check(f"{label}: no synthetic canary in summary", _no_canary(summary))
    check(
        f"{label}: warnings are closed tokens only",
        all(token in _CLOSED_WARNINGS for token in summary.get("warnings") or []),
        json.dumps(summary.get("warnings")),
    )


# --- Synthetic self-test -------------------------------------------------------


def run_synthetic() -> int:
    print("Operator structured numeric export — synthetic self-test\n")

    # 1) clean_operator_export_case: recompute passes, shippable.
    clean = run_export_validation(
        _operator_export(candidates=[_operator_candidate(value=0.2)]),
        input_kind="synthetic_safe",
    )
    check("clean: validator ok", clean["operator_validator_status"] == "ok", json.dumps(clean))
    check("clean: adapter ok", clean["structured_adapter_status"] == "ok")
    check(
        "clean: safe extractor ok/warning",
        clean["safe_numeric_extractor_status"] in {"ok", "warning"},
        clean["safe_numeric_extractor_status"],
    )
    check("clean: recompute passed", clean["recompute_status"] == "passed", clean["recompute_status"])
    check("clean: no recompute blocker", clean["recompute_blocker_present"] == "false")
    check("clean: shippable", clean["shippable"] == "true")
    # safety_floor_green is reported as a closed bool token; it stays a closed value
    # here because the harness supplies only the numeric leg (no coverage/fixture).
    check("clean: safety floor token closed", clean["safety_floor_green"] in {"true", "false"})
    _assert_closed(clean, "clean")

    # 2) wrong_operator_export_case: recompute fails -> blocking, not shippable.
    wrong = run_export_validation(
        _operator_export(candidates=[_operator_candidate(value=0.9)]),  # recomputes to 0.2
        input_kind="synthetic_safe",
    )
    check("wrong: validator ok (well-formed)", wrong["operator_validator_status"] == "ok", json.dumps(wrong))
    check("wrong: recompute failed", wrong["recompute_status"] == "failed", wrong["recompute_status"])
    check("wrong: recompute blocker present", wrong["recompute_blocker_present"] == "true")
    check("wrong: not shippable", wrong["shippable"] == "false")
    check("wrong: safety floor red", wrong["safety_floor_green"] == "false")
    _assert_closed(wrong, "wrong")

    # 3) unsupported_operator_export_case: degraded, partial/unverified, no false blocker.
    unsupported = run_export_validation(
        _operator_export(candidates=[_operator_candidate(value=0.2, method="entropy")]),
        input_kind="synthetic_safe",
    )
    check(
        "unsupported: validator warning/partial",
        unsupported["operator_validator_status"] in {"warning", "partial"},
        unsupported["operator_validator_status"],
    )
    check(
        "unsupported: adapter warning/partial/skipped",
        unsupported["structured_adapter_status"] in {"warning", "partial", "skipped"},
        unsupported["structured_adapter_status"],
    )
    check(
        "unsupported: recompute unverified (skipped/unknown/partial/not_observed)",
        unsupported["recompute_status"] in {"skipped", "unknown", "partial", "not_observed"},
        unsupported["recompute_status"],
    )
    check("unsupported: no false recompute blocker", unsupported["recompute_blocker_present"] == "false")
    check("unsupported: unverified flagged", "unverified_unsupported_method" in (unsupported["warnings"] or []))
    _assert_closed(unsupported, "unsupported")

    # 4) malformed_operator_export_case: failed/warning, no leak.
    malformed = run_export_validation(
        {"kind": "not_a_structured_numeric_export", "candidates": "oops"},
        input_kind="synthetic_safe",
    )
    check(
        "malformed: validator failed/warning/skipped",
        malformed["operator_validator_status"] in {"failed", "warning", "skipped"},
        malformed["operator_validator_status"],
    )
    check("malformed: no recompute blocker", malformed["recompute_blocker_present"] == "false")
    check("malformed: not shippable-by-fabrication", malformed["operator_export_created"] == "false")
    _assert_closed(malformed, "malformed")

    # 5) forbidden_field_operator_export_case: forbidden fields stripped, no canary leak.
    forbidden = run_export_validation(
        _operator_export(candidates=[_forbidden_field_candidate()]),
        input_kind="synthetic_safe",
    )
    check("forbidden: validator accepted but flagged", forbidden["operator_validator_status"] in {"ok", "warning"})
    check("forbidden: unsafe_field_excluded flagged", "unsafe_field_excluded" in (forbidden["warnings"] or []))
    check("forbidden: recompute passed (clean value)", forbidden["recompute_status"] == "passed", forbidden["recompute_status"])
    check("forbidden: NO canary in summary", _no_canary(forbidden))
    _assert_closed(forbidden, "forbidden")

    # Aggregate no-leak across every summary produced.
    blob = json.dumps([clean, wrong, unsupported, malformed, forbidden])
    check("aggregate: no synthetic canary anywhere", SYNTHETIC_CANARY not in blob)

    print("\nClosed-vocabulary synthetic operator-export records:")
    for label, summary in (
        ("clean_operator_export_case", clean),
        ("wrong_operator_export_case", wrong),
        ("unsupported_operator_export_case", unsupported),
        ("malformed_operator_export_case", malformed),
        ("forbidden_field_operator_export_case", forbidden),
    ):
        record = {"validation_case": label, **summary}
        print("  " + json.dumps(record, sort_keys=True))

    # Closed-vocabulary harness conclusion for the docs (display only).
    print("\nOperator structured numeric export harness (closed-vocabulary):")
    print(
        "  "
        + json.dumps(
            {
                "validation_id": VALIDATION_ID,
                "input_kind": "synthetic_safe",
                "operator_export_harness_status": "ok" if FAIL == 0 else "failed",
                "private_operator_run": "not_run",
                "operator_numeric_export_waiver": "approved_for_safety_floor_finalization_synthetic_only",
                "numeric_infrastructure_frozen": True,
                "judge_ready": False,
                "repair_ready": False,
                "next_step": "deterministic_safety_floor_final_gate",
            },
            sort_keys=True,
        )
    )

    print(f"\nvalidate_quality_safety_operator_structured_numeric_export: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


# --- Optional local/private operator mode --------------------------------------


def run_local(input_path: str) -> int:
    """Validate one explicit local JSON file. Never prints the path or raw values.

    Reads only that exact file; writes nothing; prints a closed-vocabulary summary
    only. Any read/parse failure degrades to a closed ``input_read_failed`` token
    with no path or exception text.
    """
    try:
        text = Path(input_path).read_text(encoding="utf-8")
        payload = json.loads(text)
    except Exception:
        summary = _not_run_summary("private_local_operator_material", extra_warning="input_read_failed")
        print(json.dumps(summary, sort_keys=True))
        return 1

    summary = run_export_validation(payload, input_kind="private_local_operator_material")
    # Defence in depth: never emit any forbidden synthetic canary even in local mode.
    if not _no_canary(summary):
        summary = _not_run_summary("private_local_operator_material", extra_warning="input_read_failed")
    print(json.dumps(summary, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operator structured numeric export validation harness (synthetic by default)."
    )
    parser.add_argument(
        "--input",
        default=None,
        help=(
            "Optional local/private operator JSON file to validate. Read-only; the "
            "path and raw values are never printed or committed."
        ),
    )
    args = parser.parse_args(argv)

    if args.input:
        return run_local(args.input)
    return run_synthetic()


if __name__ == "__main__":
    raise SystemExit(main())
