"""Offline quality-safety eval harness skeleton (Slice 108).

Pure, deterministic, synthetic-only measurement helpers for the Quality Safety
Unit phase. This module does not call providers, judges, APIs, renderers, OCR,
or generation. It reads caller-supplied fixture dictionaries and candidate
Markdown strings, then returns JSON-serializable reports containing only closed
statuses/warnings, counts, numeric values, and sanitized synthetic fixture ids.

It intentionally does not persist JSONL records. A future slice can wire these
pure records to an output path after the schema is validated.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

VERSION = 1
FIXTURE_KIND = "quality_safety_fixture"
LAYER1_KIND = "quality_safety_eval_layer1"
REGRESSION_KIND = "quality_safety_regression_record"

REPORT_STATUSES = frozenset({"passed", "warning", "failed", "skipped", "partial"})
CHECK_IDS = (
    "leaked_reasoning",
    "numeric_correctness",
    "worked_answer_completeness",
    "coverage",
    "mock_question_count",
)
CHECK_STATUSES = frozenset({"passed", "warning", "failed", "not_applicable", "unknown"})

FIXTURE_WARNING_ORDER = (
    "malformed_fixture_degraded",
    "invalid_expected_topic_dropped",
    "invalid_numeric_target_dropped",
    "invalid_min_mock_questions_defaulted",
    "invalid_tier_target_defaulted",
    "max_items_reached",
)

REPORT_WARNING_ORDER = (
    "fixture_missing",
    "candidate_markdown_missing",
    "malformed_fixture_degraded",
    "malformed_input_degraded",
    "max_items_reached",
    "numeric_target_missing",
    "expected_topic_missing",
    "mock_question_count_below_minimum",
    "worked_answer_incomplete_signal",
    "leaked_reasoning_signal",
    "numeric_contradiction_signal",
    "numeric_mismatch_signal",
    "coverage_below_target",
)

SOURCE_QUALITIES = frozenset(
    {"clean", "ambiguous_animation_frames", "scanned", "mixed", "synthetic", "unknown"}
)
TIER_KEYS = ("premium", "local")
BLOCKING_CHECK_IDS = frozenset(
    {"leaked_reasoning", "numeric_correctness", "worked_answer_completeness"}
)

# --- Phase 0 real golden-pair layer (Slice 160) -----------------------------
# A separate, strict layer over the synthetic Slice 108 fixtures above. The two
# real golden-pair specs (nn3, ensemble) are closed authored *expectation* data
# only (topics, ground-truth numeric labels/values/tolerances, mock-question
# minimum, tier targets). They are NOT private source/reference documents and
# NOT a general operator-typed known_numbers runtime path. The production
# offline judge stays frozen here by construction: the Phase 0 report skeleton
# always reports judge_ready=False / repair_ready=False with no override.
GOLDEN_PAIR_KIND = "quality_safety_golden_pair"
PHASE0_REPORT_KIND = "quality_safety_phase0_report"
REQUIRED_GOLDEN_PAIR_IDS = ("nn3", "ensemble")
ALLOWED_GOLDEN_PAIR_KEYS = frozenset(
    {
        "version",
        "kind",
        "lecture_id",
        "title",
        "source_quality",
        "expected_topics",
        "ground_truth_numerics",
        "min_mock_questions",
        "tier_targets",
        "fixture_ref",
    }
)
ALLOWED_NUMERIC_KEYS = frozenset({"label", "value", "tol"})
REFERENCE_JUDGE_STATUSES = frozenset({"not_run", "missing", "miscalibrated", "ok"})
REGRESSION_RECORD_STATUSES = frozenset({"shape_only", "not_persisted"})

# Phase 0 Layer-1 deterministic scorer (Slice 161). The scorer runs the closed
# Layer-1 detectors over one validated golden-pair spec and candidate text the
# caller supplies. Golden pairs treat every authored numeric as required, so a
# missing or contradicted numeric is a blocking failure; coverage below the
# threshold is also blocking. ``overall_10`` is intentionally left unscored here
# (a real 0-10 quality score is owned by the later, separate dev-time
# reference-anchored eval judge) and the frozen production offline judge stays
# frozen by construction (judge_ready/repair_ready never true here).
PHASE0_LAYER1_KIND = "quality_safety_phase0_layer1_score"
PHASE0_COVERAGE_THRESHOLD = 0.90

# Phase 0 overall score + regression record (Slice 162). ``overall_10`` here is a
# bounded, deterministic Layer-1-only envelope: it starts at 10.0 and subtracts
# closed penalties for the deterministic detectors. It is explicitly NOT the
# final premium/local 9.5/9.0 product-quality score -- that belongs to the later,
# separate dev-time reference-anchored Layer-2 judge -- so the envelope always
# carries overall_score_kind=layer1_deterministic_only and layer2_judge_included=
# False. The frozen production offline judge stays frozen by construction here:
# judge_ready/repair_ready are never True and cannot be overridden. Regression
# records are closed summaries (lecture id, source quality, tier, counts/statuses
# and bounded numerics) only; they never carry candidate/source/guide/OCR text,
# snippets, paths, filenames, hashes, byte counts, or provider payloads.
PHASE0_OVERALL_SCORE_KIND = "layer1_deterministic_only"
PHASE0_REGRESSION_RECORD_KIND = "phase0_eval_regression_record"
PHASE0_MODEL_TIERS = frozenset({"premium", "local", "unknown"})
PHASE0_BLOCKING_CHECK_IDS = frozenset(
    {"leaked_reasoning", "numeric_correctness", "worked_answer_completeness", "coverage"}
)
PHASE0_REGRESSION_STATUSES = frozenset(
    {"record_only", "not_compared", "regressed", "green", "not_comparable"}
)
# Bounded Layer-1 penalties subtracted from a 10.0 start; the total is clamped to
# [0.0, 10.0]. Blocking detectors carry large penalties; the advisory
# mock-question shortfall carries a small one and never sets shippable=False on
# its own. Coverage shortfall is scaled by how far below the threshold it falls.
PHASE0_PENALTY_LEAKED_REASONING = 6.0
PHASE0_PENALTY_NUMERIC = 6.0
PHASE0_PENALTY_WORKED = 4.0
PHASE0_PENALTY_COVERAGE_MAX = 4.0
PHASE0_PENALTY_MOCK = 0.5
# A drop of more than this versus a previous green run on the same lecture/model
# counts as a regression (per the master roadmap).
PHASE0_REGRESSION_DROP_THRESHOLD = 0.3
PHASE0_COMPARE_WARNINGS = (
    "lecture_mismatch",
    "model_tier_mismatch",
    "previous_overall_missing",
    "current_overall_missing",
)
# Field names that must never appear in a Phase 0 regression record. The JSONL
# writer rejects any record carrying one of these, so no raw candidate/source/
# guide/OCR/table/caption text, snippet, path, filename, hash, byte count, or
# provider payload/prompt/response can be persisted.
PHASE0_FORBIDDEN_RECORD_KEYS = frozenset(
    {
        "candidate_text",
        "candidate",
        "snippet",
        "snippets",
        "text",
        "source_text",
        "guide_text",
        "ocr_text",
        "table_text",
        "caption",
        "captions",
        "filename",
        "path",
        "sha256",
        "hash",
        "bytes",
        "byte_count",
        "prompt",
        "response",
        "payload",
        "raw_json",
        "evidence",
        "quote",
        "quotes",
    }
)


class GoldenPairSpecError(ValueError):
    """Raised when a Phase 0 golden-pair spec is malformed or out of contract."""

_SAFE_ID_RE = re.compile(r"[^a-z0-9 _.-]+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_])-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?![A-Za-z0-9_])"
)
# Alphanumeric run tokenizer used to locate an authored label's span inside a
# candidate line so label-internal numeric parameters are not read as answers.
# Matches the token boundaries that ``_normalize`` produces (it collapses every
# non-``[a-z0-9]`` run to a single space), so a label's normalized tokens line
# up with the line's raw tokens one-for-one.
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_SECRETISH_RE = re.compile(
    r"(https?://|/home/|/mnt/|/tmp/|\\\\|[A-Za-z]:\\|authorization|bearer|"
    r"api[_-]?key|data:|base64|provider payload|ocr|caption|table text|"
    r"\.pdf|\.docx|\.zip|\.png|\.jpg|\.jpeg|\.webp)",
    re.IGNORECASE,
)
_LEAK_SIGNATURES = (
    "wait",
    "actually",
    "unclear",
    "we'll trust",
    "we will trust",
    "it seems",
    "let's infer",
    "i think",
    "presumably",
)
_LEAK_PATTERNS = tuple(
    re.compile(r"\b" + re.escape(token).replace(r"\ ", r"\s+") + r"\b", re.IGNORECASE)
    for token in _LEAK_SIGNATURES
)
_STRUCTURAL_UNCERTAINTY_RE = re.compile(r"(=\s*\?|≈\s*\?|≃\s*\?)")
_WORKED_MARKER_RE = re.compile(r"\b(worked\s+answer|worked\s+solution|solution|answer)\b", re.IGNORECASE)
_UNRESOLVED_RE = re.compile(
    r"(=\s*\?|≈\s*\?|≃\s*\?|answer\s+missing|solution\s+missing|unresolved|incomplete\s+answer)",
    re.IGNORECASE,
)
_MOCK_LINE_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:(?:mock|practice)\s+question\b|q\d+\b(?:[\s:.)-]|$))",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+")


def load_quality_safety_fixture_spec(data: Any) -> dict[str, Any]:
    """Return a normalized synthetic fixture spec; never raise on bad input."""
    warnings: set[str] = set()
    if not isinstance(data, dict):
        warnings.add("malformed_fixture_degraded")
        data = {}

    lecture_id = _safe_fixture_id(data.get("lecture_id"), default="synthetic_eval_fixture")
    title = _safe_fixture_id(data.get("title"), default="Synthetic Eval Fixture")
    source_quality = data.get("source_quality")
    if not isinstance(source_quality, str):
        source_quality = "synthetic"
    source_quality = source_quality.strip().lower()
    if source_quality not in SOURCE_QUALITIES:
        source_quality = "synthetic"

    expected_topics = _load_expected_topics(data.get("expected_topics"), warnings)
    numerics = _load_numeric_targets(data.get("ground_truth_numerics"), warnings)
    min_mock_questions = _load_min_mock_questions(data.get("min_mock_questions"), warnings)
    tier_targets = _load_tier_targets(data.get("tier_targets"), warnings)

    return {
        "version": VERSION,
        "kind": FIXTURE_KIND,
        "lecture_id": lecture_id,
        "title": title,
        "source_quality": source_quality,
        "expected_topics": expected_topics,
        "ground_truth_numerics": numerics,
        "min_mock_questions": min_mock_questions,
        "tier_targets": tier_targets,
        "warnings": _ordered(warnings, FIXTURE_WARNING_ORDER),
    }


def run_quality_safety_layer1_checks(
    candidate_markdown: Any,
    fixture_spec: Any,
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Run deterministic Layer-1 checks over Markdown and a synthetic fixture."""
    report_warnings: set[str] = set()
    if not isinstance(candidate_markdown, str):
        report_warnings.add("candidate_markdown_missing")
        candidate_markdown = ""

    if not isinstance(fixture_spec, dict) or fixture_spec.get("kind") != FIXTURE_KIND:
        report_warnings.add("fixture_missing")
        fixture = load_quality_safety_fixture_spec(fixture_spec)
    else:
        fixture = load_quality_safety_fixture_spec(fixture_spec)
    if fixture.get("warnings"):
        report_warnings.add("malformed_fixture_degraded")

    checks = [
        _check_leaked_reasoning(candidate_markdown, report_warnings),
        _check_numeric_correctness(candidate_markdown, fixture, report_warnings),
        _check_worked_answer_completeness(candidate_markdown, report_warnings),
        _check_coverage(candidate_markdown, fixture, report_warnings),
        _check_mock_question_count(candidate_markdown, fixture, report_warnings),
    ]

    truncated = False
    if isinstance(max_items, int) and not isinstance(max_items, bool):
        cap = max(0, min(max_items, len(checks)))
        if cap < len(checks):
            checks = checks[:cap]
            truncated = True
            report_warnings.add("max_items_reached")

    blocking_failures = [
        check["id"]
        for check in checks
        if check["id"] in BLOCKING_CHECK_IDS and check["status"] == "failed"
    ]
    summary = _layer1_summary(checks, fixture, blocking_failures, report_warnings)
    status = _layer1_status(
        checks=checks,
        blocking_failures=blocking_failures,
        warning_count=len(report_warnings),
        truncated=truncated,
    )
    return {
        "version": VERSION,
        "kind": LAYER1_KIND,
        "status": status,
        "shippable": status == "passed" and not blocking_failures,
        "summary": summary,
        "checks": checks,
        "blocking_failures": blocking_failures,
        "warnings": _ordered(report_warnings, REPORT_WARNING_ORDER),
    }


