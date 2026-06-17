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
from pipeline.quality_safety_extraction_bundle_adapter import (
    build_empty_quality_safety_extraction_coverage_bundle,
    build_quality_safety_extraction_coverage_bundle_from_artifacts,
)
from pipeline.quality_safety_fact_sheet_producer import run_quality_safety_fact_sheet_producer
from pipeline.quality_safety_leak_scanner import build_quality_safety_leak_report
from pipeline.quality_safety_numeric_extraction_mapper import (
    build_empty_quality_safety_numeric_extraction_bundle,
    build_quality_safety_numeric_extraction_bundle,
    map_numeric_extraction_bundle_to_fact_sheet_input,
)
from pipeline.quality_safety_recompute_verifier import verify_quality_safety_fact_sheet
from pipeline.quality_safety_safe_numeric_extractor import (
    extract_quality_safety_numeric_records_from_candidates,
)
from pipeline.quality_safety_structured_numeric_candidate_adapter import (
    adapt_structured_numeric_candidates_to_safe_candidates,
)
from pipeline.quality_safety_unified_qa import build_quality_safety_unified_qa_report

VERSION = 1
KIND = "quality_safety_job_artifact"
ARTIFACT_NAME = "quality_safety_unified_qa.json"
SOURCE = "job_runtime"

# Slice 126: exact-name, job-local *input* sidecar candidate that a future safe
# numeric extractor may drop next to the artifact. It is read-only and optional —
# never created or written in production by this slice — and is never added to the
# generic artifact/export lists or any UI row.
NUMERIC_RECORDS_ARTIFACT_NAME = "quality_safety_numeric_extraction_records.json"

# Slice 130: exact-name, job-local *input* sidecar of caller-supplied, already
# sanitized numeric candidates. It is read-only and optional — never created or
# written in production by this slice — feeds only the Slice 129 safe numeric
# extractor, and is never added to the generic artifact/export lists or any UI row.
# It carries a list of sanitized candidate dicts, or a dict wrapper under a closed
# ``candidates`` key. It must never carry source/OCR/table/caption text, raw
# formulas, numeric prose snippets, filenames, basenames, paths, URLs, provider
# payloads, or raw runtime/artifact JSON; the Slice 125 mapper (the extractor's
# final sanitizer) strips any such fields regardless.
SAFE_NUMERIC_CANDIDATES_ARTIFACT_NAME = "quality_safety_safe_numeric_candidates.json"

# Slice 134: exact-name, job-local *input* sidecar for a future producer-owned
# structured numeric candidate artifact. It is read-only and optional — never
# created or written in production by this slice — and feeds only the Slice 133
# adapter, which then feeds the existing Slice 129 safe candidate path. It is
# internal/non-user-facing and is never added to generic artifact/export lists or
# any UI row.
STRUCTURED_NUMERIC_CANDIDATES_ARTIFACT_NAME = "quality_safety_structured_numeric_candidates.json"

STRUCTURED_ADAPTER_STATUSES = frozenset({"ok", "warning", "skipped", "partial", "failed"})
STRUCTURED_ADAPTER_WARNING_ORDER = (
    "component_missing",
    "structured_numeric_candidates_missing",
    "empty_structured_numeric_artifact",
    "malformed_structured_numeric_artifact_input",
    "unsupported_artifact_kind",
    "missing_candidates",
    "invalid_candidate_dropped",
    "max_items_reached",
    "superseded_by_explicit_records",
    "superseded_by_safe_candidates",
)
STRUCTURED_ADAPTER_WARNINGS = frozenset(STRUCTURED_ADAPTER_WARNING_ORDER)
STRUCTURED_ADAPTER_SUMMARY_KEYS = (
    "input_candidate_count",
    "output_candidate_count",
    "supported_method_count",
    "unsupported_method_count",
    "dropped_candidate_count",
)

