"""Artifact writer for ``source_coverage_report.json``.

The writer persists the Slice 76 pure report from already-sanitized extraction
metadata and optional visual-manifest counts. It never reads source documents,
images, OCR output, providers, prompts, or rendered artifacts, and it never lets
report writing fail guide generation.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from pipeline.source_coverage_report import build_source_coverage_report

SOURCE_COVERAGE_REPORT_FILENAME = "source_coverage_report.json"

SKIP_REASON_REPORT_UNAVAILABLE = "source_coverage_unavailable"
SKIP_REASON_WRITE_FAILED = "write_failed"
SKIP_REASONS = {
    SKIP_REASON_REPORT_UNAVAILABLE,
    SKIP_REASON_WRITE_FAILED,
}


def write_source_coverage_report(
    job: Any,
    extraction_metadata: Any,
    *,
    visual_manifest: Any = None,
) -> dict[str, Any]:
    """Persist ``source_coverage_report.json`` under ``job.dir``.

    ``extraction_metadata`` is the already-sanitized
    ``extraction_metadata.json``-shaped dict or a skipped/malformed stand-in.
    ``visual_manifest`` is optional and counts-only; malformed values are handled
    by the pure core through closed warning tokens. Any build/write failure
    returns a safe skipped report and never raises into job generation.
    """
    try:
        report = build_source_coverage_report(
            extraction_metadata,
            visual_manifest=visual_manifest,
        )
        job.save_text(
            job.source_coverage_report_json,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        return report
    except Exception as exc:  # never let an advisory artifact break a job
        print(
            f"Source coverage report skipped ({type(exc).__name__}); job continues.",
            file=sys.stderr,
        )
        return write_skipped_source_coverage_report(
            job,
            reason=SKIP_REASON_WRITE_FAILED,
            safe_message="Source coverage report could not be written.",
        )


def write_skipped_source_coverage_report(
    job: Any,
    *,
    reason: str = SKIP_REASON_REPORT_UNAVAILABLE,
    safe_message: str = "Source coverage report could not be produced.",
) -> dict[str, Any]:
    """Best-effort writer for an explicit skipped source coverage artifact."""
    payload = _skipped_report(reason, safe_message)
    try:
        job.save_text(
            job.source_coverage_report_json,
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
        )
    except Exception:
        pass
    return payload


def _skipped_report(reason: Any, safe_message: Any) -> dict[str, Any]:
    safe_reason = reason if reason in SKIP_REASONS else SKIP_REASON_REPORT_UNAVAILABLE
    return build_source_coverage_report(
        {
            "version": 2,
            "kind": "extraction_metadata",
            "status": "skipped",
            "reason": safe_reason,
            "safe_message": str(safe_message)[:300],
        }
    )
