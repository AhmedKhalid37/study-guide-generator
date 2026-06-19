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

from pipeline.quality_safety_fact_sheet import normalize_quality_safety_fact_sheet
from pipeline.quality_safety_recompute_verifier import verify_quality_safety_fact_sheet

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
    "leak_structural_unknown_present",
    "numeric_contradiction_signal",
    "numeric_mismatch_signal",
    "fact_sheet_invalid",
    "fact_sheet_partial",
    "fact_sheet_unverified_numeric",
    "recompute_verifier_failed",
    "recompute_verifier_partial",
    "committed_numeric_missing",
    "committed_numeric_mismatch",
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
ALLOWED_NUMERIC_KEYS = frozenset({"label", "value", "tol", "aliases"})
# Bound on safe label aliases / concept anchors a single numeric target may carry
# (Slice 170). Aliases are closed, public-safe anchor phrases authored in the
# fixture -- never private guide/source snippets -- so the matcher can attribute a
# value to its target via the concept the guide actually names, not only the
# fixture's internal label code. The cap keeps a target from smuggling material.
MAX_NUMERIC_ALIASES = 16
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

# --- Phase 0 Layer-2 dev-time reference-anchored judge contract (Slice 163) ---
# Closed contract constants for the dev-time, reference-anchored eval judge. This
# judge scores a candidate guide *relative to a Claude reference guide* (the 9-10
# benchmark) on a 0-5 integer scale per axis, with a calibration step (the judge
# must also score the reference itself >= the floor on every axis or the run is
# discarded as miscalibrated). It is a DEV-TIME EVAL contract, NOT the frozen
# production offline judge and NOT a production shippability gate: nothing in this
# module executes a provider/model call, persists prompts/responses, blends a
# Layer-2 score into ``overall_10``, or flips ``judge_ready``/``repair_ready``.
# The prompt construction and output sanitization live in the pure, unwired helper
# module ``pipeline/quality_safety_reference_judge.py`` (which imports these
# constants); the harness here only stores a sanitized, closed Layer-2 *summary*
# when a caller explicitly supplies one to a regression record, and that summary
# never carries evidence quotes, raw model output, prompts, paths, or any other
# forbidden material.
PHASE0_REFERENCE_JUDGE_AXES = (
    "conceptual_depth",
    "beginner_friendliness",
    "explanation_quality",
    "comparison_quality",
    "memory_support",
    "mock_question_quality",
    "density_anti_bloat",
)
PHASE0_REFERENCE_JUDGE_AXIS_SET = frozenset(PHASE0_REFERENCE_JUDGE_AXES)
PHASE0_REFERENCE_AXIS_SCORE_MIN = 0
PHASE0_REFERENCE_AXIS_SCORE_MAX = 5
# The reference (the Claude 9-10 benchmark) must score at least this on every axis
# or the run is miscalibrated and the candidate scores are discarded for scoring.
PHASE0_REFERENCE_CALIBRATION_MIN = 4
PHASE0_EVIDENCE_QUOTE_MAX_WORDS = 15
PHASE0_REFERENCE_JUDGE_RESULT_STATUSES = frozenset(
    {"not_run", "ok", "miscalibrated", "invalid_output", "blocked", "skipped"}
)
PHASE0_REFERENCE_JUDGE_CALIBRATION_STATUSES = frozenset(
    {"not_run", "ok", "miscalibrated"}
)
PHASE0_REFERENCE_JUDGE_SUMMARY_KIND = "quality_safety_phase0_reference_judge_summary"

# Phase 0 fact-sheet schema + recompute verifier integration (Slice 164).
# This is a pure, caller-supplied in-memory integration boundary. It does not
# produce, discover, read, or persist fact sheets, and it never reads jobs/,
# local_operator_baselines/, source/reference PDFs, generated guides, clean.md,
# OCR/table/caption text, screenshots, or raw artifacts. Recompute remains the
# primary numeric truth path: verified/canonical numeric facts may add committed
# numeric targets that the candidate must contain, failed recompute checks block
# Layer-1 numeric correctness, and unverified/low-confidence numeric facts never
# become confident values.
PHASE0_FACT_SHEET_SUMMARY_KIND = "quality_safety_phase0_fact_sheet_summary"
PHASE0_FACT_SHEET_STATUSES = frozenset({"not_supplied", "ok", "partial", "invalid"})
PHASE0_RECOMPUTE_VERIFIER_STATUSES = frozenset(
    {"not_run", "passed", "failed", "partial", "invalid"}
)
PHASE0_FACT_SHEET_WARNING_ORDER = (
    "fact_sheet_invalid",
    "fact_sheet_partial",
    "fact_sheet_unverified_numeric",
    "recompute_verifier_failed",
    "recompute_verifier_partial",
    "committed_numeric_missing",
    "committed_numeric_mismatch",
)

# --- Phase 0 eval runner + exit-check skeleton (Slice 165) -------------------
# A pure, in-memory runner that ties together the Phase 0 pieces built in Slices
# 160-164 (real golden-pair specs nn3+ensemble, the Layer-1 deterministic scorer,
# the deterministic-only overall_10 envelope kept separate from shippable, closed
# regression records, the optional caller-supplied fact-sheet summary, and the
# reference-anchored judge contract status). The runner scores caller-supplied
# synthetic candidate text only and returns a closed aggregate summary; it never
# discovers/reads files, jobs/, local_operator_baselines/, source/reference PDFs,
# generated guides, clean.md, OCR/table/caption text, screenshots, or raw
# artifacts, and it executes no provider/model/judge. The exit-check reports
# honestly whether Phase 0 can end; it cannot invent readiness, and the frozen
# production offline judge stays frozen by construction (judge_ready/repair_ready
# are always False with no override).
PHASE0_RUN_KIND = "phase0_eval_harness_run"
PHASE0_EXIT_CHECK_KIND = "phase0_exit_check"
PHASE0_EXIT_PHASE = "phase0_eval_harness_fact_sheet_skeleton"
PHASE0_EXIT_STATUSES = frozenset({"ready", "blocked", "not_ready"})
PHASE0_RUN_WARNING_ORDER = (
    "candidate_missing",
    "candidate_invalid",
    "fact_sheet_input_ignored",
    "reference_summary_input_ignored",
    "unexpected_candidate_lecture_ignored",
)
# Closed exit-check vocabularies. Blockers are honest reasons Phase 0 cannot end
# yet; satisfied tokens name Phase 0 components that verifiably exist in this
# module. Both are emitted as closed tokens only.
PHASE0_EXIT_BLOCKER_ORDER = (
    "phase0_required_run_missing",
    "phase0_run_not_all_shippable",
    "real_old_ensemble_run_not_recorded",
    "reference_judge_execution_not_run",
    "reference_judge_calibration_not_recorded",
    "fact_sheet_production_wiring_not_present",
    "regression_history_not_established",
)
PHASE0_EXIT_SATISFIED_ORDER = (
    "golden_pair_specs_present",
    "layer1_deterministic_scorer_present",
    "overall_10_separate_from_shippable",
    "regression_record_shape_present",
    "reference_judge_contract_present",
    "factsheet_recompute_integration_present",
    "production_offline_judge_frozen",
)
# Structural blockers that always hold in this slice: the real required local
# runs and the reference-judge calibration have not been recorded through safe
# closed summaries yet, and the fact-sheet path is not production-wired.
PHASE0_EXIT_STRUCTURAL_BLOCKERS = (
    "real_old_ensemble_run_not_recorded",
    "reference_judge_execution_not_run",
    "reference_judge_calibration_not_recorded",
    "fact_sheet_production_wiring_not_present",
    "regression_history_not_established",
)
PHASE0_EXIT_NEXT_STEPS = frozenset(
    {
        "phase0_address_non_shippable_run",
        "phase0_record_real_runs_and_judge_calibration",
    }
)