# Closed status / warning vocabulary for the advisory safe numeric extractor leg
# (Slice 130). Statuses mirror the Slice 129 extractor payload; ``warnings`` mirror
# its closed payload-warning set widened by the precedence token raised when an
# explicit numeric records sidecar supersedes the safe candidates.
SAFE_EXTRACTOR_STATUSES = frozenset({"ok", "warning", "skipped", "partial", "failed"})
SAFE_EXTRACTOR_WARNING_ORDER = (
    "component_missing",
    "empty_numeric_extraction",
    "malformed_numeric_extraction_input",
    "invalid_numeric_record_dropped",
    "max_items_reached",
    "superseded_by_explicit_records",
)
SAFE_EXTRACTOR_WARNINGS = frozenset(SAFE_EXTRACTOR_WARNING_ORDER)
SAFE_EXTRACTOR_SUMMARY_KEYS = (
    "candidate_count",
    "record_count",
    "supported_method_count",
    "unsupported_method_count",
    "dropped_candidate_count",
)

WARNING_ORDER = (
    "candidate_markdown_missing",
    "extraction_bundle_missing",
    "fact_sheet_component_missing",
    "recompute_component_missing",
    "canonical_component_missing",
    "extraction_coverage_missing",
    "extraction_coverage_degraded",
    "numeric_extraction_missing",
    "numeric_extraction_degraded",
    "artifact_write_failed",
    "component_degraded",
    "unsafe_metadata_dropped",
    "max_items_reached",
)
SAFE_WARNINGS = frozenset(WARNING_ORDER)
SAFE_STATUSES = frozenset({"passed", "warning", "failed", "skipped", "partial"})
# Closed status vocabulary for the advisory structural extraction-coverage leg
# (Slice 122). This is the *structural coverage* bundle from Slice 121, not the
# concept/fact extraction bundle and not numeric recompute evidence.
EXTRACTION_COVERAGE_STATUSES = frozenset({"ok", "warning", "skipped", "partial", "failed"})
# Closed status vocabulary for the advisory numeric extraction leg (Slice 126).
# This is the *numeric fact* bundle from Slice 125 — kept SEPARATE from the
# structural coverage bundle above. Unlike structural coverage, numeric records DO
# feed the concept/fact producer + recompute verifier and may therefore raise a
# recompute blocker (never an upgrade).
NUMERIC_EXTRACTION_STATUSES = frozenset({"ok", "warning", "skipped", "partial", "failed"})
# Closed numeric-bundle warning vocabulary mirrored from the Slice 125 mapper.
NUMERIC_BUNDLE_WARNINGS = frozenset(
    {
        "component_missing",
        "empty_numeric_extraction",
        "malformed_numeric_extraction_input",
        "invalid_numeric_record_dropped",
        "max_items_reached",
    }
)