def run_quality_safety_eval(
    candidate_markdown: Any,
    fixture_spec: Any,
    *,
    run_metadata: dict[str, Any] | None = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Convenience wrapper returning a report and safe regression record."""
    fixture = load_quality_safety_fixture_spec(fixture_spec)
    report = run_quality_safety_layer1_checks(
        candidate_markdown, fixture, max_items=max_items
    )
    metadata = run_metadata if isinstance(run_metadata, dict) else {}
    record = build_quality_safety_regression_record(
        run_id=metadata.get("run_id", "synthetic_run"),
        git_sha=metadata.get("git_sha"),
        model=metadata.get("model"),
        preset=metadata.get("preset"),
        lecture_id=metadata.get("lecture_id", fixture.get("lecture_id")),
        tier=metadata.get("tier"),
        layer1_report=report,
        overall_10=metadata.get("overall_10"),
        previous_record=metadata.get("previous_record"),
    )
    return {"layer1": report, "record": record}


def build_quality_safety_regression_record(
    *,
    run_id: Any,
    git_sha: Any = None,
    model: Any = None,
    preset: Any = None,
    lecture_id: Any = None,
    tier: Any = None,
    layer1_report: dict[str, Any] | None = None,
    overall_10: Any = None,
    previous_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, JSON-serializable future JSONL record."""
    layer1 = layer1_report if isinstance(layer1_report, dict) else None
    score = _safe_score(overall_10)
    shippable = bool(layer1.get("shippable")) if layer1 else False
    warnings = _safe_string_list(layer1.get("warnings")) if layer1 else []
    blocking_failures = _safe_blocking_failures(layer1.get("blocking_failures")) if layer1 else []
    delta_vs_prev = _delta_vs_previous(score, previous_record)
    regressed = _is_regressed(
        current_shippable=shippable,
        current_score=score,
        current_layer1=layer1,
        previous_record=previous_record,
    )

    return {
        "version": VERSION,
        "kind": REGRESSION_KIND,
        "run_id": _safe_meta(run_id, "synthetic_run"),
        "git_sha": _safe_meta(git_sha, "unknown"),
        "model": _safe_meta(model, "unknown"),
        "preset": _safe_meta(preset, "unknown"),
        "lecture_id": _safe_meta(lecture_id, "synthetic_eval_fixture"),
        "tier": _safe_meta(tier, "unknown"),
        "overall_10": score,
        "shippable": shippable,
        "axes": {},
        "layer1": layer1 if layer1 is not None else None,
        "blocking_failures": blocking_failures,
        "warnings": warnings,
        "delta_vs_prev": delta_vs_prev,
        "regressed": regressed,
    }


def load_golden_pair_spec(
    data: Any, *, expected_lecture_id: str | None = None
) -> dict[str, Any]:
    """Strictly validate a single Phase 0 golden-pair spec.

    Unlike ``load_quality_safety_fixture_spec`` (which silently degrades), this
    raises ``GoldenPairSpecError`` on any contract violation, because golden
    pairs are authored specs that must be correct. Unknown keys are rejected so
    no raw source/guide/OCR/caption material can ride along. Returns a
    normalized, JSON-serializable closed spec; never reads any file.
    """
    if not isinstance(data, dict):
        raise GoldenPairSpecError("golden pair spec must be a mapping")

    unknown = set(data) - ALLOWED_GOLDEN_PAIR_KEYS
    if unknown:
        raise GoldenPairSpecError(f"unknown golden pair keys: {sorted(unknown)}")

    kind = data.get("kind", GOLDEN_PAIR_KIND)
    if kind != GOLDEN_PAIR_KIND:
        raise GoldenPairSpecError(f"unexpected golden pair kind: {kind!r}")

    lecture_id = data.get("lecture_id")
    if lecture_id not in REQUIRED_GOLDEN_PAIR_IDS:
        raise GoldenPairSpecError(f"unknown golden pair lecture_id: {lecture_id!r}")
    if expected_lecture_id is not None and lecture_id != expected_lecture_id:
        raise GoldenPairSpecError(
            f"lecture_id {lecture_id!r} does not match expected {expected_lecture_id!r}"
        )

    source_quality = data.get("source_quality")
    if not isinstance(source_quality, str) or source_quality not in SOURCE_QUALITIES:
        raise GoldenPairSpecError(f"invalid source_quality: {source_quality!r}")

    title = _require_safe_label(data.get("title"), "title")
    expected_topics = _require_topics(data.get("expected_topics"))
    numerics = _require_numerics(data.get("ground_truth_numerics"))

    min_mock = data.get("min_mock_questions")
    if isinstance(min_mock, bool) or not isinstance(min_mock, int) or min_mock < 0:
        raise GoldenPairSpecError(f"invalid min_mock_questions: {min_mock!r}")

    tier_targets = _require_tier_targets(data.get("tier_targets"))

    return {
        "version": VERSION,
        "kind": GOLDEN_PAIR_KIND,
        "lecture_id": lecture_id,
        "title": title,
        "source_quality": source_quality,
        "expected_topics": expected_topics,
        "ground_truth_numerics": numerics,
        "min_mock_questions": min_mock,
        "tier_targets": tier_targets,
    }


def load_golden_pair_specs(raw_specs: Any) -> dict[str, dict[str, Any]]:
    """Validate a collection of golden-pair specs as the Phase 0 set.

    The set must be exactly ``{nn3, ensemble}`` with no duplicates and no extra
    lecture ids. Returns a dict keyed by lecture_id. Pure; performs no file IO.
    """
    if not isinstance(raw_specs, (list, tuple)):
        raise GoldenPairSpecError("golden pair specs must be a list")

    specs: dict[str, dict[str, Any]] = {}
    for raw in raw_specs:
        spec = load_golden_pair_spec(raw)
        lecture_id = spec["lecture_id"]
        if lecture_id in specs:
            raise GoldenPairSpecError(f"duplicate golden pair lecture_id: {lecture_id}")
        specs[lecture_id] = spec

    present = set(specs)
    required = set(REQUIRED_GOLDEN_PAIR_IDS)
    if present != required:
        raise GoldenPairSpecError(
            f"golden pair set must be exactly {sorted(required)}, got {sorted(present)}"
        )
    return specs


def build_phase0_report_skeleton(
    golden_pair_spec: Any,
    layer1_report: dict[str, Any] | None = None,
    *,
    overall_10: Any = None,
    reference_anchored_judge_status: str = "not_run",
    regression_record_status: str = "shape_only",
) -> dict[str, Any]:
    """Build the Phase 0 scoreboard record skeleton for one golden pair.

    Holds the shape that later slices fill in: Layer-1 deterministic summary,
    a separate ``overall_10`` and ``shippable``, blocking checks, and tier
    targets. The dev-time reference-anchored judge status is tracked here but is
    kept entirely separate from the frozen production offline judge: this record
    always reports ``judge_ready=False`` and ``repair_ready=False`` and exposes
    no way to flip them. No provider/model is called; no JSONL is persisted.
    """
    if (
        not isinstance(golden_pair_spec, dict)
        or golden_pair_spec.get("kind") != GOLDEN_PAIR_KIND
    ):
        raise GoldenPairSpecError(
            "phase0 report requires a validated golden pair spec"
        )

    if reference_anchored_judge_status not in REFERENCE_JUDGE_STATUSES:
        reference_anchored_judge_status = "not_run"
    if regression_record_status not in REGRESSION_RECORD_STATUSES:
        regression_record_status = "shape_only"

    layer1 = (
        layer1_report
        if isinstance(layer1_report, dict) and layer1_report.get("kind") == LAYER1_KIND
        else None
    )
    if layer1 is not None:
        layer1_status = layer1.get("status")
        layer1_summary = layer1.get("summary")
        shippable = bool(layer1.get("shippable"))
        blocking_checks = _safe_blocking_failures(layer1.get("blocking_failures"))
    else:
        layer1_status = "not_run"
        layer1_summary = None
        shippable = False
        blocking_checks = []

    return {
        "version": VERSION,
        "kind": PHASE0_REPORT_KIND,
        "lecture_id": golden_pair_spec["lecture_id"],
        "source_quality": golden_pair_spec["source_quality"],
        "tier_targets": dict(golden_pair_spec.get("tier_targets", {})),
        "layer1_status": layer1_status,
        "layer1_summary": layer1_summary,
        "overall_10": _safe_score(overall_10),
        "shippable": shippable,
        "blocking_checks": blocking_checks,
        "judge_ready": False,
        "repair_ready": False,
        "reference_anchored_judge_status": reference_anchored_judge_status,
        "regression_record_status": regression_record_status,
    }


def score_phase0_layer1(
    candidate_text: Any,
    golden_spec: Any,
    *,
    reference_anchored_judge_status: str = "not_run",
    regression_record_status: str = "shape_only",
) -> dict[str, Any]:
    """Score caller-supplied candidate guide text against one golden-pair spec.

    Pure, deterministic, in-memory Layer-1 scoring. It reads only the candidate
    string and the closed authored expectation spec (topics, ground-truth
    numeric labels/values/tolerances, mock-question minimum, tier targets) and
    runs the five closed Layer-1 detectors: ``leaked_reasoning``,
    ``numeric_correctness``, ``worked_answer_completeness``, ``coverage``, and
    ``mock_question_count``. It never reads a file, source/reference document,
    ``clean.md``, OCR/caption/table text, provider payload, model, or judge.

    Phase 0 golden-pair gating tightens the synthetic Layer-1 contract: every
    authored numeric is required, so any missing or contradicted numeric is a
    blocking failure, and topic coverage below ``PHASE0_COVERAGE_THRESHOLD`` is
    blocking. ``shippable`` reflects only the deterministic Layer-1 blocking
    gates; advisory checks (mock-question count) never block on their own.

    The returned record is closed and JSON-serializable and holds counts/closed
    statuses only -- no raw candidate text, snippets, matched values, topic
    labels, paths, filenames, hashes, or byte counts. ``overall_10`` is left
    unscored (a 0-10 quality score is owned by the later, separate dev-time
    reference-anchored eval judge, not this deterministic path) and is kept a
    distinct field from ``shippable``. The frozen production offline judge stays
    frozen by construction: this path always reports ``judge_ready=False`` and
    ``repair_ready=False`` with no override. It is not a manual operator
    known_numbers runtime; the closed golden expectations drive it. It does not
    persist any JSONL record.
    """
    spec = load_golden_pair_spec(golden_spec)

    report_warnings: set[str] = set()
    if not isinstance(candidate_text, str):
        report_warnings.add("candidate_markdown_missing")
        candidate_text = ""

    if reference_anchored_judge_status not in REFERENCE_JUDGE_STATUSES:
        reference_anchored_judge_status = "not_run"
    if regression_record_status not in REGRESSION_RECORD_STATUSES:
        regression_record_status = "shape_only"

    leaked = _check_leaked_reasoning(candidate_text, report_warnings)
    numeric = _phase0_numeric_check(
        _check_numeric_correctness(candidate_text, spec, report_warnings)
    )
    worked = _check_worked_answer_completeness(candidate_text, report_warnings)
    coverage = _phase0_coverage_check(
        _check_coverage(candidate_text, spec, report_warnings)
    )
    mock = _phase0_mock_check(
        _check_mock_question_count(candidate_text, spec, report_warnings)
    )
    checks = [leaked, numeric, worked, coverage, mock]

    blocking_checks = [
        check["id"]
        for check in checks
        if check.get("blocking") and check.get("status") == "failed" and check["id"] in CHECK_IDS
    ]
    layer1_status = _layer1_status(
        checks=checks,
        blocking_failures=blocking_checks,
        warning_count=len(report_warnings),
        truncated=False,
    )

    return {
        "version": VERSION,
        "kind": PHASE0_LAYER1_KIND,
        "lecture_id": spec["lecture_id"],
        "source_quality": spec["source_quality"],
        "tier_targets": dict(spec.get("tier_targets", {})),
        "layer1_status": layer1_status,
        "layer1_summary": {
            "blocking_failure_count": len(blocking_checks),
            "advisory_warning_count": len(report_warnings),
            "check_count": len(checks),
            "expected_topic_count": int(coverage.get("expected_topic_count") or 0),
            "matched_topic_count": int(coverage.get("matched_topic_count") or 0),
            "numeric_expected_count": int(numeric.get("expected_count") or 0),
            "numeric_matched_count": int(numeric.get("matched_count") or 0),
            "numeric_missing_count": int(numeric.get("missing_count") or 0),
            "numeric_mismatch_count": int(numeric.get("mismatch_count") or 0),
            "mock_question_count": int(mock.get("count") or 0),
        },
        "shippable": not blocking_checks,
        "overall_10": _safe_score(None),
        "overall_10_basis": "layer1_deterministic_not_scored",
        "blocking_checks": blocking_checks,
        "checks": checks,
        "judge_ready": False,
        "repair_ready": False,
        "reference_anchored_judge_status": reference_anchored_judge_status,
        "regression_record_status": regression_record_status,
        "warnings": _ordered(report_warnings, REPORT_WARNING_ORDER),
    }


def _phase0_numeric_check(numeric: dict[str, Any]) -> dict[str, Any]:
    """Reshape the numeric check to counts-only golden-pair semantics.

    Golden pairs require every authored numeric, so any missing or mismatched
    numeric is a blocking failure. Drops the detailed per-target list (including
    any extracted candidate values) so the record carries counts only.
    """
    if numeric.get("status") == "not_applicable":
        return {
            "id": "numeric_correctness",
            "status": "not_applicable",
            "blocking": False,
            "expected_count": 0,
            "matched_count": 0,
            "missing_count": 0,
            "mismatch_count": 0,
        }
    expected = int(numeric.get("target_count") or 0)
    matched = int(numeric.get("pass_count") or 0)
    missing = int(numeric.get("missing_count") or 0)
    mismatch = int(numeric.get("fail_count") or 0)
    failed = bool(missing or mismatch)
    return {
        "id": "numeric_correctness",
        "status": "failed" if failed else "passed",
        "blocking": failed,
        "expected_count": expected,
        "matched_count": matched,
        "missing_count": missing,
        "mismatch_count": mismatch,
    }


def _phase0_coverage_check(coverage: dict[str, Any]) -> dict[str, Any]:
    """Reshape coverage to counts-only and make below-threshold blocking.

    Drops the authored ``missing_topics`` list so the record carries counts and
    the coverage ratio only.
    """
    if coverage.get("status") == "not_applicable":
        return {
            "id": "coverage",
            "status": "not_applicable",
            "blocking": False,
            "expected_topic_count": 0,
            "matched_topic_count": 0,
            "coverage_ratio": None,
            "threshold": PHASE0_COVERAGE_THRESHOLD,
        }
    expected = int(coverage.get("expected_count") or 0)
    matched = int(coverage.get("observed_count") or 0)
    ratio = coverage.get("coverage_ratio")
    below = isinstance(ratio, (int, float)) and not isinstance(ratio, bool) and ratio < PHASE0_COVERAGE_THRESHOLD
    return {
        "id": "coverage",
        "status": "failed" if below else "passed",
        "blocking": bool(below),
        "expected_topic_count": expected,
        "matched_topic_count": matched,
        "coverage_ratio": ratio,
        "threshold": PHASE0_COVERAGE_THRESHOLD,
    }


def _phase0_mock_check(mock: dict[str, Any]) -> dict[str, Any]:
    """Reshape the mock-question count to the advisory golden-pair shape."""
    count = int(mock.get("mock_question_count") or 0)
    minimum = int(mock.get("minimum_required") or 0)
    return {
        "id": "mock_question_count",
        "status": "passed" if count >= minimum else "warning",
        "blocking": False,
        "count": count,
        "min_required": minimum,
    }


def compute_phase0_overall_10(layer1_record: Any) -> dict[str, Any]:
    """Compute the bounded, deterministic Phase 0 Layer-1 overall envelope.

    Takes a record produced by :func:`score_phase0_layer1` and returns a closed,
    JSON-serializable envelope that holds a separate ``overall_10`` and
    ``shippable``. ``overall_10`` starts at 10.0 and subtracts bounded penalties
    for the deterministic detectors, clamped to ``[0.0, 10.0]`` and rounded to one
    decimal. It is Layer-1 deterministic-only and does NOT include any Layer-2
    judge score: the envelope always reports
    ``overall_score_kind=layer1_deterministic_only`` and
    ``layer2_judge_included=False``. ``shippable`` mirrors the Layer-1 blocking
    gates only; the advisory mock-question shortfall reduces ``overall_10`` but
    never sets ``shippable=False`` on its own. The frozen production offline judge
    stays frozen: ``judge_ready`` and ``repair_ready`` are always ``False`` here
    and cannot be overridden. No file, provider, model, or judge is touched.
    """
    checks = _phase0_checks_by_id(layer1_record)
    blocking_checks = _safe_blocking_failures(
        layer1_record.get("blocking_checks") if isinstance(layer1_record, dict) else None
    )

    score = 10.0
    penalties: dict[str, float] = {}

    if _phase0_check_failed(checks, "leaked_reasoning"):
        penalties["leaked_reasoning"] = PHASE0_PENALTY_LEAKED_REASONING
    if _phase0_check_failed(checks, "numeric_correctness"):
        penalties["numeric_correctness"] = PHASE0_PENALTY_NUMERIC
    if _phase0_check_failed(checks, "worked_answer_completeness"):
        penalties["worked_answer_completeness"] = PHASE0_PENALTY_WORKED

    coverage = checks.get("coverage")
    if isinstance(coverage, dict) and coverage.get("status") == "failed":
        ratio = coverage.get("coverage_ratio")
        threshold = coverage.get("threshold")
        shortfall = 1.0
        if (
            isinstance(ratio, (int, float))
            and not isinstance(ratio, bool)
            and isinstance(threshold, (int, float))
            and not isinstance(threshold, bool)
            and threshold > 0
        ):
            shortfall = max(0.0, min(1.0, (threshold - ratio) / threshold))
        penalties["coverage"] = round(PHASE0_PENALTY_COVERAGE_MAX * shortfall, 4)

    mock = checks.get("mock_question_count")
    if isinstance(mock, dict) and mock.get("status") == "warning":
        penalties["mock_question_count"] = PHASE0_PENALTY_MOCK

    score -= sum(penalties.values())
    overall_10 = max(0.0, min(10.0, round(score, 1)))

    return {
        "kind": "quality_safety_phase0_overall",
        "overall_10": overall_10,
        "overall_score_kind": PHASE0_OVERALL_SCORE_KIND,
        "layer2_judge_included": False,
        "shippable": not blocking_checks,
        "blocking_checks": blocking_checks,
        "penalties": {key: penalties[key] for key in sorted(penalties)},
        "judge_ready": False,
        "repair_ready": False,
    }


def build_phase0_regression_record(
    layer1_record: Any,
    *,
    run_id: Any,
    model_tier: Any,
    candidate_id: Any = None,
    previous_overall_10: Any = None,
) -> dict[str, Any]:
    """Build a closed, append-safe Phase 0 regression record.

    Summarizes one Layer-1 scoring run into a record that is safe to persist or
    commit: it holds only the lecture id, source quality, run/model labels, the
    deterministic ``overall_10`` and ``shippable``, blocking-check ids, per-check
    statuses, and bounded numerics. It never carries candidate/source/guide/OCR/
    table/caption text, snippets, paths, filenames, hashes, byte counts, or
    provider payloads. ``overall_10`` is Layer-1 deterministic-only
    (``layer2_judge_included=False``) and the frozen production offline judge stays
    frozen (``judge_ready``/``repair_ready`` always ``False``). When a previous
    ``overall_10`` is supplied the numeric delta is recorded, but the authoritative
    regression verdict is produced separately by :func:`compare_phase0_regression`.
    """
    envelope = compute_phase0_overall_10(layer1_record)
    overall_10 = envelope["overall_10"]
    record = layer1_record if isinstance(layer1_record, dict) else {}

    previous = _safe_score(previous_overall_10)
    if previous is None:
        regression_status = "record_only"
        delta_overall_10: float | None = None
    else:
        regression_status = "not_compared"
        delta_overall_10 = (
            round(overall_10 - previous, 4) if overall_10 is not None else None
        )

    reference_status = record.get("reference_anchored_judge_status")
    if reference_status not in REFERENCE_JUDGE_STATUSES:
        reference_status = "not_run"

    return {
        "version": VERSION,
        "kind": PHASE0_REGRESSION_RECORD_KIND,
        "lecture_id": _safe_phase0_lecture_id(record.get("lecture_id")),
        "source_quality": _safe_phase0_source_quality(record.get("source_quality")),
        "run_id": _safe_meta(run_id, "synthetic_run"),
        "model_tier": _safe_model_tier(model_tier),
        "candidate_id": _safe_candidate_id(candidate_id),
        "overall_10": overall_10,
        "overall_score_kind": PHASE0_OVERALL_SCORE_KIND,
        "layer2_judge_included": False,
        "shippable": envelope["shippable"],
        "blocking_checks": envelope["blocking_checks"],
        "layer1_status": _safe_layer1_status(record.get("layer1_status")),
        "check_statuses": _phase0_check_statuses(record),
        "judge_ready": False,
        "repair_ready": False,
        "reference_anchored_judge_status": reference_status,
        "regression_status": regression_status,
        "previous_overall_10": previous,
        "delta_overall_10": delta_overall_10,
        "warnings": _safe_string_list(record.get("warnings")),
    }


def append_phase0_regression_record_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append one Phase 0 regression record as a compact JSON line.

    Append-only; never reads a private file. The parent directory must be
    supplied by the caller (there is no default path into ``jobs/`` or
    ``local_operator_baselines/``). The record must be a
    ``phase0_eval_regression_record`` and is rejected if it carries any forbidden
    field (raw text, snippet, path, filename, hash, byte count, payload) or any
    secret-ish token, so no private material can ever be persisted.
    """
    _assert_phase0_regression_record_safe(record)
    line = json.dumps(record, sort_keys=True, separators=(",", ":"))
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def compare_phase0_regression(
    current_record: Any, previous_record: Any
) -> dict[str, Any]:
    """Compare two Phase 0 regression records and return a closed verdict.

    Per the master roadmap, a run regresses if its ``overall_10`` drops by more
    than ``PHASE0_REGRESSION_DROP_THRESHOLD`` versus a previous green run on the
    same lecture/model, or if any previously passing blocking check now fails.
    Returns closed tokens/numerics only; never reads a file or any private
    material. When the records are not comparable (missing, lecture/model
    mismatch, or a missing ``overall_10``) the status is ``not_comparable``.
    """
    warnings: set[str] = set()
    current = current_record if isinstance(current_record, dict) else {}
    previous = previous_record if isinstance(previous_record, dict) else {}

    if not current or not previous:
        return _phase0_not_comparable(warnings)

    if current.get("lecture_id") != previous.get("lecture_id"):
        warnings.add("lecture_mismatch")
    if current.get("model_tier") != previous.get("model_tier"):
        warnings.add("model_tier_mismatch")

    current_score = _safe_score(current.get("overall_10"))
    previous_score = _safe_score(previous.get("overall_10"))
    if current_score is None:
        warnings.add("current_overall_missing")
    if previous_score is None:
        warnings.add("previous_overall_missing")

    if (
        warnings & {"lecture_mismatch", "model_tier_mismatch"}
        or current_score is None
        or previous_score is None
    ):
        return _phase0_not_comparable(warnings)

    overall_delta = round(current_score - previous_score, 4)
    blocking_regression_count = _phase0_blocking_regression_count(current, previous)

    if overall_delta < -PHASE0_REGRESSION_DROP_THRESHOLD or blocking_regression_count:
        status = "regressed"
    else:
        status = "green"

    return {
        "kind": "quality_safety_phase0_regression_compare",
        "regression_status": status,
        "overall_delta": overall_delta,
        "blocking_regression_count": blocking_regression_count,
        "warnings": _ordered(warnings, PHASE0_COMPARE_WARNINGS),
    }


def _phase0_not_comparable(warnings: set[str]) -> dict[str, Any]:
    return {
        "kind": "quality_safety_phase0_regression_compare",
        "regression_status": "not_comparable",
        "overall_delta": None,
        "blocking_regression_count": 0,
        "warnings": _ordered(warnings, PHASE0_COMPARE_WARNINGS),
    }


def _phase0_blocking_regression_count(
    current: dict[str, Any], previous: dict[str, Any]
) -> int:
    current_statuses = _safe_check_statuses(current.get("check_statuses"))
    previous_statuses = _safe_check_statuses(previous.get("check_statuses"))
    count = 0
    for check_id in PHASE0_BLOCKING_CHECK_IDS:
        if (
            previous_statuses.get(check_id) == "passed"
            and current_statuses.get(check_id) == "failed"
        ):
            count += 1
    return count


def _phase0_checks_by_id(layer1_record: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(layer1_record, dict):
        return {}
    checks = layer1_record.get("checks")
    if not isinstance(checks, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in checks:
        if isinstance(item, dict) and item.get("id") in CHECK_IDS:
            out[str(item["id"])] = item
    return out


def _phase0_check_failed(checks: dict[str, dict[str, Any]], check_id: str) -> bool:
    check = checks.get(check_id)
    return isinstance(check, dict) and check.get("status") == "failed"


def _phase0_check_statuses(layer1_record: dict[str, Any]) -> dict[str, str]:
    checks = _phase0_checks_by_id(layer1_record)
    statuses: dict[str, str] = {}
    for check_id in CHECK_IDS:
        check = checks.get(check_id)
        status = check.get("status") if isinstance(check, dict) else None
        if status in CHECK_STATUSES:
            statuses[check_id] = str(status)
    return statuses


def _safe_check_statuses(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, str] = {}
    for key, status in value.items():
        if key in CHECK_IDS and status in CHECK_STATUSES:
            out[str(key)] = str(status)
    return out


def _safe_layer1_status(value: Any) -> str:
    return str(value) if value in REPORT_STATUSES else "unknown"


def _safe_model_tier(value: Any) -> str:
    if isinstance(value, str) and value in PHASE0_MODEL_TIERS:
        return value
    return "unknown"


def _safe_candidate_id(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or len(stripped) > 80 or _SECRETISH_RE.search(stripped):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", stripped):
        return None
    return stripped


def _safe_phase0_lecture_id(value: Any) -> str:
    if value in REQUIRED_GOLDEN_PAIR_IDS:
        return str(value)
    return "unknown"


def _safe_phase0_source_quality(value: Any) -> str:
    if isinstance(value, str) and value in SOURCE_QUALITIES:
        return value
    return "unknown"


def _assert_phase0_regression_record_safe(record: Any) -> None:
    if not isinstance(record, dict):
        raise ValueError("phase0 regression record must be a mapping")
    if record.get("kind") != PHASE0_REGRESSION_RECORD_KIND:
        raise ValueError("not a phase0 regression record")
    forbidden = _collect_forbidden_keys(record)
    if forbidden:
        raise ValueError(f"forbidden record fields: {sorted(forbidden)}")
    try:
        blob = json.dumps(record, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("phase0 regression record is not JSON-serializable") from exc
    if _SECRETISH_RE.search(blob):
        raise ValueError("phase0 regression record contains forbidden tokens")


def _collect_forbidden_keys(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and key.lower() in PHASE0_FORBIDDEN_RECORD_KEYS:
                found.add(key.lower())
            found |= _collect_forbidden_keys(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            found |= _collect_forbidden_keys(item)
    return found


def _require_safe_label(value: Any, field: str) -> str:
    label = _safe_golden_label(value)
    if label is None:
        raise GoldenPairSpecError(f"invalid {field}: {value!r}")
    return label


def _require_topics(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise GoldenPairSpecError("expected_topics must be a non-empty list")
    topics: list[str] = []
    seen: set[str] = set()
    for item in value:
        topic = _safe_golden_label(item)
        if topic is None:
            raise GoldenPairSpecError(f"invalid expected_topic: {item!r}")
        key = _normalize(topic)
        if key in seen:
            continue
        seen.add(key)
        topics.append(topic)
    if not topics:
        raise GoldenPairSpecError("expected_topics resolved to empty")
    return topics


def _require_numerics(value: Any) -> list[dict[str, float | str]]:
    if not isinstance(value, list) or not value:
        raise GoldenPairSpecError("ground_truth_numerics must be a non-empty list")
    numerics: list[dict[str, float | str]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise GoldenPairSpecError(f"invalid numeric target: {item!r}")
        extra = set(item) - ALLOWED_NUMERIC_KEYS
        if extra:
            raise GoldenPairSpecError(f"unknown numeric keys: {sorted(extra)}")
        label = _safe_golden_label(item.get("label"))
        if label is None:
            raise GoldenPairSpecError(f"invalid numeric label: {item.get('label')!r}")
        expected = _finite_float(item.get("value"))
        if expected is None:
            raise GoldenPairSpecError(f"invalid numeric value for {label}")
        tol = _finite_float(item.get("tol"))
        if tol is None or tol < 0:
            raise GoldenPairSpecError(f"invalid numeric tolerance for {label}")
        key = _normalize(label)
        if key in seen:
            raise GoldenPairSpecError(f"duplicate numeric label: {label}")
        seen.add(key)
        numerics.append({"label": label, "value": float(expected), "tol": float(tol)})
    return numerics


def _require_tier_targets(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        raise GoldenPairSpecError("tier_targets must be a mapping")
    extra = set(value) - set(TIER_KEYS)
    if extra:
        raise GoldenPairSpecError(f"unknown tier keys: {sorted(extra)}")
    targets: dict[str, float] = {}
    for key in TIER_KEYS:
        score = _finite_float(value.get(key))
        if score is None or not 0.0 <= score <= 10.0:
            raise GoldenPairSpecError(f"invalid tier target for {key}: {value.get(key)!r}")
        targets[key] = float(score)
    return targets


def _safe_golden_label(value: Any) -> str | None:
    """Return a closed authored label, or None if unsafe/invalid.

    Preserves authored case and math/slash punctuation (e.g. ``ReLU``,
    ``Cross-Entropy``, ``training/inference pipeline``, ``htop_pw0.5_sw0.37``)
    while rejecting any secret-ish, path-ish, URL-ish, or raw-material content.
    """
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    if not cleaned or len(cleaned) > 100:
        return None
    if _SECRETISH_RE.search(cleaned):
        return None
    if not re.search(r"[A-Za-z0-9]", cleaned):
        return None
    return cleaned


def _load_expected_topics(value: Any, warnings: set[str]) -> list[str]:
    topics: list[str] = []
    if value is None:
        return topics
    if not isinstance(value, list):
        warnings.add("invalid_expected_topic_dropped")
        return topics
    seen: set[str] = set()
    for item in value:
        topic = _safe_fixture_id(item, default="")
        if not topic:
            warnings.add("invalid_expected_topic_dropped")
            continue
        key = _normalize(topic)
        if key in seen:
            continue
        seen.add(key)
        topics.append(topic)
    return topics


def _load_numeric_targets(value: Any, warnings: set[str]) -> list[dict[str, float | str]]:
    targets: list[dict[str, float | str]] = []
    if value is None:
        return targets
    if not isinstance(value, list):
        warnings.add("invalid_numeric_target_dropped")
        return targets
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            warnings.add("invalid_numeric_target_dropped")
            continue
        label = _safe_fixture_id(item.get("label"), default="")
        expected = _finite_float(item.get("value"))
        tol = _finite_float(item.get("tol"))
        if not label or expected is None or tol is None or tol < 0:
            warnings.add("invalid_numeric_target_dropped")
            continue
        key = _normalize(label)
        if key in seen:
            continue
        seen.add(key)
        targets.append({"label": label, "value": float(expected), "tol": float(tol)})
    return targets


def _load_min_mock_questions(value: Any, warnings: set[str]) -> int:
    if isinstance(value, bool):
        warnings.add("invalid_min_mock_questions_defaulted")
        return 0
    if isinstance(value, int):
        return max(0, value)
    if value is None:
        return 0
    warnings.add("invalid_min_mock_questions_defaulted")
    return 0


def _load_tier_targets(value: Any, warnings: set[str]) -> dict[str, float]:
    targets: dict[str, float] = {}
    if value is None:
        return targets
    if not isinstance(value, dict):
        warnings.add("invalid_tier_target_defaulted")
        return targets
    for key in TIER_KEYS:
        score = _finite_float(value.get(key))
        if score is None:
            if key in value:
                warnings.add("invalid_tier_target_defaulted")
            continue
        targets[key] = max(0.0, min(10.0, float(score)))
    return targets


def _check_leaked_reasoning(candidate: str, warnings: set[str]) -> dict[str, Any]:
    signature_count = 0
    for pattern in _LEAK_PATTERNS:
        signature_count += len(pattern.findall(candidate))
    structural_count = 0
    for line in candidate.splitlines():
        if _is_mock_question_line(line):
            continue
        if _STRUCTURAL_UNCERTAINTY_RE.search(line) or "?" in line:
            structural_count += 1
    signal_count = signature_count + structural_count
    status = "failed" if signal_count else "passed"
    if signal_count:
        warnings.add("leaked_reasoning_signal")
    return {
        "id": "leaked_reasoning",
        "status": status,
        "blocking": status == "failed",
        "signature_count": signature_count,
        "structural_uncertainty_count": structural_count,
        "signal_count": signal_count,
    }


def _check_numeric_correctness(
    candidate: str, fixture: dict[str, Any], warnings: set[str]
) -> dict[str, Any]:
    targets = fixture.get("ground_truth_numerics")
    if not isinstance(targets, list) or not targets:
        return {
            "id": "numeric_correctness",
            "status": "not_applicable",
            "blocking": False,
            "target_count": 0,
            "pass_count": 0,
            "fail_count": 0,
            "missing_count": 0,
            "targets": [],
        }

    details: list[dict[str, Any]] = []
    pass_count = fail_count = missing_count = 0
    normalized_lines = [(_normalize(line), line) for line in candidate.splitlines()]
    for item in targets:
        label = str(item.get("label", ""))
        expected = float(item.get("value", 0.0))
        tol = float(item.get("tol", 0.0))
        label_norm = _normalize(label)
        values: list[float] = []
        for line_norm, line in normalized_lines:
            if label_norm and label_norm in line_norm:
                values.extend(_extract_numbers(_strip_label_spans(line, label_norm)))
        unique_values = _dedupe_floats(values)
        if not unique_values:
            missing_count += 1
            status = "unknown"
            warnings.add("numeric_target_missing")
        elif _has_numeric_contradiction(unique_values, tol):
            fail_count += 1
            status = "failed"
            warnings.add("numeric_contradiction_signal")
        elif any(abs(value - expected) <= tol for value in unique_values):
            pass_count += 1
            status = "passed"
        else:
            fail_count += 1
            status = "failed"
            warnings.add("numeric_mismatch_signal")
        details.append(
            {
                "label": label,
                "status": status,
                "expected_value": expected,
                "tolerance": tol,
                "found_values": unique_values,
                "distinct_value_count": len(unique_values),
            }
        )

    if fail_count:
        status = "failed"
    elif missing_count:
        status = "unknown"
    else:
        status = "passed"
    return {
        "id": "numeric_correctness",
        "status": status,
        "blocking": status == "failed",
        "target_count": len(targets),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "missing_count": missing_count,
        "targets": details,
    }


def _check_worked_answer_completeness(candidate: str, warnings: set[str]) -> dict[str, Any]:
    in_worked_section = False
    marker_count = 0
    unresolved_count = 0
    for line in candidate.splitlines():
        stripped = line.strip()
        if _HEADING_RE.match(stripped):
            in_worked_section = bool(_WORKED_MARKER_RE.search(stripped))
        marker = bool(_WORKED_MARKER_RE.search(stripped))
        if marker:
            marker_count += 1
        if marker or in_worked_section:
            if _UNRESOLVED_RE.search(stripped) or stripped.endswith("?"):
                unresolved_count += 1
    status = "failed" if unresolved_count else "passed"
    if unresolved_count:
        warnings.add("worked_answer_incomplete_signal")
    return {
        "id": "worked_answer_completeness",
        "status": status,
        "blocking": status == "failed",
        "worked_marker_count": marker_count,
        "unresolved_signal_count": unresolved_count,
    }


def _check_coverage(candidate: str, fixture: dict[str, Any], warnings: set[str]) -> dict[str, Any]:
    topics = fixture.get("expected_topics")
    if not isinstance(topics, list) or not topics:
        return {
            "id": "coverage",
            "status": "not_applicable",
            "blocking": False,
            "expected_count": 0,
            "observed_count": 0,
            "missing_count": 0,
            "coverage_ratio": None,
            "missing_topics": [],
        }
    haystack = _normalize(candidate)
    missing: list[str] = []
    for topic in topics:
        needle = _normalize(topic)
        if not needle or needle not in haystack:
            missing.append(topic)
    observed = len(topics) - len(missing)
    ratio = observed / len(topics) if topics else 1.0
    if missing:
        warnings.add("expected_topic_missing")
    if ratio < 0.9:
        warnings.add("coverage_below_target")
    return {
        "id": "coverage",
        "status": "warning" if ratio < 0.9 else "passed",
        "blocking": False,
        "expected_count": len(topics),
        "observed_count": observed,
        "missing_count": len(missing),
        "coverage_ratio": round(ratio, 4),
        "missing_topics": missing,
    }


def _check_mock_question_count(
    candidate: str, fixture: dict[str, Any], warnings: set[str]
) -> dict[str, Any]:
    minimum = fixture.get("min_mock_questions")
    minimum = minimum if isinstance(minimum, int) and not isinstance(minimum, bool) else 0
    count = sum(1 for line in candidate.splitlines() if _is_mock_question_line(line))
    status = "passed" if count >= minimum else "warning"
    if status == "warning":
        warnings.add("mock_question_count_below_minimum")
    return {
        "id": "mock_question_count",
        "status": status,
        "blocking": False,
        "mock_question_count": count,
        "minimum_required": minimum,
    }


def _layer1_summary(
    checks: list[dict[str, Any]],
    fixture: dict[str, Any],
    blocking_failures: list[str],
    warnings: set[str],
) -> dict[str, Any]:
    by_id = {check["id"]: check for check in checks}
    coverage = by_id.get("coverage", {})
    numeric = by_id.get("numeric_correctness", {})
    mock = by_id.get("mock_question_count", {})
    return {
        "blocking_failure_count": len(blocking_failures),
        "advisory_warning_count": len(warnings),
        "check_count": len(checks),
        "expected_topic_count": int(coverage.get("expected_count") or len(fixture.get("expected_topics") or [])),
        "observed_topic_count": int(coverage.get("observed_count") or 0),
        "numeric_target_count": int(numeric.get("target_count") or len(fixture.get("ground_truth_numerics") or [])),
        "numeric_pass_count": int(numeric.get("pass_count") or 0),
        "numeric_fail_count": int(numeric.get("fail_count") or 0),
        "mock_question_count": int(mock.get("mock_question_count") or 0),
    }


def _layer1_status(
    *,
    checks: list[dict[str, Any]],
    blocking_failures: list[str],
    warning_count: int,
    truncated: bool,
) -> str:
    if not checks:
        return "skipped"
    if blocking_failures:
        return "failed"
    if truncated:
        return "partial"
    if warning_count:
        return "warning"
    return "passed"


def _is_regressed(
    *,
    current_shippable: bool,
    current_score: float | None,
    current_layer1: dict[str, Any] | None,
    previous_record: dict[str, Any] | None,
) -> bool:
    if not isinstance(previous_record, dict):
        return False
    if previous_record.get("shippable") is True and not current_shippable:
        return True
    previous_score = _safe_score(previous_record.get("overall_10"))
    if previous_score is not None and current_score is not None:
        if previous_score - current_score > 0.3:
            return True
    previous_checks = _checks_by_id(_previous_layer1(previous_record))
    current_checks = _checks_by_id(current_layer1)
    for check_id in BLOCKING_CHECK_IDS:
        previous = previous_checks.get(check_id)
        current = current_checks.get(check_id)
        if previous and current and previous.get("status") == "passed" and current.get("status") == "failed":
            return True
    return False


def _delta_vs_previous(
    current_score: float | None, previous_record: dict[str, Any] | None
) -> dict[str, float] | None:
    if not isinstance(previous_record, dict):
        return None
    previous_score = _safe_score(previous_record.get("overall_10"))
    if previous_score is None or current_score is None:
        return None
    return {"overall_10_delta": round(current_score - previous_score, 4)}


def _previous_layer1(previous_record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(previous_record, dict):
        return None
    layer1 = previous_record.get("layer1")
    return layer1 if isinstance(layer1, dict) else None


def _checks_by_id(layer1: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(layer1, dict):
        return {}
    checks = layer1.get("checks")
    if not isinstance(checks, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in checks:
        if isinstance(item, dict) and item.get("id") in CHECK_IDS:
            out[str(item["id"])] = item
    return out


def _safe_blocking_failures(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item in CHECK_IDS]


def _safe_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    allowed = set(REPORT_WARNING_ORDER)
    return [str(item) for item in value if item in allowed]


def _safe_score(value: Any) -> float | None:
    score = _finite_float(value)
    if score is None:
        return None
    return max(0.0, min(10.0, round(float(score), 4)))


def _safe_meta(value: Any, default: str) -> str:
    if not isinstance(value, str):
        return default
    stripped = value.strip()
    if not stripped or len(stripped) > 80 or _SECRETISH_RE.search(stripped):
        return default
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", stripped):
        return default
    return stripped


def _safe_fixture_id(value: Any, *, default: str) -> str:
    if not isinstance(value, str):
        return default
    stripped = " ".join(value.strip().split())
    if not stripped or len(stripped) > 100 or _SECRETISH_RE.search(stripped):
        return default
    cleaned = _SAFE_ID_RE.sub("", stripped.lower()).strip(" ._-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or default


def _normalize(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return _NON_ALNUM_RE.sub(" ", value.lower()).strip()


def _finite_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _strip_label_spans(line: str, label_norm: str) -> str:
    """Remove every occurrence of the matched label from ``line``.

    The Phase 0 numeric check finds an authored label on a line and then reads
    the candidate answer value from that same line. Authored labels routinely
    embed numeric parameters -- for example ``pw=0.5``, ``sw=0.37`` or
    ``-ln 0.57`` -- and those label-internal numbers must never be counted as
    candidate answer values or as numeric contradictions. We locate each
    contiguous run of line tokens that equals the label's normalized token
    sequence and drop that raw span (parameters and all), leaving only the
    surrounding text -- typically the right-hand-side answer after a ``=``,
    ``:`` or ``≈`` -- for number extraction. The line is returned unchanged when
    the label tokens are not found as a contiguous run, so general contradiction
    detection is never weakened.
    """
    label_tokens = label_norm.split()
    if not label_tokens:
        return line
    raw_tokens = [
        (match.group(0).lower(), match.start(), match.end())
        for match in _TOKEN_RE.finditer(line)
    ]
    width = len(label_tokens)
    spans: list[tuple[int, int]] = []
    index = 0
    while index + width <= len(raw_tokens):
        window = raw_tokens[index : index + width]
        if [token for token, _, _ in window] == label_tokens:
            spans.append((window[0][1], window[-1][2]))
            index += width
        else:
            index += 1
    if not spans:
        return line
    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        pieces.append(line[cursor:start])
        pieces.append(" ")
        cursor = end
    pieces.append(line[cursor:])
    return "".join(pieces)


def _extract_numbers(line: str) -> list[float]:
    numbers: list[float] = []
    for match in _NUMBER_RE.finditer(line):
        try:
            value = float(match.group(0))
        except ValueError:
            continue
        if math.isfinite(value):
            numbers.append(value)
    return numbers


def _dedupe_floats(values: list[float]) -> list[float]:
    out: list[float] = []
    seen: set[float] = set()
    for value in values:
        rounded = round(value, 12)
        if rounded in seen:
            continue
        seen.add(rounded)
        out.append(float(value))
    return out


def _has_numeric_contradiction(values: list[float], tolerance: float) -> bool:
    if len(values) < 2:
        return False
    tol = max(float(tolerance), 1e-12)
    for idx, left in enumerate(values):
        for right in values[idx + 1 :]:
            if not math.isclose(left, right, rel_tol=0.0, abs_tol=tol):
                return True
    return False


def _is_mock_question_line(line: str) -> bool:
    return bool(_MOCK_LINE_RE.search(line))


def _ordered(values: set[str], order: tuple[str, ...]) -> list[str]:
    return [token for token in order if token in values]
