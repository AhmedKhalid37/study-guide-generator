"""Quality Safety advisory job artifact v1 (Slice 118).

Builds and writes the exact-name ``quality_safety_unified_qa.json`` job artifact
from already-produced, caller-supplied safe inputs. The artifact is advisory
only: it never blocks jobs, repairs text, tunes prompts, or calls providers.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.quality_safety_canonical_matcher import build_quality_safety_canonical_match_report
from pipeline.quality_safety_fact_sheet_producer import run_quality_safety_fact_sheet_producer
from pipeline.quality_safety_leak_scanner import build_quality_safety_leak_report
from pipeline.quality_safety_recompute_verifier import verify_quality_safety_fact_sheet
from pipeline.quality_safety_unified_qa import build_quality_safety_unified_qa_report

VERSION = 1
KIND = "quality_safety_job_artifact"
ARTIFACT_NAME = "quality_safety_unified_qa.json"
SOURCE = "job_runtime"

WARNING_ORDER = (
    "candidate_markdown_missing",
    "extraction_bundle_missing",
    "fact_sheet_component_missing",
    "recompute_component_missing",
    "canonical_component_missing",
    "artifact_write_failed",
    "component_degraded",
    "unsafe_metadata_dropped",
    "max_items_reached",
)
SAFE_WARNINGS = frozenset(WARNING_ORDER)
SAFE_STATUSES = frozenset({"passed", "warning", "failed", "skipped", "partial"})


def build_quality_safety_job_artifact_payload(
    *,
    candidate_markdown: Any = None,
    extraction_bundle: Any = None,
    fixture_spec: Any = None,
    canonical_fixture: Any = None,
    job_metadata: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Return a safe advisory job artifact payload; never raise."""
    warnings: set[str] = set()
    try:
        if job_metadata is not None:
            warnings.add("unsafe_metadata_dropped")

        fact_sheet = None
        verified_sheet = None
        recompute_report = None
        canonical_report = None

        if extraction_bundle is None:
            warnings.update(
                {
                    "extraction_bundle_missing",
                    "fact_sheet_component_missing",
                    "recompute_component_missing",
                }
            )
        else:
            producer = run_quality_safety_fact_sheet_producer(
                extraction_bundle,
                max_items=max_items,
            )
            if _has_warning(producer, "max_items_reached"):
                warnings.add("max_items_reached")
            if producer.get("warnings") or producer.get("status") not in {"completed", "partial"}:
                warnings.add("component_degraded")
            fact_sheet = producer.get("fact_sheet") if isinstance(producer.get("fact_sheet"), dict) else None
            if fact_sheet is None:
                warnings.add("fact_sheet_component_missing")
                warnings.add("recompute_component_missing")
            else:
                verified = verify_quality_safety_fact_sheet(fact_sheet, max_items=max_items)
                verified_sheet = verified.get("fact_sheet") if isinstance(verified, dict) else fact_sheet
                recompute_report = verified.get("report") if isinstance(verified, dict) else None
                if recompute_report is None:
                    warnings.add("recompute_component_missing")

        if canonical_fixture is None:
            warnings.add("canonical_component_missing")
        elif verified_sheet is not None:
            canonical_report = build_quality_safety_canonical_match_report(
                verified_sheet,
                canonical_fixture,
                recompute_report=recompute_report,
                max_items=max_items,
            )
        else:
            warnings.add("canonical_component_missing")

        if not isinstance(candidate_markdown, str) or not candidate_markdown.strip():
            candidate_for_unified = None
            leak_report = None
            warnings.add("candidate_markdown_missing")
        else:
            candidate_for_unified = candidate_markdown
            leak_report = build_quality_safety_leak_report(
                candidate_markdown,
                fact_sheet=verified_sheet or fact_sheet,
                recompute_report=recompute_report,
                canonical_report=canonical_report,
                max_items=max_items,
            )

        unified = build_quality_safety_unified_qa_report(
            candidate_markdown=candidate_for_unified,
            fixture_spec=fixture_spec,
            fact_sheet=verified_sheet or fact_sheet,
            recompute_report=recompute_report,
            canonical_report=canonical_report,
            leak_report=leak_report,
            max_items=max_items,
        )
        if _has_warning(unified, "max_items_reached"):
            warnings.add("max_items_reached")
        return _payload(unified, warnings)
    except Exception:
        unified = build_quality_safety_unified_qa_report(max_items=max_items)
        warnings.add("component_degraded")
        return _payload(unified, warnings)