# --- Phase 0 local-operator run packet + closed result ingest (Slice 166) ---
# These pure functions are the *bridge* from the synthetic-only harness to real,
# local-only operator validation against private materials -- WITHOUT ever
# touching that material. The run packet is a closed instruction/contract object
# (no private paths, filenames, source/reference names, or shell commands). The
# ingest layer accepts only closed operator summaries (counts/statuses/booleans/
# bounded numerics) and rejects anything carrying raw candidate/source/reference/
# guide/OCR/table/caption text, prompts/responses, provider payloads, paths,
# filenames, hashes, byte counts, screenshots, base64/data URIs, secrets, or long
# evidence quotes. Nothing here reads a file, discovers anything, or calls a
# provider/model/judge, and the frozen production offline judge stays frozen by
# construction (judge_ready/repair_ready are always False and cannot be flipped
# true through this layer). This is NOT manual operator ``known_numbers``
# infrastructure: numeric correctness stays recompute-first via the golden specs.
PHASE0_OPERATOR_RUN_PACKET_KIND = "phase0_operator_run_packet"
PHASE0_OPERATOR_INGEST_KIND = "phase0_operator_closed_result_ingest"
PHASE0_OPERATOR_EXIT_CHECK_KIND = "phase0_operator_exit_check"
PHASE0_OPERATOR_LAYER2_EXECUTION_MODE = "operator_local_only_not_in_production"
PHASE0_OPERATOR_PERSISTENCE_POLICY = "closed_summary_only"
# The four local runs the operator must perform by hand against private material.
# Labels only -- no paths, no filenames, no commands.
PHASE0_OPERATOR_REQUIRED_LOCAL_RUNS = (
    "nn3_current_candidate",
    "ensemble_current_candidate",
    "ensemble_old_failure_candidate",
    "reference_judge_calibration_run",
)
# The closed summary kinds the operator must record (and that the ingest accepts).
# These reuse the real harness kinds (PHASE0_RUN_KIND / PHASE0_EXIT_CHECK_KIND /
# PHASE0_REGRESSION_RECORD_KIND) plus an operator-facing reference-judge summary
# token, so the packet and the ingest contract agree by construction.
PHASE0_OPERATOR_REFERENCE_JUDGE_SUMMARY_KIND = "phase0_reference_judge_summary"
PHASE0_OPERATOR_REQUIRED_CLOSED_OUTPUTS = (
    PHASE0_RUN_KIND,
    PHASE0_EXIT_CHECK_KIND,
    PHASE0_OPERATOR_REFERENCE_JUDGE_SUMMARY_KIND,
    PHASE0_REGRESSION_RECORD_KIND,
)
PHASE0_OPERATOR_RESULT_KINDS = frozenset(PHASE0_OPERATOR_REQUIRED_CLOSED_OUTPUTS)
# Output *types* the operator must never record into a closed summary. Advisory,
# human-facing list carried in the packet; the ingest enforces a superset of this
# via PHASE0_OPERATOR_FORBIDDEN_KEYS and the string scanner below.
PHASE0_OPERATOR_FORBIDDEN_OUTPUTS = (
    "source_text",
    "guide_text",
    "reference_text",
    "ocr_text",
    "table_text",
    "captions",
    "raw_prompt",
    "raw_response",
    "provider_payload",
    "filepath",
    "filename",
    "hash",
    "byte_count",
    "screenshot",
)
# Keys an ingested closed result may never carry (anywhere in the tree). This is
# the regression-record forbidden set plus the operator-specific raw/private keys.
PHASE0_OPERATOR_FORBIDDEN_KEYS = PHASE0_FORBIDDEN_RECORD_KEYS | frozenset(
    {
        "reference_text",
        "raw_prompt",
        "raw_response",
        "provider_payload",
        "filepath",
        "screenshot",
    }
)
PHASE0_OPERATOR_INGEST_STATUSES = frozenset({"ok", "invalid", "blocked"})
# Closed blocker tokens the ingest may emit. ``invalid`` blockers are structural
# (bad shape / unknown kind); ``blocked`` blockers name the kind of forbidden
# material detected (never the material itself).
PHASE0_OPERATOR_INGEST_BLOCKER_ORDER = (
    "result_not_mapping",
    "unknown_result_kind",
    "forbidden_key_present",
    "private_path_like_value",
    "data_uri_or_encoded_value",
    "secret_like_value",
    "private_material_like_value",
    "long_evidence_quote_value",
    "judge_ready_must_stay_false",
    "repair_ready_must_stay_false",
)
PHASE0_OPERATOR_INGEST_WARNING_ORDER = (
    "non_closed_value_dropped",
)
# Satisfied tokens the operator-results exit-check may emit (closed vocabulary).
PHASE0_OPERATOR_EXIT_SATISFIED_ORDER = (
    "operator_results_validated_closed",
    "operator_nn3_current_run_recorded",
    "operator_ensemble_current_run_recorded",
    "operator_ensemble_old_failure_run_recorded",
    "operator_reference_judge_execution_recorded",
    "operator_reference_judge_calibration_recorded",
    "operator_regression_history_recorded",
    "production_offline_judge_frozen",
)
# Bound for a "closed" numeric/string in an ingested summary. Strings longer than
# this (or carrying more words than the evidence-quote bound) are treated as
# possible evidence quotes and rejected.
PHASE0_OPERATOR_CLOSED_TOKEN_MAX_CHARS = 64
PHASE0_OPERATOR_EVIDENCE_QUOTE_MAX_WORDS = 12
_PHASE0_OPERATOR_PATH_RE = re.compile(r"(/home/|/mnt/|/tmp/|[A-Za-z]:\\|\\\\|https?://)")
_PHASE0_OPERATOR_SECRET_RE = re.compile(
    r"(authorization|bearer|api[_-]?key|secret|access[_-]?token)", re.IGNORECASE
)
_PHASE0_OPERATOR_DATA_URI_RE = re.compile(r"(data:|base64)", re.IGNORECASE)
_PHASE0_OPERATOR_CLOSED_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]*$")


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
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+")

# --- Slice 171: Phase 0 leak structural-signal classification ----------------
# The Phase 0 leak check previously counted every line containing "?" (minus a
# narrow set of mock headings) as "structural uncertainty". Solved-mock and
# practice-heavy guides legitimately carry many study questions, so that rule
# collapsed genuine leaked reasoning together with practice / self-test /
# worked-solution / source-reference / rhetorical scaffolding (a closed audit of
# the regenerated guides found only 1-2 of 32 structural hits were genuine). We
# now classify each question-like line into one closed category and keep the
# check blocking ONLY on genuine deliberation/uncertainty or an unclassifiable
# ("unknown") line, while reporting the clearly-legitimate scaffolding categories
# as non-blocking counts. The whole-text signature scan (``_LEAK_PATTERNS``) is
# unchanged and still blocks on its own. No raw line text, snippet, or path ever
# leaves this function -- only closed category names and counts.
LEAK_STRUCTURAL_CATEGORIES = (
    "genuine_deliberation_or_uncertainty",
    "mock_or_practice_question",
    "self_test_or_checklist_question",
    "exam_alert_or_instructional_question",
    "worked_solution_prompt_question",
    "source_citation_or_page_ref_pattern",
    "rhetorical_or_concept_heading_question",
    "other_false_positive",
    "unknown_needs_operator_review",
)
# Only these structural categories keep the leak check blocking. Everything else
# is legitimate study-guide scaffolding and is reported as a non-blocking count.
# ``unknown_needs_operator_review`` stays blocking on purpose: an ambiguous line
# we cannot confidently call legitimate must not be silently dropped, so we keep
# the safe (non-weakening) side and surface it for operator review.
LEAK_BLOCKING_STRUCTURAL_CATEGORIES = frozenset(
    {"genuine_deliberation_or_uncertainty", "unknown_needs_operator_review"}
)
LEAK_STRUCTURAL_WARNINGS = (
    "genuine_leaked_reasoning_present",
    "leak_structural_unknown_present",
)
# Strong, line-level deliberation/uncertainty phrasing beyond the whole-text
# signature words. A line carrying any of these (or an unresolved ``= ?`` form,
# or a signature word) is treated as a genuine leak and keeps blocking.
_LEAK_GENUINE_LINE_RE = re.compile(
    r"\b(?:not\s+sure|unsure|uncertain|ambiguous|unresolved|can(?:no|')t\s+tell|"
    r"hard\s+to\s+tell|or\s+maybe|maybe\s+it'?s|could\s+be\s+either|"
    r"which\s+(?:value|one|number)\s+is\s+(?:right|correct)|conflicting|"
    r"competing\s+values?|doesn'?t\s+match|don'?t\s+match)\b",
    re.IGNORECASE,
)
# Weak, ambiguous hints that are common in legitimate prose but might mask a
# leak. A question-like line carrying one of these, with no strong genuine
# signal and no recognized scaffold shape, is routed to operator review
# (blocking) rather than silently treated as a false positive.
_LEAK_SOFT_LINE_RE = re.compile(
    r"\b(?:maybe|perhaps|possibly|might\s+be|not\s+entirely|roughly|approximately)\b",
    re.IGNORECASE,
)
_SELF_TEST_RE = re.compile(
    r"\b(?:self[\s-]?test|self[\s-]?check|check\s+your\s+understanding|"
    r"test\s+yourself|quiz\s+yourself|checklist|"
    r"can\s+you\s+(?:explain|state|describe|derive|list|recall|name|identify))\b",
    re.IGNORECASE,
)
_EXAM_ALERT_RE = re.compile(
    r"(?:\bexam\s+(?:alert|tip|note|watch|hint)\b|\bkey\s+point\b|"
    r"\bcommon\s+(?:mistake|pitfall)\b|\bremember\s*:|\bnote\s*:|\btip\s*:|"
    r"\bimportant\s*:|\bwatch\s+out\b)",
    re.IGNORECASE,
)
_WORKED_PROMPT_RE = re.compile(
    r"(?:\bworked\s+(?:answer|solution|example)\b|\bstep\s+\d|\bsolution\s*:|"
    r"\bhint\s*:|\bapproach\s*:|\bstrategy\s*:)",
    re.IGNORECASE,
)
_SOURCE_REF_RE = re.compile(
    r"(?:\bsee\s+(?:page|slide|section|figure|fig\.?|chapter|lecture)\b|"
    r"\bpp?\.?\s*\d|\bpage\s+\d|\bslide\s+\d|\bsection\s+\d|\bfigure\s+\d|"
    r"\bfig\.?\s*\d|\bchapter\s+\d|\bref(?:erence)?\s*:|\bcf\.|\[\d+\])",
    re.IGNORECASE,
)


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


def build_phase0_fact_sheet_summary(fact_sheet: Any, golden_spec: Any) -> dict[str, Any]:
    """Summarize a caller-supplied Phase 0 fact sheet safely.

    Pure in-memory boundary: validates the golden-pair spec, normalizes the
    caller-supplied fact sheet, runs the recompute verifier, and returns only
    closed statuses/counts/warnings. It does not read files, discover artifacts,
    call providers/models, or echo fact labels, source refs, raw text,
    computation inputs, snippets, paths, filenames, hashes, byte counts, prompts,
    responses, or provider payloads.
    """
    spec = load_golden_pair_spec(golden_spec)
    return _phase0_fact_sheet_context(fact_sheet, spec)["summary"]