def build_quality_safety_job_artifact_payload(
    *,
    candidate_markdown: Any = None,
    extraction_bundle: Any = None,
    numeric_extraction_records: Any = None,
    safe_numeric_candidates: Any = None,
    structured_numeric_candidates: Any = None,
    fixture_spec: Any = None,
    canonical_fixture: Any = None,
    job_metadata: Any = None,
    source_coverage_report: Any = None,
    extraction_metadata: Any = None,
    visual_inclusion_plan: Any = None,
    table_candidates_manifest: Any = None,
    table_reconstruction_policy: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Return a safe advisory job artifact payload; never raise.

    The optional structural artifacts (``source_coverage_report``,
    ``extraction_metadata``, ``visual_inclusion_plan``,
    ``table_candidates_manifest``, ``table_reconstruction_policy``) feed only the
    Slice 121 *structural coverage* adapter and are surfaced under
    ``extraction_coverage_*``. They are advisory transparency only: they never
    feed the concept/fact fact-sheet producer, never become numeric recompute
    evidence, and never upgrade ``shippable`` / ``safety_floor_green``.

    ``numeric_extraction_records`` (Slice 126) is an optional, caller-supplied
    list of *sanitized numeric extraction records* (the Slice 124/125 contract
    shape) or a dict wrapper carrying one. When present, it is mapped via the
    Slice 125 numeric extraction mapper into the producer's concept/fact bundle
    shape and run through the existing fact-sheet producer + recompute verifier,
    so a wrong numeric claim CAN raise a recompute blocker (and therefore make the
    advisory ``shippable`` / ``safety_floor_green`` red). It is kept SEPARATE from
    the structural coverage bundle, never invents numeric facts from structural
    coverage, and degrades to a closed ``component_missing`` / ``skipped`` numeric
    state when absent or malformed. This slice wires no production extractor — the
    sidecar is read only when it already exists.

    ``safe_numeric_candidates`` (Slice 130) is an optional, caller-supplied list of
    *already-sanitized numeric candidates* (or a dict wrapper carrying one under a
    closed ``candidates`` key). When present and no explicit
    ``numeric_extraction_records`` were supplied, the candidates are run through the
    Slice 129 safe numeric extractor (whose final sanitizer is the Slice 125 mapper)
    and the resulting records feed the *same* numeric leg as explicit records — so a
    wrong safe-candidate claim CAN raise a recompute blocker. Precedence is
    deterministic: explicit ``numeric_extraction_records`` always win; safe
    candidates are then only summarized (``safe_numeric_extractor_status=skipped``,
    ``superseded_by_explicit_records``) and never merged. The safe extractor never
    parses source/OCR/table/caption text, never reads ``clean.md``, never scans job
    folders, never writes sidecars, and never invents numeric facts from structural
    coverage. The leg degrades to a closed ``skipped`` / ``failed`` state when the
    candidate sidecar is absent or malformed.

    ``structured_numeric_candidates`` (Slice 134) is an optional, caller-supplied
    future-artifact dict with kind ``quality_safety_structured_numeric_candidates``.
    It is adapted through the Slice 133 pure adapter only when explicit numeric
    records and safe candidates are both absent. Precedence is deterministic:
    explicit records > safe candidates > structured candidates. The structured
    adapter section stores only status, count summary, and closed warning tokens;
    adapted candidates flow internally into the safe extractor and are not
    duplicated top-level.
    """
    warnings: set[str] = set()
    coverage_bundle = _build_coverage_bundle(
        source_coverage_report=source_coverage_report,
        extraction_metadata=extraction_metadata,
        visual_inclusion_plan=visual_inclusion_plan,
        table_candidates_manifest=table_candidates_manifest,
        table_reconstruction_policy=table_reconstruction_policy,
        max_items=max_items,
        warnings=warnings,
    )
    structured_safe_candidates, structured_status, structured_summary, structured_warnings = (
        _build_structured_numeric_adapter_section(
            structured_numeric_candidates,
            explicit_records_present=numeric_extraction_records is not None,
            safe_candidates_present=safe_numeric_candidates is not None,
            max_items=max_items,
        )
    )
    effective_safe_candidates = safe_numeric_candidates
    if (
        numeric_extraction_records is None
        and effective_safe_candidates is None
        and structured_safe_candidates is not None
    ):
        effective_safe_candidates = structured_safe_candidates

    # Slice 130/134: deterministic precedence — explicit numeric records win;
    # safe candidates win over structured candidates; structured candidates feed
    # the numeric leg only through adapter -> safe extractor when both are absent.
    safe_records, safe_status, safe_summary, safe_warnings = _build_safe_numeric_section(
        effective_safe_candidates,
        explicit_records_present=numeric_extraction_records is not None,
        max_items=max_items,
    )
    effective_numeric_records = numeric_extraction_records
    if effective_numeric_records is None and safe_records is not None:
        effective_numeric_records = safe_records
    numeric_bundle = _build_numeric_extraction_bundle(
        effective_numeric_records,
        max_items=max_items,
        warnings=warnings,
    )
    try:
        if job_metadata is not None:
            warnings.add("unsafe_metadata_dropped")

        fact_sheet = None
        verified_sheet = None
        recompute_report = None
        canonical_report = None

        # Numeric extraction records feed the concept/fact producer only when no
        # explicit extraction bundle was supplied. Structural coverage never does.
        effective_extraction_bundle = extraction_bundle
        if effective_extraction_bundle is None and numeric_bundle.get("numeric_records"):
            effective_extraction_bundle = map_numeric_extraction_bundle_to_fact_sheet_input(numeric_bundle)

        if effective_extraction_bundle is None:
            warnings.update(
                {
                    "extraction_bundle_missing",
                    "fact_sheet_component_missing",
                    "recompute_component_missing",
                }
            )
        else:
            producer = run_quality_safety_fact_sheet_producer(
                effective_extraction_bundle,
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
        return _payload(
            unified, warnings, coverage_bundle, numeric_bundle,
            structured_status=structured_status,
            structured_summary=structured_summary,
            structured_warnings=structured_warnings,
            safe_status=safe_status, safe_summary=safe_summary, safe_warnings=safe_warnings,
        )
    except Exception:
        unified = build_quality_safety_unified_qa_report(max_items=max_items)
        warnings.add("component_degraded")
        return _payload(
            unified, warnings, coverage_bundle, numeric_bundle,
            structured_status=structured_status,
            structured_summary=structured_summary,
            structured_warnings=structured_warnings,
            safe_status=safe_status, safe_summary=safe_summary, safe_warnings=safe_warnings,
        )


def write_quality_safety_job_artifact(
    job_dir: Any,
    *,
    candidate_markdown: Any = None,
    extraction_bundle: Any = None,
    numeric_extraction_records: Any = None,
    safe_numeric_candidates: Any = None,
    structured_numeric_candidates: Any = None,
    fixture_spec: Any = None,
    canonical_fixture: Any = None,
    job_metadata: Any = None,
    source_coverage_report: Any = None,
    extraction_metadata: Any = None,
    visual_inclusion_plan: Any = None,
    table_candidates_manifest: Any = None,
    table_reconstruction_policy: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Write ``quality_safety_unified_qa.json`` under ``job_dir``; never raise.

    When ``numeric_extraction_records`` is not supplied, the optional read-only
    sidecar ``quality_safety_numeric_extraction_records.json`` is consumed if it
    already exists under ``job_dir`` (never created here). Likewise, when
    ``safe_numeric_candidates`` is not supplied, the optional read-only sidecar
    ``quality_safety_safe_numeric_candidates.json`` is consumed if it already exists
    under ``job_dir`` (never created here). When ``structured_numeric_candidates``
    is not supplied, the optional read-only sidecar
    ``quality_safety_structured_numeric_candidates.json`` is consumed if it already
    exists under ``job_dir`` (never created here). Precedence is explicit numeric
    records > safe candidates > structured candidates; sources are never merged.
    """
    if numeric_extraction_records is None:
        numeric_extraction_records = read_quality_safety_numeric_extraction_records(job_dir)
    if safe_numeric_candidates is None:
        safe_numeric_candidates = read_quality_safety_safe_numeric_candidates(job_dir)
    if structured_numeric_candidates is None:
        structured_numeric_candidates = read_quality_safety_structured_numeric_candidates(job_dir)
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown,
        extraction_bundle=extraction_bundle,
        numeric_extraction_records=numeric_extraction_records,
        safe_numeric_candidates=safe_numeric_candidates,
        structured_numeric_candidates=structured_numeric_candidates,
        fixture_spec=fixture_spec,
        canonical_fixture=canonical_fixture,
        job_metadata=job_metadata,
        source_coverage_report=source_coverage_report,
        extraction_metadata=extraction_metadata,
        visual_inclusion_plan=visual_inclusion_plan,
        table_candidates_manifest=table_candidates_manifest,
        table_reconstruction_policy=table_reconstruction_policy,
        max_items=max_items,
    )
    try:
        path = Path(job_dir) / ARTIFACT_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload
    except Exception:
        return _with_job_warnings(payload, {"artifact_write_failed"})