def write_quality_safety_job_artifact(
    job_dir: Any,
    *,
    candidate_markdown: Any = None,
    extraction_bundle: Any = None,
    fixture_spec: Any = None,
    canonical_fixture: Any = None,
    job_metadata: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Write ``quality_safety_unified_qa.json`` under ``job_dir``; never raise."""
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown,
        extraction_bundle=extraction_bundle,
        fixture_spec=fixture_spec,
        canonical_fixture=canonical_fixture,
        job_metadata=job_metadata,
        max_items=max_items,
    )
    try:
        path = Path(job_dir) / ARTIFACT_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload
    except Exception:
        return _with_job_warnings(payload, {"artifact_write_failed"})


def _payload(unified_report: Any, warnings: set[str]) -> dict[str, Any]:
    unified = unified_report if isinstance(unified_report, dict) else build_quality_safety_unified_qa_report()
    summary = unified.get("summary") if isinstance(unified.get("summary"), dict) else {}
    component_statuses = unified.get("component_statuses") if isinstance(unified.get("component_statuses"), dict) else {}
    blocking_failures = unified.get("blocking_failures") if isinstance(unified.get("blocking_failures"), list) else []
    axes = unified.get("deterministic_axes_0_5") if isinstance(unified.get("deterministic_axes_0_5"), dict) else {}
    ordered_warnings = _ordered(warnings)
    status = unified.get("status") if unified.get("status") in SAFE_STATUSES else "partial"
    return {
        "version": VERSION,
        "kind": KIND,
        "artifact_name": ARTIFACT_NAME,
        "advisory": True,
        "source": SOURCE,
        "status": status,
        "shippable": bool(unified.get("shippable")),
        "safety_floor_green": bool(unified.get("safety_floor_green")),
        "component_statuses": component_statuses,
        "deterministic_axes_0_5": axes,
        "summary": {
            "blocking_failure_count": _int(summary.get("blocking_failure_count")),
            "quality_safety_warning_count": _int(summary.get("warning_count")),
            "component_missing_count": _component_missing_count(component_statuses),
            "deterministic_axis_count": _int(summary.get("deterministic_axis_count")),
            "job_artifact_warning_count": len(ordered_warnings),
        },
        "blocking_failures": blocking_failures,
        "warnings": ordered_warnings,
        "quality_safety_unified_qa": unified,
    }


def _with_job_warnings(payload: dict[str, Any], warnings: set[str]) -> dict[str, Any]:
    existing = set(payload.get("warnings") if isinstance(payload.get("warnings"), list) else [])
    payload = dict(payload)
    payload["warnings"] = _ordered({*existing, *warnings})
    summary = dict(payload.get("summary") if isinstance(payload.get("summary"), dict) else {})
    summary["job_artifact_warning_count"] = len(payload["warnings"])
    payload["summary"] = summary
    return payload


def _component_missing_count(component_statuses: Any) -> int:
    if not isinstance(component_statuses, dict):
        return 0
    return sum(1 for status in component_statuses.values() if status in {"unknown", "skipped"})


def _has_warning(report: Any, token: str) -> bool:
    if not isinstance(report, dict):
        return False
    warnings = report.get("warnings")
    return isinstance(warnings, list) and token in warnings


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    return 0


def _ordered(warnings: set[str]) -> list[str]:
    safe = {token for token in warnings if token in SAFE_WARNINGS}
    return [token for token in WARNING_ORDER if token in safe]