def score_phase0_layer1(
    candidate_text: Any,
    golden_spec: Any,
    *,
    fact_sheet: Any = None,
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
    blocking. When a caller supplies an in-memory fact sheet, the recompute
    verifier is used as an additional numeric truth signal: failed recomputes
    block numeric correctness, verified/canonical numeric facts must appear in
    the candidate text, and unverified numeric facts are counted/warned but never
    treated as confident values. ``shippable`` reflects only the deterministic
    Layer-1 blocking gates; advisory checks (mock-question count) never block on
    their own.

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

    fact_context = _phase0_fact_sheet_context(fact_sheet, spec)
    fact_summary = fact_context["summary"]
    for token in fact_summary.get("warnings", []):
        report_warnings.add(token)

    leaked = _check_leaked_reasoning(candidate_text, report_warnings)
    numeric = _phase0_apply_fact_sheet_numeric_context(
        _phase0_numeric_check(
            _check_numeric_correctness(candidate_text, spec, report_warnings)
        ),
        candidate_text=candidate_text,
        fact_context=fact_context,
        report_warnings=report_warnings,
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
            "fact_sheet_status": fact_summary["fact_sheet_status"],
            "recompute_verifier_status": fact_summary["recompute_verifier_status"],
            "verified_numeric_count": fact_summary["verified_numeric_count"],
            "failed_numeric_count": fact_summary["failed_numeric_count"],
            "unverified_numeric_count": fact_summary["unverified_numeric_count"],
            "canonical_numeric_count": fact_summary["canonical_numeric_count"],
            "mock_question_count": int(mock.get("count") or 0),
        },
        "fact_sheet_summary": fact_summary,
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


def _phase0_fact_sheet_context(fact_sheet: Any, spec: dict[str, Any]) -> dict[str, Any]:
    if fact_sheet is None:
        return {
            "summary": _phase0_fact_sheet_summary(
                fact_sheet_status="not_supplied",
                recompute_verifier_status="not_run",
                fact_sheet_numeric_count=0,
                verified_numeric_count=0,
                failed_numeric_count=0,
                unverified_numeric_count=0,
                canonical_numeric_count=0,
                committed_numeric_count=0,
                warnings=set(),
            ),
            "committed_numeric_targets": [],
            "failed_numeric_count": 0,
        }

    warnings: set[str] = set()
    try:
        verification = verify_quality_safety_fact_sheet(fact_sheet)
        verified_sheet = verification.get("fact_sheet") if isinstance(verification, dict) else None
        recompute_report = verification.get("report") if isinstance(verification, dict) else None
    except Exception:
        verified_sheet = normalize_quality_safety_fact_sheet(None)
        recompute_report = None
        warnings.add("fact_sheet_invalid")

    if not isinstance(verified_sheet, dict):
        verified_sheet = normalize_quality_safety_fact_sheet(None)
        warnings.add("fact_sheet_invalid")
    if not isinstance(recompute_report, dict):
        recompute_report = {}
        warnings.add("recompute_verifier_partial")

    fact_sheet_status = _phase0_fact_sheet_status(verified_sheet, warnings)
    recompute_status = _phase0_recompute_status(recompute_report, fact_sheet_status)

    facts = _phase0_numeric_facts(verified_sheet)
    recompute_checks = _phase0_recompute_checks_by_fact_id(recompute_report)
    committed_targets: list[dict[str, float | str]] = []
    verified_count = failed_count = unverified_count = canonical_count = 0

    for fact in facts:
        value = _finite_float(fact.get("value"))
        provenance = fact.get("provenance")
        status = fact.get("verification_status")
        if status == "failed":
            failed_count += 1
            continue
        if provenance == "canonical_fixture" and value is not None:
            canonical_count += 1
            target = _phase0_fact_target(fact, recompute_checks)
            if target is not None:
                committed_targets.append(target)
            continue
        if status == "verified" and value is not None:
            verified_count += 1
            target = _phase0_fact_target(fact, recompute_checks)
            if target is not None:
                committed_targets.append(target)
            continue
        unverified_count += 1

    report_summary = recompute_report.get("summary") if isinstance(recompute_report, dict) else {}
    recompute_failed = _non_negative_int(report_summary.get("failed_fact_count") if isinstance(report_summary, dict) else None)
    failed_count = max(failed_count, recompute_failed)
    if unverified_count and fact_sheet_status == "ok":
        fact_sheet_status = "partial"
    if fact_sheet_status == "invalid":
        warnings.add("fact_sheet_invalid")
    elif fact_sheet_status == "partial":
        warnings.add("fact_sheet_partial")
    if recompute_status == "failed":
        warnings.add("recompute_verifier_failed")
    elif recompute_status == "partial":
        warnings.add("recompute_verifier_partial")
    if unverified_count:
        warnings.add("fact_sheet_unverified_numeric")

    return {
        "summary": _phase0_fact_sheet_summary(
            fact_sheet_status=fact_sheet_status,
            recompute_verifier_status=recompute_status,
            fact_sheet_numeric_count=len(facts),
            verified_numeric_count=verified_count,
            failed_numeric_count=failed_count,
            unverified_numeric_count=unverified_count,
            canonical_numeric_count=canonical_count,
            committed_numeric_count=len(committed_targets),
            warnings=warnings,
        ),
        "committed_numeric_targets": committed_targets,
        "failed_numeric_count": failed_count,
    }


def _phase0_fact_sheet_summary(
    *,
    fact_sheet_status: str,
    recompute_verifier_status: str,
    fact_sheet_numeric_count: int,
    verified_numeric_count: int,
    failed_numeric_count: int,
    unverified_numeric_count: int,
    canonical_numeric_count: int,
    committed_numeric_count: int,
    warnings: set[str],
) -> dict[str, Any]:
    if fact_sheet_status not in PHASE0_FACT_SHEET_STATUSES:
        fact_sheet_status = "invalid"
    if recompute_verifier_status not in PHASE0_RECOMPUTE_VERIFIER_STATUSES:
        recompute_verifier_status = "invalid"
    return {
        "kind": PHASE0_FACT_SHEET_SUMMARY_KIND,
        "fact_sheet_status": fact_sheet_status,
        "recompute_verifier_status": recompute_verifier_status,
        "fact_sheet_numeric_count": max(0, int(fact_sheet_numeric_count)),
        "verified_numeric_count": max(0, int(verified_numeric_count)),
        "failed_numeric_count": max(0, int(failed_numeric_count)),
        "unverified_numeric_count": max(0, int(unverified_numeric_count)),
        "canonical_numeric_count": max(0, int(canonical_numeric_count)),
        "committed_numeric_count": max(0, int(committed_numeric_count)),
        "warnings": _ordered(warnings, PHASE0_FACT_SHEET_WARNING_ORDER),
    }


def _phase0_fact_sheet_status(verified_sheet: dict[str, Any], warnings: set[str]) -> str:
    sheet_status = verified_sheet.get("status")
    sheet_warnings = verified_sheet.get("warnings")
    if not isinstance(sheet_warnings, list):
        sheet_warnings = []
    if sheet_status == "skipped" or "malformed_fact_sheet_degraded" in sheet_warnings:
        return "invalid"
    if sheet_status == "partial":
        return "partial"
    if sheet_status == "warning" or warnings:
        return "partial"
    if sheet_status == "completed":
        return "ok"
    return "invalid"


def _phase0_recompute_status(recompute_report: dict[str, Any], fact_sheet_status: str) -> str:
    if fact_sheet_status == "invalid":
        return "invalid"
    status = recompute_report.get("status")
    warnings = recompute_report.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
    if "malformed_fact_sheet_degraded" in warnings:
        return "invalid"
    if status == "failed":
        return "failed"
    if status in {"partial", "warning"}:
        return "partial"
    if status in {"passed", "skipped"}:
        return "passed"
    return "invalid"


def _phase0_numeric_facts(verified_sheet: dict[str, Any]) -> list[dict[str, Any]]:
    concepts = verified_sheet.get("concepts")
    if not isinstance(concepts, list):
        return []
    facts: list[dict[str, Any]] = []
    for concept in concepts:
        raw_facts = concept.get("facts") if isinstance(concept, dict) else None
        if not isinstance(raw_facts, list):
            continue
        for fact in raw_facts:
            if isinstance(fact, dict) and fact.get("type") == "numeric":
                facts.append(fact)
    return facts


def _phase0_recompute_checks_by_fact_id(recompute_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = recompute_report.get("checks")
    if not isinstance(checks, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for check in checks:
        if isinstance(check, dict) and isinstance(check.get("fact_id"), str):
            out[check["fact_id"]] = check
    return out


def _phase0_fact_target(
    fact: dict[str, Any], recompute_checks: dict[str, dict[str, Any]]
) -> dict[str, float | str] | None:
    label = _safe_golden_label(fact.get("label"))
    value = _finite_float(fact.get("value"))
    if label is None or value is None:
        return None
    check = recompute_checks.get(str(fact.get("id")))
    tolerance = _finite_float(check.get("tolerance")) if isinstance(check, dict) else None
    if tolerance is None:
        computation = fact.get("computation")
        tolerance = _finite_float(computation.get("tolerance")) if isinstance(computation, dict) else None
    if tolerance is None:
        tolerance = 0.01
    return {"label": label, "value": float(value), "tol": max(0.0, float(tolerance))}


def _phase0_apply_fact_sheet_numeric_context(
    numeric: dict[str, Any],
    *,
    candidate_text: str,
    fact_context: dict[str, Any],
    report_warnings: set[str],
) -> dict[str, Any]:
    out = dict(numeric)
    summary = fact_context.get("summary") if isinstance(fact_context, dict) else {}
    if not isinstance(summary, dict) or summary.get("fact_sheet_status") == "not_supplied":
        return out

    failed_numeric = _non_negative_int(summary.get("failed_numeric_count"))
    committed_targets = fact_context.get("committed_numeric_targets")
    if not isinstance(committed_targets, list):
        committed_targets = []

    committed = _phase0_numeric_check(
        _check_numeric_correctness(
            candidate_text,
            {
                "ground_truth_numerics": committed_targets,
                "expected_topics": [],
                "min_mock_questions": 0,
            },
            report_warnings,
        )
    )
    committed_missing = _non_negative_int(committed.get("missing_count"))
    committed_mismatch = _non_negative_int(committed.get("mismatch_count"))
    if committed_missing:
        report_warnings.add("committed_numeric_missing")
    if committed_mismatch:
        report_warnings.add("committed_numeric_mismatch")

    out["expected_count"] = _non_negative_int(out.get("expected_count")) + _non_negative_int(
        committed.get("expected_count")
    )
    out["matched_count"] = _non_negative_int(out.get("matched_count")) + _non_negative_int(
        committed.get("matched_count")
    )
    out["missing_count"] = _non_negative_int(out.get("missing_count")) + committed_missing
    out["mismatch_count"] = (
        _non_negative_int(out.get("mismatch_count")) + committed_mismatch + failed_numeric
    )
    out["recompute_failed_count"] = failed_numeric
    out["unverified_numeric_count"] = _non_negative_int(summary.get("unverified_numeric_count"))
    out["verified_numeric_count"] = _non_negative_int(summary.get("verified_numeric_count"))
    out["canonical_numeric_count"] = _non_negative_int(summary.get("canonical_numeric_count"))
    failed = bool(out["missing_count"] or out["mismatch_count"])
    out["status"] = "failed" if failed else "passed"
    out["blocking"] = failed
    return out


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


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
    reference_judge_summary: Any = None,
) -> dict[str, Any]:
    """Build a closed, append-safe Phase 0 regression record.

    Summarizes one Layer-1 scoring run into a record that is safe to persist or
    commit: it holds only the lecture id, source quality, run/model labels, the
    deterministic ``overall_10`` and ``shippable``, blocking-check ids, per-check
    statuses, and bounded numerics. It never carries candidate/source/guide/OCR/
    table/caption text, snippets, paths, filenames, hashes, byte counts, or
    provider payloads. ``overall_10`` is Layer-1 deterministic-only
    (``layer2_judge_included=False`` unless an explicitly-supplied, fully
    calibrated Layer-2 summary is carried) and the frozen production offline judge
    stays frozen (``judge_ready``/``repair_ready`` always ``False``). When a previous
    ``overall_10`` is supplied the numeric delta is recorded, but the authoritative
    regression verdict is produced separately by :func:`compare_phase0_regression`.

    ``reference_judge_summary`` is an optional, already-sanitized closed Layer-2
    reference-anchored judge summary (produced by
    ``quality_safety_reference_judge.phase0_reference_judge_regression_summary``).
    It is defensively re-validated here: evidence quotes and any unknown/forbidden
    fields are dropped, statuses are closed, and ``layer2_judge_included`` is set
    ``True`` only when the result is fully calibrated and ``ok``. Crucially, a
    Layer-2 summary NEVER changes ``overall_10`` in this slice -- ``overall_10``
    stays Layer-1 deterministic-only.
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

    reference_summary = _safe_reference_judge_summary(reference_judge_summary)
    layer2_included = reference_summary["layer2_judge_included"]
    # Only a deliberately-supplied summary may override the Layer-1 path's status,
    # and only with a token the legacy field's closed vocabulary recognizes.
    if (
        isinstance(reference_judge_summary, dict)
        and reference_summary["status"] in REFERENCE_JUDGE_STATUSES
    ):
        reference_status = reference_summary["status"]

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
        "layer2_judge_included": layer2_included,
        "shippable": envelope["shippable"],
        "blocking_checks": envelope["blocking_checks"],
        "layer1_status": _safe_layer1_status(record.get("layer1_status")),
        "check_statuses": _phase0_check_statuses(record),
        "judge_ready": False,
        "repair_ready": False,
        "reference_anchored_judge_status": reference_status,
        "reference_anchored_judge": reference_summary,
        "fact_sheet_summary": _safe_phase0_fact_sheet_summary(record.get("fact_sheet_summary")),
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


def run_phase0_eval_harness(
    candidate_text_by_lecture_id: Any,
    golden_pair_specs: Any,
    *,
    fact_sheet_by_lecture_id: dict[str, Any] | None = None,
    reference_judge_summary_by_lecture_id: dict[str, Any] | None = None,
    run_id: Any = "synthetic",
    model_tier: Any = "premium",
) -> dict[str, Any]:
    """Run the Phase 0 eval harness over caller-supplied synthetic candidate text.

    Pure, deterministic, in-memory. ``golden_pair_specs`` must be exactly the two
    real golden-pair specs ``{nn3, ensemble}`` (validated by
    :func:`load_golden_pair_specs`, which raises ``GoldenPairSpecError`` on any
    other set, since the golden pair is authored and must be correct).
    ``candidate_text_by_lecture_id`` supplies the candidate guide text per lecture;
    a missing/non-string candidate degrades to an empty candidate (which fails the
    deterministic Layer-1 gates and is therefore non-shippable) and records a
    closed ``candidate_missing``/``candidate_invalid`` warning rather than crashing.

    Each lecture is scored with :func:`score_phase0_layer1` (optionally folding a
    caller-supplied in-memory fact sheet) and summarized into a closed
    :func:`build_phase0_regression_record`. ``overall_10`` is the Layer-1
    deterministic-only envelope and stays separate from ``shippable``. Layer-2 is
    not executed: ``layer2_judge_included`` is ``True`` only when an explicit,
    already-sanitized, fully-calibrated reference-judge summary is supplied for a
    lecture. The frozen production offline judge stays frozen by construction
    (``judge_ready``/``repair_ready`` always ``False``).

    Returns a closed aggregate summary holding counts, bounded numerics, closed
    statuses/warnings, and the per-lecture closed regression records only. It never
    reads any file, job artifact, source/reference document, ``clean.md``,
    OCR/table/caption text, screenshot, or provider payload, and it never echoes
    raw candidate text, snippets, paths, filenames, hashes, or byte counts. It is
    not a manual operator ``known_numbers`` runtime; the closed golden expectations
    drive it.
    """
    specs = load_golden_pair_specs(golden_pair_specs)

    candidates = candidate_text_by_lecture_id if isinstance(candidate_text_by_lecture_id, dict) else {}
    fact_sheets = fact_sheet_by_lecture_id if isinstance(fact_sheet_by_lecture_id, dict) else {}
    reference_summaries = (
        reference_judge_summary_by_lecture_id
        if isinstance(reference_judge_summary_by_lecture_id, dict)
        else {}
    )

    warnings: set[str] = set()
    if set(candidates) - set(REQUIRED_GOLDEN_PAIR_IDS):
        warnings.add("unexpected_candidate_lecture_ignored")

    records: list[dict[str, Any]] = []
    scores: list[float] = []
    shippable_count = 0
    layer2_included = False

    for lecture_id in REQUIRED_GOLDEN_PAIR_IDS:
        spec = specs[lecture_id]
        candidate = candidates.get(lecture_id)
        if candidate is None:
            warnings.add("candidate_missing")
            candidate = ""
        elif not isinstance(candidate, str):
            warnings.add("candidate_invalid")
            candidate = ""

        fact_sheet = fact_sheets.get(lecture_id)
        reference_summary = reference_summaries.get(lecture_id)
        if reference_summary is not None and not isinstance(reference_summary, dict):
            warnings.add("reference_summary_input_ignored")
            reference_summary = None

        layer1 = score_phase0_layer1(candidate, spec, fact_sheet=fact_sheet)
        record = build_phase0_regression_record(
            layer1,
            run_id=run_id,
            model_tier=model_tier,
            candidate_id=lecture_id,
            reference_judge_summary=reference_summary,
        )
        records.append(record)

        score = _safe_score(record.get("overall_10"))
        if score is not None:
            scores.append(score)
        if record.get("shippable"):
            shippable_count += 1
        if record.get("layer2_judge_included"):
            layer2_included = True

    lecture_count = len(records)
    non_shippable_count = lecture_count - shippable_count
    min_overall_10 = round(min(scores), 4) if scores else None
    average_overall_10 = round(sum(scores) / len(scores), 4) if scores else None

    return {
        "version": VERSION,
        "kind": PHASE0_RUN_KIND,
        "run_id": _safe_meta(run_id, "synthetic"),
        "model_tier": _safe_model_tier(model_tier),
        "golden_pair_ids": list(REQUIRED_GOLDEN_PAIR_IDS),
        "lecture_count": lecture_count,
        "shippable_count": shippable_count,
        "non_shippable_count": non_shippable_count,
        "min_overall_10": min_overall_10,
        "average_overall_10": average_overall_10,
        "all_shippable": lecture_count > 0 and shippable_count == lecture_count,
        "overall_score_kind": PHASE0_OVERALL_SCORE_KIND,
        "layer2_judge_included": layer2_included,
        "production_offline_judge_frozen": True,
        "judge_ready": False,
        "repair_ready": False,
        "records": records,
        "warnings": _ordered(warnings, PHASE0_RUN_WARNING_ORDER),
    }


def build_phase0_exit_check(run_record: Any) -> dict[str, Any]:
    """Evaluate whether Phase 0 can end, honestly, from a closed run record.

    Takes a record produced by :func:`run_phase0_eval_harness` and returns a
    closed exit-check record holding closed blocker/satisfied tokens only. It must
    not invent readiness: the structural blockers (no real old Ensemble run
    recorded, reference-judge execution/calibration not run, fact-sheet path not
    production-wired, regression history not established) always hold in this
    slice, so ``phase0_exit_status`` is never ``ready`` here. A non-shippable run,
    or a missing/invalid run record, is surfaced as an additional blocker. The
    frozen production offline judge stays frozen (``judge_ready``/``repair_ready``
    always ``False``). Reads no file and echoes no private material.
    """
    run = (
        run_record
        if isinstance(run_record, dict) and run_record.get("kind") == PHASE0_RUN_KIND
        else None
    )

    blockers: set[str] = set(PHASE0_EXIT_STRUCTURAL_BLOCKERS)
    satisfied: set[str] = {
        "layer1_deterministic_scorer_present",
        "overall_10_separate_from_shippable",
        "reference_judge_contract_present",
        "factsheet_recompute_integration_present",
        "production_offline_judge_frozen",
    }

    if run is None:
        blockers.add("phase0_required_run_missing")
    else:
        satisfied.add("golden_pair_specs_present")
        satisfied.add("regression_record_shape_present")
        if not run.get("all_shippable"):
            blockers.add("phase0_run_not_all_shippable")

    if "phase0_run_not_all_shippable" in blockers:
        status = "blocked"
        next_step = "phase0_address_non_shippable_run"
    elif blockers:
        status = "not_ready"
        next_step = "phase0_record_real_runs_and_judge_calibration"
    else:  # pragma: no cover - unreachable while structural blockers hold
        status = "ready"
        next_step = "phase0_record_real_runs_and_judge_calibration"

    return {
        "version": VERSION,
        "kind": PHASE0_EXIT_CHECK_KIND,
        "phase": PHASE0_EXIT_PHASE,
        "phase0_exit_status": status,
        "golden_pair_ids": list(REQUIRED_GOLDEN_PAIR_IDS),
        "blockers": _ordered(blockers, PHASE0_EXIT_BLOCKER_ORDER),
        "satisfied": _ordered(satisfied, PHASE0_EXIT_SATISFIED_ORDER),
        "production_offline_judge_frozen": True,
        "judge_ready": False,
        "repair_ready": False,
        "next_step": next_step,
    }


def build_phase0_operator_run_packet() -> dict[str, Any]:
    """Return the closed Phase 0 local-operator run packet (pure, no I/O).

    The packet tells a human operator *what* local runs to perform against their
    own private materials, and *what* closed summaries to record back -- without
    ever naming a private path, filename, source/reference document, or shell
    command. It is a contract object only: it executes nothing, reads nothing, and
    discovers nothing. The frozen production offline judge stays frozen
    (``judge_ready``/``repair_ready`` always ``False``), Layer-2 stays an
    operator-local dev-time activity (never production), and persistence is
    closed-summary-only. Numeric correctness remains recompute-first via the
    golden specs -- this is NOT a manual ``known_numbers`` packet.
    """
    return {
        "version": VERSION,
        "kind": PHASE0_OPERATOR_RUN_PACKET_KIND,
        "phase": PHASE0_EXIT_PHASE,
        "golden_pair_ids": list(REQUIRED_GOLDEN_PAIR_IDS),
        "required_local_runs": list(PHASE0_OPERATOR_REQUIRED_LOCAL_RUNS),
        "required_closed_outputs": list(PHASE0_OPERATOR_REQUIRED_CLOSED_OUTPUTS),
        "forbidden_outputs": list(PHASE0_OPERATOR_FORBIDDEN_OUTPUTS),
        "layer2_execution_mode": PHASE0_OPERATOR_LAYER2_EXECUTION_MODE,
        "persistence_policy": PHASE0_OPERATOR_PERSISTENCE_POLICY,
        "numeric_strategy": "recompute_first_not_manual_known_numbers",
        "production_offline_judge_frozen": True,
        "judge_ready": False,
        "repair_ready": False,
    }


# Backwards/forwards-friendly alias for callers preferring a ``get_`` accessor.
def get_phase0_operator_run_packet() -> dict[str, Any]:
    """Alias of :func:`build_phase0_operator_run_packet` (returns a fresh dict)."""
    return build_phase0_operator_run_packet()


def ingest_phase0_operator_closed_result(result: Any) -> dict[str, Any]:
    """Validate and sanitize one closed operator result summary (pure, no I/O).

    Accepts only closed summaries of a recognized kind
    (:data:`PHASE0_OPERATOR_RESULT_KINDS`). Returns a closed ingest record with
    ``ingest_status`` in ``{ok, invalid, blocked}``:

    * ``invalid`` -- structurally wrong (not a mapping, or unknown/missing kind).
    * ``blocked`` -- recognized kind but carrying forbidden material: a forbidden
      key anywhere in the tree, a value that looks like a private path, a
      base64/data URI, a secret, other private material, a long evidence quote, or
      an attempt to set ``judge_ready``/``repair_ready`` true.
    * ``ok`` -- clean; a sanitized closed projection is returned.

    The function never reads a file, never calls a provider/model/judge, never
    echoes the offending material (only closed tokens naming *what kind* of
    violation occurred), and never sets ``judge_ready``/``repair_ready`` true.
    """
    blockers: set[str] = set()
    warnings: set[str] = set()

    if not isinstance(result, dict):
        return _operator_ingest_record("invalid", None, {"result_not_mapping"}, set())

    kind = result.get("kind")
    if not isinstance(kind, str) or kind not in PHASE0_OPERATOR_RESULT_KINDS:
        return _operator_ingest_record("invalid", None, {"unknown_result_kind"}, set())

    if _collect_operator_forbidden_keys(result):
        blockers.add("forbidden_key_present")
    _operator_scan_value(result, blockers)
    if result.get("judge_ready") is True:
        blockers.add("judge_ready_must_stay_false")
    if result.get("repair_ready") is True:
        blockers.add("repair_ready_must_stay_false")

    if blockers:
        return _operator_ingest_record("blocked", None, blockers, set())

    sanitized = _operator_sanitize_closed_result(result, kind, warnings)
    return _operator_ingest_record("ok", sanitized, set(), warnings)


def build_phase0_exit_check_from_operator_results(results: Any) -> dict[str, Any]:
    """Honest Phase 0 exit-check derived from validated closed operator results.

    Ingests each supplied result with :func:`ingest_phase0_operator_closed_result`
    and uses only the ones that validate ``ok``. It can never invent readiness:
    the fact-sheet production-wiring blocker is structural and cannot be cleared by
    a closed summary, so ``phase0_exit_status`` is never ``ready`` here. Missing
    required closed summaries surface honest closed blockers (no real old Ensemble
    run, no reference-judge execution/calibration, no regression history). The
    frozen production offline judge stays frozen. Reads no file; echoes no private
    material.
    """
    items = results if isinstance(results, list) else []

    run_labels: set[str] = set()
    have_reference_summary = False
    reference_calibrated = False
    have_regression = False
    any_run_not_all_shippable = False
    validated_count = 0

    for raw in items:
        ingest = ingest_phase0_operator_closed_result(raw)
        if ingest.get("ingest_status") != "ok":
            continue
        validated_count += 1
        kind = ingest.get("accepted_kind")
        summary = ingest.get("sanitized_result") or {}
        if kind == PHASE0_RUN_KIND:
            label = summary.get("run_label")
            if isinstance(label, str) and label in PHASE0_OPERATOR_REQUIRED_LOCAL_RUNS:
                run_labels.add(label)
            # The old-Ensemble-failure run is *expected* to be non-shippable (that
            # is what makes it a useful recorded failure), so only a current
            # candidate run reporting non-shippable is a genuine block.
            if (
                label in ("nn3_current_candidate", "ensemble_current_candidate")
                and summary.get("all_shippable") is False
            ):
                any_run_not_all_shippable = True
        elif kind == PHASE0_OPERATOR_REFERENCE_JUDGE_SUMMARY_KIND:
            have_reference_summary = True
            if summary.get("calibrated") is True or summary.get("reference_judge_status") == "ok":
                reference_calibrated = True
        elif kind == PHASE0_REGRESSION_RECORD_KIND:
            have_regression = True

    blockers: set[str] = set()
    satisfied: set[str] = {"production_offline_judge_frozen"}
    if validated_count:
        satisfied.add("operator_results_validated_closed")

    if "nn3_current_candidate" in run_labels:
        satisfied.add("operator_nn3_current_run_recorded")
    if "ensemble_current_candidate" in run_labels:
        satisfied.add("operator_ensemble_current_run_recorded")
    if "ensemble_old_failure_candidate" in run_labels:
        satisfied.add("operator_ensemble_old_failure_run_recorded")
    else:
        blockers.add("real_old_ensemble_run_not_recorded")

    if have_reference_summary:
        satisfied.add("operator_reference_judge_execution_recorded")
    else:
        blockers.add("reference_judge_execution_not_run")

    if reference_calibrated and "reference_judge_calibration_run" in run_labels:
        satisfied.add("operator_reference_judge_calibration_recorded")
    else:
        blockers.add("reference_judge_calibration_not_recorded")

    if have_regression:
        satisfied.add("operator_regression_history_recorded")
    else:
        blockers.add("regression_history_not_established")

    # The fact-sheet production-wiring blocker is structural: no closed operator
    # summary can establish production wiring, so it always holds in Phase 0 and
    # readiness can never be faked from operator results alone.
    blockers.add("fact_sheet_production_wiring_not_present")

    if any_run_not_all_shippable:
        blockers.add("phase0_run_not_all_shippable")
        status = "blocked"
        next_step = "phase0_address_non_shippable_run"
    elif blockers:
        status = "not_ready"
        next_step = "phase0_record_real_runs_and_judge_calibration"
    else:  # pragma: no cover - unreachable while the structural blocker holds
        status = "ready"
        next_step = "phase0_record_real_runs_and_judge_calibration"

    return {
        "version": VERSION,
        "kind": PHASE0_OPERATOR_EXIT_CHECK_KIND,
        "phase": PHASE0_EXIT_PHASE,
        "phase0_exit_status": status,
        "golden_pair_ids": list(REQUIRED_GOLDEN_PAIR_IDS),
        "validated_result_count": validated_count,
        "blockers": _ordered(blockers, PHASE0_EXIT_BLOCKER_ORDER),
        "satisfied": _ordered(satisfied, PHASE0_OPERATOR_EXIT_SATISFIED_ORDER),
        "production_offline_judge_frozen": True,
        "judge_ready": False,
        "repair_ready": False,
        "next_step": next_step,
    }


def _operator_ingest_record(
    status: str,
    sanitized: dict[str, Any] | None,
    blockers: set[str],
    warnings: set[str],
) -> dict[str, Any]:
    return {
        "version": VERSION,
        "kind": PHASE0_OPERATOR_INGEST_KIND,
        "ingest_status": status,
        "accepted_kind": (sanitized.get("kind") if isinstance(sanitized, dict) else None),
        "golden_pair_ids": list(REQUIRED_GOLDEN_PAIR_IDS),
        "blockers": _ordered(blockers, PHASE0_OPERATOR_INGEST_BLOCKER_ORDER),
        "warnings": _ordered(warnings, PHASE0_OPERATOR_INGEST_WARNING_ORDER),
        "sanitized_result": sanitized,
        "production_offline_judge_frozen": True,
        "judge_ready": False,
        "repair_ready": False,
    }


def _collect_operator_forbidden_keys(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and key.lower() in PHASE0_OPERATOR_FORBIDDEN_KEYS:
                found.add(key.lower())
            found |= _collect_operator_forbidden_keys(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            found |= _collect_operator_forbidden_keys(item)
    return found


def _operator_scan_value(node: Any, blockers: set[str]) -> None:
    if isinstance(node, str):
        if _PHASE0_OPERATOR_PATH_RE.search(node):
            blockers.add("private_path_like_value")
        if _PHASE0_OPERATOR_DATA_URI_RE.search(node):
            blockers.add("data_uri_or_encoded_value")
        if _PHASE0_OPERATOR_SECRET_RE.search(node):
            blockers.add("secret_like_value")
        if _SECRETISH_RE.search(node):
            blockers.add("private_material_like_value")
        if _operator_looks_like_evidence_quote(node):
            blockers.add("long_evidence_quote_value")
    elif isinstance(node, dict):
        for value in node.values():
            _operator_scan_value(value, blockers)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _operator_scan_value(item, blockers)


def _operator_looks_like_evidence_quote(value: str) -> bool:
    if len(value) > PHASE0_OPERATOR_CLOSED_TOKEN_MAX_CHARS:
        return True
    return len(value.split()) > PHASE0_OPERATOR_EVIDENCE_QUOTE_MAX_WORDS


def _operator_is_closed_token(value: str) -> bool:
    if not value or len(value) > PHASE0_OPERATOR_CLOSED_TOKEN_MAX_CHARS:
        return False
    if not _PHASE0_OPERATOR_CLOSED_TOKEN_RE.match(value):
        return False
    if _SECRETISH_RE.search(value) or _PHASE0_OPERATOR_PATH_RE.search(value):
        return False
    return not _operator_looks_like_evidence_quote(value)


def _operator_sanitize_node(node: Any, warnings: set[str]) -> Any:
    if isinstance(node, bool):
        return node
    if isinstance(node, int):
        if abs(node) <= 1_000_000_000:
            return node
        warnings.add("non_closed_value_dropped")
        return None
    if isinstance(node, float):
        if math.isfinite(node) and abs(node) <= 1_000_000_000.0:
            return round(node, 6)
        warnings.add("non_closed_value_dropped")
        return None
    if node is None:
        return None
    if isinstance(node, str):
        if _operator_is_closed_token(node):
            return node
        warnings.add("non_closed_value_dropped")
        return None
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            if not isinstance(key, str) or key.lower() in PHASE0_OPERATOR_FORBIDDEN_KEYS:
                warnings.add("non_closed_value_dropped")
                continue
            out[key] = _operator_sanitize_node(value, warnings)
        return out
    if isinstance(node, (list, tuple)):
        return [_operator_sanitize_node(item, warnings) for item in node]
    warnings.add("non_closed_value_dropped")
    return None


def _operator_sanitize_closed_result(
    result: dict[str, Any], kind: str, warnings: set[str]
) -> dict[str, Any]:
    sanitized = _operator_sanitize_node(result, warnings)
    if not isinstance(sanitized, dict):
        sanitized = {}
    sanitized["kind"] = kind
    sanitized["judge_ready"] = False
    sanitized["repair_ready"] = False
    sanitized["production_offline_judge_frozen"] = True
    return sanitized


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


def _safe_reference_judge_summary(value: Any) -> dict[str, Any]:
    """Return a closed, persist-safe Layer-2 reference-judge summary.

    Defensive re-validation of a sanitized summary supplied by a caller (produced
    by ``quality_safety_reference_judge.phase0_reference_judge_regression_summary``).
    Returns a closed dict holding only closed statuses and bounded integer axis
    scores -- never evidence quotes, raw model output, prompts, paths, filenames,
    hashes, byte counts, or any other forbidden material. ``judge_ready`` and
    ``repair_ready`` are always ``False``; ``layer2_judge_included`` is ``True``
    only when the result is fully calibrated and ``ok``. A missing/invalid summary
    degrades to a closed ``not_run`` summary.
    """
    if not isinstance(value, dict):
        status, calibration = "not_run", "not_run"
    else:
        status = value.get("status")
        if status not in PHASE0_REFERENCE_JUDGE_RESULT_STATUSES:
            status = "invalid_output"
        calibration = value.get("calibration_status")
        if calibration not in PHASE0_REFERENCE_JUDGE_CALIBRATION_STATUSES:
            calibration = "not_run"
    included = status == "ok" and calibration == "ok"
    summary: dict[str, Any] = {
        "kind": PHASE0_REFERENCE_JUDGE_SUMMARY_KIND,
        "status": status,
        "calibration_status": calibration,
        "layer2_judge_included": included,
        "axis_count": 0,
        "judge_ready": False,
        "repair_ready": False,
    }
    raw = value if isinstance(value, dict) else {}
    candidate_scores = _safe_reference_axis_scores(raw.get("candidate_axis_scores"))
    reference_scores = _safe_reference_axis_scores(raw.get("reference_axis_scores"))
    # Candidate scores are only meaningful (and only retained) when calibrated/ok.
    if included and candidate_scores:
        summary["candidate_axis_scores"] = candidate_scores
        summary["axis_count"] = len(candidate_scores)
    if reference_scores:
        summary["reference_axis_scores"] = reference_scores
    return summary


def _safe_reference_axis_scores(value: Any) -> dict[str, int]:
    """Keep only closed axis keys mapped to bounded integer scores (0..5)."""
    if not isinstance(value, dict):
        return {}
    out: dict[str, int] = {}
    for axis in PHASE0_REFERENCE_JUDGE_AXES:
        score = value.get(axis)
        if (
            isinstance(score, int)
            and not isinstance(score, bool)
            and PHASE0_REFERENCE_AXIS_SCORE_MIN <= score <= PHASE0_REFERENCE_AXIS_SCORE_MAX
        ):
            out[axis] = score
    return out


def _safe_phase0_fact_sheet_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return _phase0_fact_sheet_summary(
            fact_sheet_status="not_supplied",
            recompute_verifier_status="not_run",
            fact_sheet_numeric_count=0,
            verified_numeric_count=0,
            failed_numeric_count=0,
            unverified_numeric_count=0,
            canonical_numeric_count=0,
            committed_numeric_count=0,
            warnings=set(),
        )
    fact_sheet_status = value.get("fact_sheet_status")
    if fact_sheet_status not in PHASE0_FACT_SHEET_STATUSES:
        fact_sheet_status = "invalid"
    recompute_status = value.get("recompute_verifier_status")
    if recompute_status not in PHASE0_RECOMPUTE_VERIFIER_STATUSES:
        recompute_status = "invalid"
    warnings = set(value.get("warnings")) if isinstance(value.get("warnings"), list) else set()
    return _phase0_fact_sheet_summary(
        fact_sheet_status=str(fact_sheet_status),
        recompute_verifier_status=str(recompute_status),
        fact_sheet_numeric_count=_non_negative_int(value.get("fact_sheet_numeric_count")),
        verified_numeric_count=_non_negative_int(value.get("verified_numeric_count")),
        failed_numeric_count=_non_negative_int(value.get("failed_numeric_count")),
        unverified_numeric_count=_non_negative_int(value.get("unverified_numeric_count")),
        canonical_numeric_count=_non_negative_int(value.get("canonical_numeric_count")),
        committed_numeric_count=_non_negative_int(value.get("committed_numeric_count")),
        warnings={token for token in warnings if token in PHASE0_FACT_SHEET_WARNING_ORDER},
    )


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
        target: dict[str, float | str | list[str]] = {
            "label": label,
            "value": float(expected),
            "tol": float(tol),
        }
        aliases = _coerce_numeric_aliases(item.get("aliases"), strict=True)
        if aliases:
            target["aliases"] = aliases
        numerics.append(target)
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


def _coerce_numeric_aliases(value: Any, *, strict: bool) -> list[str]:
    """Return the closed, public-safe label aliases / concept anchors for a target.

    Aliases are optional. Each is validated exactly like an authored label
    (``_safe_golden_label``): closed, <=100 chars, no secret/path/URL/raw-material
    content, at least one alphanumeric. They are deduped by normalized form,
    capped at ``MAX_NUMERIC_ALIASES``, and must never carry private guide/source
    text -- only the generic concept/symbol/formula phrasing the guide names. The
    strict loader raises on a malformed aliases container or entry; the lenient
    loader silently drops bad entries so a hostile fixture cannot smuggle material.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        if strict:
            raise GoldenPairSpecError(f"aliases must be a list: {value!r}")
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        alias = _safe_golden_label(item)
        if alias is None:
            if strict:
                raise GoldenPairSpecError(f"invalid numeric alias: {item!r}")
            continue
        key = _normalize(alias)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(alias)
        if len(out) >= MAX_NUMERIC_ALIASES:
            break
    return out


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
        target: dict[str, float | str | list[str]] = {
            "label": label,
            "value": float(expected),
            "tol": float(tol),
        }
        aliases = _coerce_numeric_aliases(item.get("aliases"), strict=False)
        if aliases:
            target["aliases"] = aliases
        targets.append(target)
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


def _classify_leak_structural_line(line: str) -> str:
    """Classify one question-like line into a closed leak structural category.

    Priority order matters: genuine deliberation/uncertainty is detected first so
    a study-question line that *also* carries a leak signature (e.g. "unclear")
    still blocks. The remaining checks recognise legitimate study-guide
    scaffolding shapes; anything with only a weak/ambiguous hint falls to operator
    review, and a plain question with no uncertainty signal is a false positive.
    """
    if _STRUCTURAL_UNCERTAINTY_RE.search(line):
        return "genuine_deliberation_or_uncertainty"
    if _LEAK_GENUINE_LINE_RE.search(line) or any(p.search(line) for p in _LEAK_PATTERNS):
        return "genuine_deliberation_or_uncertainty"
    if _is_mock_question_count_line(line):
        return "mock_or_practice_question"
    if _SELF_TEST_RE.search(line):
        return "self_test_or_checklist_question"
    if _EXAM_ALERT_RE.search(line):
        return "exam_alert_or_instructional_question"
    if _WORKED_PROMPT_RE.search(line):
        return "worked_solution_prompt_question"
    if _SOURCE_REF_RE.search(line):
        return "source_citation_or_page_ref_pattern"
    if _HEADING_RE.match(line):
        return "rhetorical_or_concept_heading_question"
    if _LEAK_SOFT_LINE_RE.search(line):
        return "unknown_needs_operator_review"
    return "other_false_positive"


def _check_leaked_reasoning(candidate: str, warnings: set[str]) -> dict[str, Any]:
    signature_count = 0
    for pattern in _LEAK_PATTERNS:
        signature_count += len(pattern.findall(candidate))

    categories = {name: 0 for name in LEAK_STRUCTURAL_CATEGORIES}
    question_like_count = 0
    for line in candidate.splitlines():
        if not (_STRUCTURAL_UNCERTAINTY_RE.search(line) or "?" in line):
            continue
        question_like_count += 1
        categories[_classify_leak_structural_line(line)] += 1

    genuine_count = categories["genuine_deliberation_or_uncertainty"]
    unknown_count = categories["unknown_needs_operator_review"]
    # Only genuine deliberation/uncertainty and unclassifiable lines keep the
    # check blocking; legitimate study scaffolding is reported but does not block.
    blocking_structural = sum(
        categories[name] for name in LEAK_BLOCKING_STRUCTURAL_CATEGORIES
    )
    non_leak_scaffold = question_like_count - blocking_structural
    signal_count = signature_count + blocking_structural
    status = "failed" if signal_count else "passed"

    check_warnings: list[str] = []
    if signal_count:
        warnings.add("leaked_reasoning_signal")
    if genuine_count:
        check_warnings.append("genuine_leaked_reasoning_present")
    if unknown_count:
        check_warnings.append("leak_structural_unknown_present")
        warnings.add("leak_structural_unknown_present")

    return {
        "id": "leaked_reasoning",
        "status": status,
        "blocking": status == "failed",
        "signature_count": signature_count,
        # Backward-compatible field: now the *blocking* structural count (genuine
        # deliberation + unknown-needs-review). Legitimate study scaffolding no
        # longer inflates it. Total question-like hits are exposed separately via
        # ``structural_question_like_count`` and ``structural_signal_categories``.
        "structural_uncertainty_count": blocking_structural,
        "genuine_structural_uncertainty_count": genuine_count,
        "non_leak_question_scaffold_count": non_leak_scaffold,
        "structural_question_like_count": question_like_count,
        "structural_signal_categories": categories,
        "signal_count": signal_count,
        "warnings": check_warnings,
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
        anchor_norms = [norm for _, norm, _ in _numeric_anchor_terms(item)]
        scan = _label_value_scan_multi(normalized_lines, anchor_norms)
        # Same-line evidence wins. Only when the label's own line carries no number
        # at all do we accept a value recovered from the next non-empty line (a
        # common PDF-extraction line break). Contradiction is judged on the
        # literally written numbers; the within-tolerance test additionally accepts
        # format-equivalent readings (e.g. a percent written as 97% matching a
        # golden 0.97) -- equivalence implied by the fixture's own tolerance, never
        # a widened tolerance and never a manufactured value.
        if scan["same_match"]:
            literal_values = _dedupe_floats(scan["same_literal"])
            match_values = _dedupe_floats(scan["same_match"])
        else:
            literal_values = _dedupe_floats(scan["prox_literal"])
            match_values = _dedupe_floats(scan["prox_match"])
        # A worked line states its working steps before the FINAL committed answer
        # (e.g. ``= (1/2)ln(7) ≈ 0.97``). The committed answer after the last result
        # separator is credited when it is internally consistent and within the
        # EXISTING tolerance, so a correct final answer is not falsely failed as a
        # contradiction by its own derivation. Two different committed answers still
        # contradict, and a wrong committed answer is never credited. Same-line
        # committed evidence wins over a proximity (next-line) committed value, so a
        # weak cross-line guess never poisons a strong same-line answer.
        if scan["same_committed"]:
            committed = _dedupe_floats(scan["same_committed"])
        else:
            committed = _dedupe_floats(scan["prox_committed"])
        committed_clean = (
            bool(committed)
            and not _has_numeric_contradiction(committed, tol)
            and any(abs(value - expected) <= tol for value in committed)
        )
        if not match_values:
            missing_count += 1
            status = "unknown"
            warnings.add("numeric_target_missing")
        elif committed_clean:
            pass_count += 1
            status = "passed"
        elif _has_numeric_contradiction(literal_values, tol):
            fail_count += 1
            status = "failed"
            warnings.add("numeric_contradiction_signal")
        elif any(abs(value - expected) <= tol for value in match_values):
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
                "found_values": match_values,
                "distinct_value_count": len(match_values),
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
    count = sum(1 for line in candidate.splitlines() if _is_mock_question_count_line(line))
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


# --- Slice 169: shared label-anchored value scan + closed numeric diagnostic ---
# Phase 0 measurement trust: the real current-pair run reported numeric 0/n, but the
# generated guides do contain numeric worked examples, so a blind 0 is not proof the
# values are absent. These helpers (1) make the matcher recognize format/proximity
# equivalents that are already implied by the fixture tolerance, and (2) classify
# every target so a 0/n score can be proven a real product gap vs. a matcher
# artifact BEFORE any regeneration. They never edit expected values, widen a
# tolerance, or turn a wrong value into a match.
NUMERIC_CLASS_MATCHED = "found_and_matched"
NUMERIC_CLASS_FORMAT_MISSED = "found_but_format_or_context_missed"
NUMERIC_CLASS_WRONG_VALUE = "found_but_wrong_value"
NUMERIC_CLASS_MISSING = "genuinely_missing"

# Slice 170: closed, enum-only attribution metadata. ``alias_matched`` carries the
# fixture-authored anchor that produced the winning match (or the sentinels below);
# ``proximity_mode`` records how close the value sat to that anchor. None of these
# echo guide/source text -- the alias strings are public-safe fixture metadata.
NUMERIC_ALIAS_PRIMARY = "primary_label"
NUMERIC_ALIAS_NONE = "none"
PROXIMITY_SAME_LINE = "same_line"
PROXIMITY_NEXT_LINE = "next_line"
PROXIMITY_NONE = "none"

_PERCENT_RE = re.compile(r"(?<![A-Za-z0-9_])(-?(?:\d+(?:\.\d*)?|\.\d+))\s*%")


def _numeric_anchor_terms(item: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Ordered anchor terms for a numeric target: the authored label first, then
    each safe alias / concept anchor.

    Returns ``(text, normalized, kind)`` triples where ``kind`` is ``"label"`` or
    ``"alias"``, deduped by normalized form so the same phrase is never scanned
    twice and so an alias that merely repeats the label adds no weight. The label
    is yielded first so label-anchored evidence is preferred on ties when the
    matcher picks a winner. The label may itself be empty/unusable, in which case
    only aliases anchor -- a value is still never matched without *some* approved
    anchor present on a line.
    """
    terms: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    label_norm = _normalize(str(item.get("label", "")))
    if label_norm:
        terms.append((str(item.get("label", "")), label_norm, "label"))
        seen.add(label_norm)
    aliases = item.get("aliases")
    if isinstance(aliases, list):
        for alias in aliases:
            if not isinstance(alias, str):
                continue
            alias_norm = _normalize(alias)
            if not alias_norm or alias_norm in seen:
                continue
            seen.add(alias_norm)
            terms.append((alias, alias_norm, "alias"))
    return terms


def _label_value_scan_multi(
    normalized_lines: list[tuple[str, str]], anchor_norms: list[str]
) -> dict[str, list[float]]:
    """Merge per-anchor :func:`_label_value_scan` results across every anchor.

    The four value lists are concatenated in anchor order (label first), so the
    gate -- which keeps its Slice 169 same-line-wins / proximity-fallback /
    contradiction logic unchanged -- now sees a value anchored to the authored
    label OR any approved alias, never a stray number floating elsewhere in the
    guide. With no aliases (the synthetic fixtures) this is identical to the
    single-label scan, so existing gate behavior is preserved exactly.
    """
    merged: dict[str, list[float]] = {
        "same_literal": [],
        "same_match": [],
        "prox_literal": [],
        "prox_match": [],
        "same_committed": [],
        "prox_committed": [],
    }
    for norm in anchor_norms:
        scan = _label_value_scan(normalized_lines, norm)
        for key in merged:
            merged[key].extend(scan.get(key, []))
    return merged


def _match_candidate_values(text: str) -> list[float]:
    """Numbers in ``text`` plus format-equivalent readings of those same numbers.

    A percent token such as ``97%`` is read both as its written value ``97`` and as
    its fractional equivalent ``0.97`` so a golden target stored in either form can
    match within the fixture's own tolerance. This only ADDS an equivalent reading
    of a number that is literally present -- it never invents a value and never
    widens a tolerance. It feeds the within-tolerance match test only; contradiction
    detection stays on the literally written numbers so an equivalent reading is not
    mistaken for a competing value.
    """
    values = list(_extract_numbers(text))
    for match in _PERCENT_RE.finditer(text):
        try:
            pct = float(match.group(1))
        except ValueError:
            continue
        if math.isfinite(pct):
            values.append(pct / 100.0)
    return values


# Result separators that mark a committed answer at the end of a worked line
# (Slice 170). A line like ``= (1/2)ln(7) ≈ 0.97`` or ``Total Error = 1/8 = 0.125``
# states intermediate working numbers before the FINAL committed answer. Reading
# only the number(s) after the LAST separator lets the matcher credit the
# committed answer the guide actually lands on, instead of treating the working
# steps as competing values. This is strictly an attribution refinement: a wrong
# committed answer is still wrong, and two different committed answers still
# contradict, so nothing is laundered.
_RESULT_SEP_RE = re.compile(r"[=≈≃→]")


def _committed_answer_numbers(stripped: str) -> list[float]:
    """Literal numbers after the LAST result separator on a worked line.

    Returns ``[]`` when the line states no result separator, so the committed-answer
    path only ever activates on an explicit ``= / ≈ / ≃ / →`` statement and never
    invents a value. Numbers BEFORE the final separator (the working steps) are
    intentionally excluded so a correct final answer is not buried by its own
    derivation.
    """
    matches = list(_RESULT_SEP_RE.finditer(stripped))
    if not matches:
        return []
    return _extract_numbers(stripped[matches[-1].end():])


def _label_value_scan(
    normalized_lines: list[tuple[str, str]], label_norm: str
) -> dict[str, list[float]]:
    """Label-anchored candidate-value scan shared by the gate and the classifier.

    Returns four value lists, every one anchored to an actual occurrence of the
    label so a stray number elsewhere in the guide is never attributed to this
    target:

    - ``same_literal`` : numbers written on the label's own line(s)
    - ``same_match``   : same line(s) + format-equivalent readings (percent)
    - ``prox_literal`` : numbers on the first non-empty line *after* a label line
                         that itself carries no number -- recovers a value split off
                         by a PDF-extraction line break
    - ``prox_match``   : that proximity line + format-equivalent readings
    - ``same_committed`` : committed final-answer number(s) after the last result
                           separator on the label's own line(s) (Slice 170)
    - ``prox_committed`` : committed final-answer number(s) on the proximity line

    All lists are empty when the label appears on no line, so an unrelated value is
    never blindly matched. Proximity is bounded to the single next non-empty line.
    """
    result: dict[str, list[float]] = {
        "same_literal": [],
        "same_match": [],
        "prox_literal": [],
        "prox_match": [],
        "same_committed": [],
        "prox_committed": [],
    }
    if not label_norm:
        return result
    total = len(normalized_lines)
    for index in range(total):
        line_norm, line_raw = normalized_lines[index]
        if label_norm not in line_norm:
            continue
        stripped = _strip_label_spans(line_raw, label_norm)
        same_literal = _extract_numbers(stripped)
        same_match = _match_candidate_values(stripped)
        result["same_literal"].extend(same_literal)
        result["same_match"].extend(same_match)
        result["same_committed"].extend(_committed_answer_numbers(stripped))
        if same_match:
            continue
        # Proximity (value on the next line) is only defensible when the anchor
        # stands alone as a header/label on its own line -- e.g. ``Cross-Entropy:``
        # then ``0.56`` split off by a PDF line break. When the anchor is merely
        # mentioned mid-sentence among other words (a "Covered topics:" list, a
        # prose reference), stripping it leaves other word tokens behind; in that
        # case the next line's number belongs to something else and must not be
        # attributed here. So skip proximity unless the anchor is the line's only
        # word content.
        if _TOKEN_RE.search(stripped):
            continue
        # The label's own line carries no number: recover a value that spilled onto
        # the next non-empty line (a common PDF-extraction line break).
        for probe in range(index + 1, total):
            probe_norm, probe_raw = normalized_lines[probe]
            if not probe_norm.strip():
                continue
            result["prox_literal"].extend(_extract_numbers(probe_raw))
            result["prox_match"].extend(_match_candidate_values(probe_raw))
            result["prox_committed"].extend(_committed_answer_numbers(probe_raw))
            break
    return result


def classify_numeric_target(
    normalized_lines: list[tuple[str, str]], item: dict[str, Any]
) -> dict[str, Any]:
    """Classify one golden numeric target against the candidate's normalized lines.

    Returns a closed diagnostic record (no guide/source snippets) placing the
    target in exactly one of ``found_and_matched``,
    ``found_but_format_or_context_missed``, ``found_but_wrong_value``, or
    ``genuinely_missing``. The matcher anchors on the authored label OR any
    approved safe alias / concept anchor (Slice 170), so a value is attributed to
    its target through the phrasing the guide actually uses -- not only the
    fixture's internal label code, which the guide never prints. Evidence is still
    bounded to the anchor's own line (after stripping the anchor's tokens, so an
    anchor-embedded input parameter is never read as the answer) or the single
    next non-empty line. ``found_and_matched`` is a strict same-line value within
    the EXISTING tolerance; ``found_but_format_or_context_missed`` is a value
    correct within that same tolerance but recovered only via percent-format
    equivalence or a PDF line break -- so a clean run can be audited for how many
    matches were format/proximity-rescued. A value near an anchor but outside
    tolerance, or competing unresolved values, stays ``found_but_wrong_value``: a
    real defect, never laundered. A target with anchor evidence but no usable
    value is ``genuinely_missing`` (label_present_value_absent); a target with no
    anchor on any line at all is ``genuinely_missing`` (label_not_found) -- a stray
    value elsewhere in the guide is never blindly credited.
    """
    expected = _finite_float(item.get("value"))
    tol = _finite_float(item.get("tol")) or 0.0
    anchors = _numeric_anchor_terms(item)

    def _within(values: list[float]) -> float | None:
        if expected is None:
            return None
        for value in values:
            if abs(value - expected) <= tol:
                return value
        return None

    label_found = False
    alias_found = False
    value_found = False
    contradiction_seen = False
    competing_pool: list[float] = []
    # Best winning evidence across anchors, ranked by tier:
    #   1 strict same-line literal match     -> found_and_matched
    #   2 committed same-line final answer    -> found_and_matched (worked steps)
    #   3 format-equivalent same-line          -> found_but_format_or_context_missed
    #   4 committed proximity final answer     -> found_and_matched (worked, next line)
    #   5 proximity next-line                  -> found_but_format_or_context_missed
    # The label anchor is evaluated first and only a strictly lower tier replaces a
    # candidate, so label-anchored evidence wins on ties. Each tuple carries its own
    # closed classification/reason/proximity so nothing is inferred from the number.
    best: tuple[int, float, str, str, str, str] | None = None

    for text, norm, kind in anchors:
        present = any(norm in line_norm for line_norm, _ in normalized_lines)
        if present:
            if kind == "label":
                label_found = True
            else:
                alias_found = True
        scan = _label_value_scan(normalized_lines, norm)
        strict_literal = _dedupe_floats(scan["same_literal"])
        same_match = _dedupe_floats(scan["same_match"])
        prox_literal = _dedupe_floats(scan["prox_literal"])
        prox_match = _dedupe_floats(scan["prox_match"])
        committed_same = _dedupe_floats(scan["same_committed"])
        committed_prox = _dedupe_floats(scan["prox_committed"])
        if strict_literal or same_match or prox_literal or prox_match:
            value_found = True
        # Contradiction is judged per anchor on the literally written numbers
        # closest to that anchor (same-line if present, else the proximity line),
        # exactly as the Slice 169 single-label matcher did.
        if _has_numeric_contradiction(strict_literal or prox_literal, tol):
            contradiction_seen = True
        for value in strict_literal + prox_literal:
            if expected is None or abs(value - expected) > tol:
                competing_pool.append(value)
        alias_label = NUMERIC_ALIAS_PRIMARY if kind == "label" else text
        strict_clean = bool(strict_literal) and not _has_numeric_contradiction(strict_literal, tol)
        same_clean = bool(same_match) and not _has_numeric_contradiction(strict_literal, tol)
        prox_clean = bool(prox_match) and not _has_numeric_contradiction(prox_literal, tol)
        committed_same_clean = (
            bool(committed_same) and not _has_numeric_contradiction(committed_same, tol)
        )
        committed_prox_clean = (
            bool(committed_prox) and not _has_numeric_contradiction(committed_prox, tol)
        )
        candidate: tuple[int, float, str, str, str, str] | None = None
        if strict_clean and _within(strict_literal) is not None:
            candidate = (
                1, _within(strict_literal), alias_label, PROXIMITY_SAME_LINE,  # type: ignore[arg-type]
                "strict_same_line_match", NUMERIC_CLASS_MATCHED,
            )
        elif committed_same_clean and _within(committed_same) is not None:
            candidate = (
                2, _within(committed_same), alias_label, PROXIMITY_SAME_LINE,  # type: ignore[arg-type]
                "worked_final_answer", NUMERIC_CLASS_MATCHED,
            )
        elif same_clean and _within(same_match) is not None:
            candidate = (
                3, _within(same_match), alias_label, PROXIMITY_SAME_LINE,  # type: ignore[arg-type]
                "format_equivalent_same_line", NUMERIC_CLASS_FORMAT_MISSED,
            )
        elif committed_prox_clean and _within(committed_prox) is not None:
            candidate = (
                4, _within(committed_prox), alias_label, PROXIMITY_NEXT_LINE,  # type: ignore[arg-type]
                "worked_final_answer", NUMERIC_CLASS_MATCHED,
            )
        elif prox_clean and _within(prox_match) is not None:
            candidate = (
                5, _within(prox_match), alias_label, PROXIMITY_NEXT_LINE,  # type: ignore[arg-type]
                "proximity_line_break", NUMERIC_CLASS_FORMAT_MISSED,
            )
        if candidate is not None and (best is None or candidate[0] < best[0]):
            best = candidate

    competing_value_count = len(_dedupe_floats(competing_pool))

    if best is not None:
        _tier, matched_value, alias_matched, proximity_mode, reason_code, classification = best
        within_tolerance = True
    elif value_found:
        classification = NUMERIC_CLASS_WRONG_VALUE
        reason_code = "competing_unresolved_values" if contradiction_seen else "value_out_of_tolerance"
        matched_value = None
        alias_matched = NUMERIC_ALIAS_NONE
        proximity_mode = PROXIMITY_NONE
        within_tolerance = False
    elif label_found or alias_found:
        classification = NUMERIC_CLASS_MISSING
        reason_code = "label_present_value_absent"
        matched_value = None
        alias_matched = NUMERIC_ALIAS_NONE
        proximity_mode = PROXIMITY_NONE
        within_tolerance = False
    else:
        classification = NUMERIC_CLASS_MISSING
        reason_code = "label_not_found"
        matched_value = None
        alias_matched = NUMERIC_ALIAS_NONE
        proximity_mode = PROXIMITY_NONE
        within_tolerance = False

    recompute_status = item.get("recompute_status")
    if not isinstance(recompute_status, str) or not recompute_status:
        recompute_status = "not_applicable"
    return {
        "classification": classification,
        "reason_code": reason_code,
        "expected_value": expected,
        "tolerance": tol,
        "matched_value": matched_value,
        "within_tolerance": within_tolerance,
        "label_found": label_found,
        "alias_found": alias_found,
        "alias_matched": alias_matched,
        "value_found": value_found,
        "proximity_mode": proximity_mode,
        "competing_value_count": competing_value_count,
        "recompute_verifier_status": recompute_status,
    }


def classify_numeric_targets(candidate: str, fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Closed per-target numeric diagnostic for every golden target in ``fixture``.

    Runs against the supplied candidate guide text (the operator points it at the
    current unchanged local guide; nothing is regenerated). Returns one closed
    record per target -- safe to log as aggregate counts. Never returns or writes
    guide/source snippets, paths, hashes, or byte counts.
    """
    targets = fixture.get("ground_truth_numerics")
    if not isinstance(targets, list):
        return []
    normalized_lines = [(_normalize(line), line) for line in candidate.splitlines()]
    lecture_id = str(fixture.get("lecture_id") or fixture.get("id") or "")
    out: list[dict[str, Any]] = []
    for position, item in enumerate(targets):
        if not isinstance(item, dict):
            continue
        record = classify_numeric_target(normalized_lines, item)
        record["lecture_id"] = lecture_id
        record["target_id"] = str(item.get("id") or item.get("label") or f"target_{position}")
        out.append(record)
    return out


def summarize_numeric_classification(records: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate closed counts per classification (no per-target detail)."""
    summary = {
        NUMERIC_CLASS_MATCHED: 0,
        NUMERIC_CLASS_FORMAT_MISSED: 0,
        NUMERIC_CLASS_WRONG_VALUE: 0,
        NUMERIC_CLASS_MISSING: 0,
    }
    for record in records:
        key = record.get("classification")
        if key in summary:
            summary[key] += 1
    return summary


# Count-only mock/practice/exam question detector (Slice 169). Also reused by the
# Slice 171 leak structural classifier to attribute a question-like line to the
# ``mock_or_practice_question`` category; it never decides leak blocking on its
# own (genuine deliberation is detected first).
_MOCK_COUNT_DECORATION_RE = re.compile(r"^[\s>#*_+\-]+")
_MOCK_COUNT_BODY_RE = re.compile(
    r"(?:(?:mock|practice)\s+question\b"
    r"|question\s+\d+\b"
    r"|q\d+\b(?:[\s:.)\-]|$))",
    re.IGNORECASE,
)


def _is_mock_question_count_line(line: str) -> bool:
    """Recognize a structurally present mock/practice/exam question line.

    Matches the forms real exam guides emit -- "Mock Question 1", "Practice
    Question 2", "Question 3", "Q4." -- after stripping leading Markdown
    heading/list/emphasis decoration and PDF spacing. It credits a present question
    only: a bare "Mock Exam"/"Solution"/"Answer key" heading, a sentence without a
    question marker, and a stray "?" are not counted, so it cannot manufacture
    questions that are not there.
    """
    cleaned = _MOCK_COUNT_DECORATION_RE.sub("", line, count=1)
    return bool(_MOCK_COUNT_BODY_RE.match(cleaned))


def _ordered(values: set[str], order: tuple[str, ...]) -> list[str]:
    return [token for token in order if token in values]