def read_quality_safety_numeric_extraction_records(job_dir: Any) -> Any:
    """Read the optional numeric extraction records sidecar; never raise.

    Returns the parsed list/dict from ``quality_safety_numeric_extraction_records``
    ``.json`` under ``job_dir`` when it exists, else ``None``. Read-only: the
    sidecar is an *input* candidate for a future safe numeric extractor and is
    never created or written here. The returned value is sanitized downstream by
    the Slice 125 mapper; no raw content is trusted.
    """
    try:
        path = Path(job_dir) / NUMERIC_RECORDS_ARTIFACT_NAME
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, (list, dict)) else None
    except Exception:
        return None


def read_quality_safety_safe_numeric_candidates(job_dir: Any) -> Any:
    """Read the optional safe numeric candidate sidecar; never raise.

    Returns the parsed list/dict from ``quality_safety_safe_numeric_candidates``
    ``.json`` under ``job_dir`` when it exists, else ``None``. Read-only: the sidecar
    is an *input* candidate for the Slice 129 safe numeric extractor and is never
    created or written here. The returned value is sanitized downstream by the
    extractor (final sanitizer = Slice 125 mapper); no raw content is trusted.
    """
    try:
        path = Path(job_dir) / SAFE_NUMERIC_CANDIDATES_ARTIFACT_NAME
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, (list, dict)) else None
    except Exception:
        return None


