#!/usr/bin/env python3
"""Slice 124 — Numeric extraction contract checks (pure, synthetic-only).

This harness validates the *design contract* in
``docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`` against the existing pure
building blocks, without adding any production mapper. It builds synthetic
numeric extraction records (the contract shape), maps them locally to the
existing ``quality_safety_extraction_bundle`` shape, and confirms they normalize
into the Slice 110 fact-sheet schema and round-trip through the Slice 111
recompute verifier with only numeric structured inputs.

It proves, with synthetic data only:
  * each supported method recomputes from numeric structured inputs;
  * a correct synthetic claim verifies; a wrong one fails (blocking);
  * forbidden string fields are never carried into the produced fact sheet;
  * finite numeric bounds and tolerance caps hold;
  * the local contract-to-bundle mapping does not mutate the caller's input;
  * no synthetic canary leaks into any produced structure.

Pure: stdlib + the two pure quality-safety modules only. No providers, models,
cloud, judge, repair, OCR, table parsing, routes, or source/clean.md reads.

Run:  python test_scripts/test_quality_safety_numeric_extraction_contract.py
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_fact_sheet_producer import (  # noqa: E402
    run_quality_safety_fact_sheet_producer,
)
from pipeline.quality_safety_recompute_verifier import (  # noqa: E402
    SUPPORTED_METHODS,
    build_quality_safety_recompute_report,
)

PASS = 0
FAIL = 0

SYNTHETIC_CANARY = "ZZSYNTH_CONTRACT_PRIVATE_MARKER_ONLY"

# Closed allow-list mirrored from the contract doc (kept in sync intentionally).
ALLOWED_RECORD_FIELDS = frozenset(
    {
        "id",
        "concept_id",
        "label",
        "fact_type",
        "value",
        "unit",
        "provenance",
        "confidence",
        "source_ref",
        "page_ref",
        "computation",
        "tolerance",
        "warnings",
    }
)
FORBIDDEN_RECORD_FIELDS = frozenset(
    {
        "raw_text",
        "source_text",
        "guide_text",
        "ocr_text",
        "table_cells",
        "captions",
        "formulas_as_text",
        "evidence_quotes",
        "filenames",
        "basenames",
        "paths",
        "urls",
        "provider_payloads",
        "runtime_traces",
        "raw_exceptions",
    }
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


# --- Synthetic numeric extraction records (the contract shape) --------------
# Illustrative synthetic placeholders only. No private content.

def computation_record(
    *,
    rec_id: str,
    label: str,
    method: str,
    inputs: dict[str, Any],
    value: float,
    tolerance: float = 0.01,
) -> dict[str, Any]:
    return {
        "id": rec_id,
        "concept_id": "synthetic_concept",
        "label": label,
        "fact_type": "numeric",
        "value": value,
        "unit": "ratio",
        "provenance": "computed",
        "confidence": "medium",
        "source_ref": "source_page_1",
        "page_ref": "page_1",
        "computation": {"method": method, "inputs": inputs},
        "tolerance": tolerance,
    }


SUPPORTED_METHOD_FIXTURES: dict[str, dict[str, Any]] = {
    "weighted_gini": {
        "inputs": {"groups": [{"yes": 3, "no": 0}, {"yes": 1, "no": 4}]},
        "value": 0.2,
    },
    "total_error": {"inputs": {"misclassified_weight": 0.3}, "value": 0.3},
    "amount_of_say": {"inputs": {"total_error": 0.25}, "value": 0.5493061443340549},
    "softmax": {"inputs": {"values": [1.0, 2.0, 3.0], "index": 2}, "value": 0.6652409557748218},
    "cross_entropy": {"inputs": {"probability": 0.5}, "value": 0.6931471805599453},
    "forward_pass": {
        "inputs": {"inputs": {"x1": 1.0, "x2": 2.0}, "weights": {"x1": 0.5, "x2": 0.5}, "bias": 0.0},
        "value": 1.5,
    },
}


def numeric_observation_record(*, obs_id: str, label: str, value: float) -> dict[str, Any]:
    return {
        "id": obs_id,
        "concept_id": "synthetic_concept",
        "label": label,
        "fact_type": "numeric",
        "value": value,
        "unit": "count",
        "provenance": "extracted_high",
        "confidence": "high",
        "source_ref": "source_page_2",
    }


def _is_recomputable(record: dict[str, Any]) -> bool:
    computation = record.get("computation")
    return isinstance(computation, dict) and computation.get("method") in SUPPORTED_METHODS


def map_records_to_extraction_bundle(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Local, pure contract->bundle mapping (NOT a production mapper).

    Groups contract records by ``concept_id`` into the existing
    ``quality_safety_extraction_bundle`` shape consumed by the Slice 117 producer.
    Only allow-listed fields are forwarded; forbidden fields are never copied.
    """
    by_concept: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        # Hard contract boundary: silently exclude any forbidden field.
        safe = {key: value for key, value in record.items() if key in ALLOWED_RECORD_FIELDS}
        if safe.get("fact_type") != "numeric":
            continue
        concept_id = safe.get("concept_id") or "synthetic_concept"
        bucket = by_concept.setdefault(concept_id, {"records": [], "observations": []})
        if _is_recomputable(safe):
            computation = safe["computation"]
            bucket["records"].append(
                {
                    "id": safe.get("id"),
                    "label": safe.get("label"),
                    "method": computation.get("method"),
                    "inputs": computation.get("inputs"),
                    "claimed_value": safe.get("value"),
                    "tolerance": safe.get("tolerance"),
                    "source_ref": safe.get("source_ref"),
                    "confidence": safe.get("confidence"),
                }
            )
        else:
            bucket["observations"].append(
                {
                    "id": safe.get("id"),
                    "label": safe.get("label"),
                    "value": safe.get("value"),
                    "tolerance": safe.get("tolerance"),
                    "source_ref": safe.get("source_ref"),
                    "confidence": safe.get("confidence"),
                }
            )
    concepts = [
        {
            "concept": "Synthetic Concept",
            "source_ref": "source_page_1",
            "computation_records": payload["records"],
            "numeric_observations": payload["observations"],
        }
        for payload in by_concept.values()
    ]
    return {
        "version": 1,
        "kind": "quality_safety_extraction_bundle",
        "lecture_id": "synthetic_fixture",
        "source_quality": "synthetic",
        "concepts": concepts,
    }