def read_quality_safety_structured_numeric_candidates(job_dir: Any) -> Any:
    """Read the optional structured numeric candidate sidecar; never raise.

    Returns the parsed dict from ``quality_safety_structured_numeric_candidates``
    ``.json`` under ``job_dir`` when it exists, else ``None``. Read-only: the
    sidecar is an *input* candidate for a future producer and is never created or
    written here. The returned value is sanitized downstream by the Slice 133
    adapter, then by the Slice 129 extractor and Slice 125 mapper; no raw content
    is trusted.
    """
    try:
        path = Path(job_dir) / STRUCTURED_NUMERIC_CANDIDATES_ARTIFACT_NAME
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _payload(
    unified_report: Any,
    warnings: set[str],
    coverage_bundle: Any = None,
    numeric_bundle: Any = None,
    *,
    structured_status: str = "skipped",
    structured_summary: Any = None,
    structured_warnings: Any = None,
    safe_status: str = "skipped",
    safe_summary: Any = None,
    safe_warnings: Any = None,
) -> dict[str, Any]:
    unified = unified_report if isinstance(unified_report, dict) else build_quality_safety_unified_qa_report()
    summary = unified.get("summary") if isinstance(unified.get("summary"), dict) else {}
    component_statuses = unified.get("component_statuses") if isinstance(unified.get("component_statuses"), dict) else {}
    blocking_failures = unified.get("blocking_failures") if isinstance(unified.get("blocking_failures"), list) else []
    axes = unified.get("deterministic_axes_0_5") if isinstance(unified.get("deterministic_axes_0_5"), dict) else {}
    ordered_warnings = _ordered(warnings)
    status = unified.get("status") if unified.get("status") in SAFE_STATUSES else "partial"
    bundle = coverage_bundle if isinstance(coverage_bundle, dict) else build_empty_quality_safety_extraction_coverage_bundle("component_missing")
    coverage_status = bundle.get("status") if bundle.get("status") in EXTRACTION_COVERAGE_STATUSES else "failed"
    numeric = numeric_bundle if isinstance(numeric_bundle, dict) else build_empty_quality_safety_numeric_extraction_bundle("component_missing")
    numeric_status = numeric.get("status") if numeric.get("status") in NUMERIC_EXTRACTION_STATUSES else "failed"
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
        "extraction_coverage_status": coverage_status,
        "extraction_coverage_summary": _coverage_summary(bundle),
        "extraction_coverage_bundle": bundle,
        "numeric_extraction_status": numeric_status,
        "numeric_extraction_summary": _numeric_summary(numeric),
        "numeric_extraction_warnings": _numeric_warnings(numeric),
        "numeric_extraction_bundle": numeric,
        "structured_numeric_candidate_adapter_status": (
            structured_status if structured_status in STRUCTURED_ADAPTER_STATUSES else "failed"
        ),
        "structured_numeric_candidate_adapter_summary": _structured_summary(structured_summary),
        "structured_numeric_candidate_adapter_warnings": _structured_warnings(structured_warnings),
        "safe_numeric_extractor_status": safe_status if safe_status in SAFE_EXTRACTOR_STATUSES else "failed",
        "safe_numeric_extractor_summary": _safe_summary(safe_summary),
        "safe_numeric_extractor_warnings": _safe_warnings(safe_warnings),
        "quality_safety_unified_qa": unified,
    }


def _build_numeric_extraction_bundle(
    numeric_extraction_records: Any,
    *,
    max_items: Any,
    warnings: set[str],
) -> dict[str, Any]:
    """Build the advisory numeric extraction bundle via the Slice 125 mapper.

    Never raises. Records a closed job-artifact warning when the numeric leg is
    absent (``numeric_extraction_missing``) or degraded
    (``numeric_extraction_degraded``). Numeric records are NEVER derived from the
    structural coverage bundle.
    """
    if numeric_extraction_records is None:
        bundle = build_empty_quality_safety_numeric_extraction_bundle("component_missing")
    else:
        try:
            bundle = build_quality_safety_numeric_extraction_bundle(
                _coerce_numeric_records(numeric_extraction_records),
                max_items=max_items,
            )
        except Exception:
            bundle = build_empty_quality_safety_numeric_extraction_bundle("malformed_numeric_extraction_input")
    if not isinstance(bundle, dict):
        bundle = build_empty_quality_safety_numeric_extraction_bundle("malformed_numeric_extraction_input")
    status = bundle.get("status")
    if status == "skipped":
        warnings.add("numeric_extraction_missing")
    elif status in {"warning", "partial", "failed"}:
        warnings.add("numeric_extraction_degraded")
    return bundle


def _build_safe_numeric_section(
    safe_numeric_candidates: Any,
    *,
    explicit_records_present: bool,
    max_items: Any,
) -> tuple[Any, str, dict[str, int], list[str]]:
    """Run the Slice 129 safe numeric extractor over caller candidates; never raise.

    Returns ``(effective_records, status, summary, warnings)`` where
    ``effective_records`` is the extractor's ``quality_safety_numeric_extraction``
    ``_records`` payload (records under a closed ``records`` key, consumed by
    ``_coerce_numeric_records``) to feed the numeric leg when no explicit records
    were supplied — else ``None``. When explicit numeric records ARE present they
    win deterministically: the candidates are still summarized but the safe leg is
    marked ``skipped`` + ``superseded_by_explicit_records`` and never fed/merged.
    Structural coverage is never an input here; numeric facts are never fabricated.
    """
    if safe_numeric_candidates is None:
        return None, "skipped", _empty_safe_summary(), []
    try:
        payload = extract_quality_safety_numeric_records_from_candidates(
            _coerce_safe_candidates(safe_numeric_candidates),
            max_items=max_items,
        )
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return None, "failed", _empty_safe_summary(), ["malformed_numeric_extraction_input"]

    summary = _safe_summary(payload.get("summary"))
    section_warnings = [w for w in payload.get("warnings", []) if w in SAFE_EXTRACTOR_WARNINGS]
    status = payload.get("status") if payload.get("status") in SAFE_EXTRACTOR_STATUSES else "failed"

    if explicit_records_present:
        # Deterministic precedence: explicit numeric records win. The safe leg is
        # summarized only — never fed into the numeric bundle, never merged.
        if "superseded_by_explicit_records" not in section_warnings:
            section_warnings.append("superseded_by_explicit_records")
        return None, "skipped", summary, _ordered_safe(section_warnings)

    return payload, status, summary, _ordered_safe(section_warnings)