def _no_forbidden_keys(obj: object) -> bool:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in FORBIDDEN_RECORD_FIELDS or not _no_forbidden_keys(value):
                return False
        return True
    if isinstance(obj, list):
        return all(_no_forbidden_keys(item) for item in obj)
    return True


def main() -> int:
    # --- 1. Every supported method recomputes from numeric structured inputs --
    for method, fixture in SUPPORTED_METHOD_FIXTURES.items():
        record = computation_record(
            rec_id=f"synthetic.{method}.fact",
            label=f"synthetic_{method}_score",
            method=method,
            inputs=fixture["inputs"],
            value=fixture["value"],
        )
        bundle = map_records_to_extraction_bundle([record])
        produced = run_quality_safety_fact_sheet_producer(bundle)
        report = build_quality_safety_recompute_report(produced.get("fact_sheet"))
        passed = [c for c in report.get("checks", []) if c.get("check_id") == method and c.get("status") == "passed"]
        check(f"method {method}: correct synthetic claim verifies", bool(passed), json.dumps(report.get("checks")))
        check(f"method {method}: no blocking failure", not report.get("blocking_failures"))

    # --- 2. A wrong numeric claim fails (blocking) ----------------------------
    wrong = computation_record(
        rec_id="synthetic.weighted_gini.wrong",
        label="synthetic_weighted_gini_score",
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"]["inputs"],
        value=0.9,  # deliberately wrong vs recomputed 0.2
    )
    wrong_report = build_quality_safety_recompute_report(
        run_quality_safety_fact_sheet_producer(map_records_to_extraction_bundle([wrong])).get("fact_sheet")
    )
    check(
        "wrong claim: recompute blocking failure raised",
        any(item.get("check_id") == "weighted_gini" for item in wrong_report.get("blocking_failures") or []),
        json.dumps(wrong_report.get("blocking_failures")),
    )
    check("wrong claim: report status failed", wrong_report.get("status") == "failed")

    # --- 3. A bare numeric observation is not recomputable, never blocks ------
    obs = numeric_observation_record(obs_id="synthetic.obs.1", label="synthetic_count", value=42)
    obs_bundle = map_records_to_extraction_bundle([obs])
    obs_produced = run_quality_safety_fact_sheet_producer(obs_bundle)
    obs_report = build_quality_safety_recompute_report(obs_produced.get("fact_sheet"))
    check("observation: produced as numeric fact", obs_produced.get("summary", {}).get("numeric_observation_count") == 1)
    check("observation: not a blocking failure", not obs_report.get("blocking_failures"))

    # --- 4. Forbidden string fields never reach the produced fact sheet -------
    tainted = computation_record(
        rec_id="synthetic.tainted.fact",
        label="synthetic_tainted_score",
        method="cross_entropy",
        inputs={"probability": 0.5},
        value=0.6931471805599453,
    )
    tainted["raw_text"] = SYNTHETIC_CANARY
    tainted["source_text"] = SYNTHETIC_CANARY
    tainted["paths"] = "/home/private/secret.pdf"
    tainted_bundle = map_records_to_extraction_bundle([tainted])
    tainted_produced = run_quality_safety_fact_sheet_producer(tainted_bundle)
    check("forbidden fields: excluded from bundle", _no_forbidden_keys(tainted_bundle))
    check("forbidden fields: excluded from produced sheet", _no_forbidden_keys(tainted_produced))
    blob = json.dumps([tainted_bundle, tainted_produced])
    check("forbidden fields: canary never leaks", SYNTHETIC_CANARY not in blob)
    check("forbidden fields: private path never leaks", "/home/" not in blob)

    # --- 5. Finite numeric bounds / tolerance cap honored ---------------------
    nonfinite = computation_record(
        rec_id="synthetic.nonfinite.fact",
        label="synthetic_nonfinite_score",
        method="total_error",
        inputs={"misclassified_weight": 0.3},
        value=0.3,
        tolerance=5.0,  # above the (0, 1] cap -> must be ignored, not honored
    )
    nf_bundle = map_records_to_extraction_bundle([nonfinite])
    nf_record = nf_bundle["concepts"][0]["computation_records"][0]
    # The producer normalizes the bundle; the out-of-cap tolerance must not pass through raw.
    nf_produced = run_quality_safety_fact_sheet_producer(nf_bundle)
    nf_fact = nf_produced["fact_sheet"]["concepts"][0]["facts"][0]
    tol = nf_fact.get("computation", {}).get("tolerance")
    check("tolerance cap: normalized within (0, 1]", tol is None or (0.0 < float(tol) <= 1.0), str(tol))
    check("tolerance cap: raw 5.0 not present", nf_record.get("tolerance") != 5.0 or tol != 5.0)

    # --- 6. No mutation of caller input ---------------------------------------
    records = [
        computation_record(
            rec_id="synthetic.softmax.fact",
            label="synthetic_softmax_score",
            method="softmax",
            inputs={"values": [1.0, 2.0, 3.0], "index": 2},
            value=0.6652409557748218,
        )
    ]
    snapshot = copy.deepcopy(records)
    _ = map_records_to_extraction_bundle(records)
    _ = run_quality_safety_fact_sheet_producer(map_records_to_extraction_bundle(records))
    check("no mutation: caller records unchanged", records == snapshot)

    # --- 7. Compatibility deep-walk: produced structures are JSON + closed ----
    multi = [
        computation_record(
            rec_id=f"synthetic.{method}.multi",
            label=f"synthetic_{method}_multi",
            method=method,
            inputs=fixture["inputs"],
            value=fixture["value"],
        )
        for method, fixture in SUPPORTED_METHOD_FIXTURES.items()
    ]
    multi_bundle = map_records_to_extraction_bundle(multi)
    multi_produced = run_quality_safety_fact_sheet_producer(multi_bundle)
    multi_report = build_quality_safety_recompute_report(multi_produced.get("fact_sheet"))
    check("compat: producer result JSON-serializable", isinstance(json.dumps(multi_produced), str))
    check("compat: recompute report JSON-serializable", isinstance(json.dumps(multi_report), str))
    check("compat: all supported methods verified together", multi_report.get("status") == "passed", json.dumps(multi_report.get("summary")))
    check("compat: no forbidden keys in report", _no_forbidden_keys(multi_report))

    print(f"\ntest_quality_safety_numeric_extraction_contract: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