def _build_structured_numeric_adapter_section(
    structured_numeric_candidates: Any,
    *,
    explicit_records_present: bool,
    safe_candidates_present: bool,
    max_items: Any,
) -> tuple[Any, str, dict[str, int], list[str]]:
    """Adapt the future structured sidecar into safe candidates; never raise.

    Returns ``(adapter_payload, status, summary, warnings)`` where
    ``adapter_payload`` is fed into the safe numeric extractor only when it is the
    winning source. Explicit records and safe candidates supersede it; Slice 134
    never merges numeric sources.
    """
    if structured_numeric_candidates is None:
        return (
            None,
            "skipped",
            _empty_structured_summary(),
            ["structured_numeric_candidates_missing"],
        )

    if explicit_records_present:
        return (
            None,
            "skipped",
            _empty_structured_summary(),
            ["superseded_by_explicit_records"],
        )
    if safe_candidates_present:
        return (
            None,
            "skipped",
            _empty_structured_summary(),
            ["superseded_by_safe_candidates"],
        )

    try:
        payload = adapt_structured_numeric_candidates_to_safe_candidates(
            structured_numeric_candidates,
            max_items=max_items,
        )
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return (
            None,
            "failed",
            _empty_structured_summary(),
            ["malformed_structured_numeric_artifact_input"],
        )

    summary = _structured_summary(payload.get("summary"))
    section_warnings = _structured_warnings(payload.get("warnings"))
    status = payload.get("status") if payload.get("status") in STRUCTURED_ADAPTER_STATUSES else "failed"
    if any(
        token in section_warnings
        for token in ("malformed_structured_numeric_artifact_input", "unsupported_artifact_kind")
    ):
        status = "failed"

    return payload, status, summary, section_warnings


def _coerce_safe_candidates(value: Any) -> Any:
    """Extract a candidates list from a caller value; let the extractor judge rest.

    Accepts a bare list of sanitized candidate dicts, or a dict wrapper carrying one
    under the closed ``candidates`` key. Any other shape is passed through unchanged
    so the extractor degrades it to a closed ``failed`` payload.
    """
    if isinstance(value, dict):
        inner = value.get("candidates")
        if isinstance(inner, list):
            return inner
    return value


def _empty_safe_summary() -> dict[str, int]:
    return {key: 0 for key in SAFE_EXTRACTOR_SUMMARY_KEYS}


def _empty_structured_summary() -> dict[str, int]:
    return {key: 0 for key in STRUCTURED_ADAPTER_SUMMARY_KEYS}


def _structured_summary(summary: Any) -> dict[str, int]:
    safe = summary if isinstance(summary, dict) else {}
    return {key: _int(safe.get(key)) for key in STRUCTURED_ADAPTER_SUMMARY_KEYS}


def _structured_warnings(warnings: Any) -> list[str]:
    if not isinstance(warnings, list):
        return []
    safe = {token for token in warnings if isinstance(token, str) and token in STRUCTURED_ADAPTER_WARNINGS}
    return [token for token in STRUCTURED_ADAPTER_WARNING_ORDER if token in safe]


def _safe_summary(summary: Any) -> dict[str, int]:
    safe = summary if isinstance(summary, dict) else {}
    return {key: _int(safe.get(key)) for key in SAFE_EXTRACTOR_SUMMARY_KEYS}


def _safe_warnings(warnings: Any) -> list[str]:
    if not isinstance(warnings, list):
        return []
    safe = {token for token in warnings if isinstance(token, str) and token in SAFE_EXTRACTOR_WARNINGS}
    return [token for token in SAFE_EXTRACTOR_WARNING_ORDER if token in safe]


def _ordered_safe(warnings: list[str]) -> list[str]:
    safe = {token for token in warnings if token in SAFE_EXTRACTOR_WARNINGS}
    return [token for token in SAFE_EXTRACTOR_WARNING_ORDER if token in safe]


def _coerce_numeric_records(value: Any) -> Any:
    """Extract a records list from a caller value; let the mapper judge the rest.

    Accepts a bare list of records, or a dict wrapper carrying one under a closed
    set of keys. A dict without a records list (or any other type) is passed
    through unchanged so the mapper degrades it to a closed ``failed`` bundle.
    """
    if isinstance(value, dict):
        for key in ("records", "numeric_records", "numeric_extraction_records"):
            inner = value.get(key)
            if isinstance(inner, list):
                return inner
    return value


def _numeric_summary(bundle: Any) -> dict[str, int]:
    summary = bundle.get("summary") if isinstance(bundle, dict) and isinstance(bundle.get("summary"), dict) else {}
    return {
        "record_count": _int(summary.get("record_count")),
        "numeric_fact_count": _int(summary.get("numeric_fact_count")),
        "computation_record_count": _int(summary.get("computation_record_count")),
        "supported_method_count": _int(summary.get("supported_method_count")),
        "unsupported_method_count": _int(summary.get("unsupported_method_count")),
    }


def _numeric_warnings(bundle: Any) -> list[str]:
    warnings = bundle.get("warnings") if isinstance(bundle, dict) else None
    if not isinstance(warnings, list):
        return []
    return [token for token in warnings if isinstance(token, str) and token in NUMERIC_BUNDLE_WARNINGS]


def _build_coverage_bundle(
    *,
    source_coverage_report: Any,
    extraction_metadata: Any,
    visual_inclusion_plan: Any,
    table_candidates_manifest: Any,
    table_reconstruction_policy: Any,
    max_items: Any,
    warnings: set[str],
) -> dict[str, Any]:
    """Build the advisory structural-coverage bundle; never raise.

    Records a closed job-artifact warning when the bundle is unavailable or
    degraded. Structural coverage is *never* treated as numeric recompute
    evidence and never feeds the concept/fact producer.
    """
    have_any = any(
        isinstance(artifact, dict)
        for artifact in (
            source_coverage_report,
            extraction_metadata,
            visual_inclusion_plan,
            table_candidates_manifest,
            table_reconstruction_policy,
        )
    )
    if not have_any:
        warnings.add("extraction_coverage_missing")
        return build_empty_quality_safety_extraction_coverage_bundle("component_missing")
    try:
        bundle = build_quality_safety_extraction_coverage_bundle_from_artifacts(
            source_coverage_report=source_coverage_report,
            extraction_metadata=extraction_metadata,
            visual_inclusion_plan=visual_inclusion_plan,
            table_candidates_manifest=table_candidates_manifest,
            table_reconstruction_policy=table_reconstruction_policy,
            max_items=max_items,
        )
    except Exception:
        warnings.add("extraction_coverage_degraded")
        return build_empty_quality_safety_extraction_coverage_bundle("component_missing")
    if not isinstance(bundle, dict):
        warnings.add("extraction_coverage_degraded")
        return build_empty_quality_safety_extraction_coverage_bundle("component_missing")
    status = bundle.get("status")
    if status == "skipped":
        warnings.add("extraction_coverage_missing")
    elif status in {"warning", "partial", "failed"}:
        warnings.add("extraction_coverage_degraded")
    return bundle


def _coverage_summary(bundle: Any) -> dict[str, Any]:
    summary = bundle.get("summary") if isinstance(bundle, dict) and isinstance(bundle.get("summary"), dict) else {}
    selected = summary.get("selected_page_count")
    return {
        "source_count": _int(summary.get("source_count")),
        "page_count": _int(summary.get("page_count")),
        "selected_page_count": selected if isinstance(selected, int) and not isinstance(selected, bool) else None,
        "visual_count": _int(summary.get("visual_count")),
        "table_count": _int(summary.get("table_count")),
        "coverage_item_count": _int(summary.get("coverage_item_count")),
        # Structural coverage carries no numeric content observations by policy.
        "numeric_observation_count": 0,
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
