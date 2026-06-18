"""Phase 0 dev-time reference-anchored eval judge contract (Slice 163).

Pure, unwired contract helpers for the Layer-2 dev-time reference-anchored eval
judge. This judge scores a *candidate* study guide relative to a *Claude
reference* guide (the 9-10 benchmark) on a 0-5 integer scale per axis, with a
calibration step: the judge must also score the reference itself on every axis,
and if any reference axis falls below the floor the run is discarded as
miscalibrated (candidate scores are not used for scoring).

This is a DEV-TIME EVAL contract, NOT the frozen production offline judge and NOT
a production shippability gate. Nothing in this module:

* executes any provider / model / cloud / local-LLM call,
* reads or writes any file,
* persists prompts, responses, or raw model output,
* blends a Layer-2 score into the deterministic ``overall_10``, or
* flips ``judge_ready`` / ``repair_ready`` (both stay ``False`` by construction).

``build_phase0_reference_judge_prompt`` returns an in-memory messages object for a
caller to send later; it does not send it. The candidate-vs-reference text it
embeds is caller-supplied and in-memory only -- committed tests and docs use tiny
synthetic strings exclusively, never real guide / source / reference material.
``sanitize_phase0_reference_judge_output`` parses a JSON-like dict the caller got
back, validates the closed axes and 0-5 scores, enforces the <=15-word evidence
quote limit, classifies calibration, and returns a closed result. The
``phase0_reference_judge_regression_summary`` adapter strips evidence quotes
entirely and yields a record-safe closed summary for the eval harness.
"""
from __future__ import annotations

from typing import Any

from pipeline.quality_safety_eval_harness import (
    PHASE0_EVIDENCE_QUOTE_MAX_WORDS,
    PHASE0_REFERENCE_AXIS_SCORE_MAX,
    PHASE0_REFERENCE_AXIS_SCORE_MIN,
    PHASE0_REFERENCE_CALIBRATION_MIN,
    PHASE0_REFERENCE_JUDGE_AXES,
    PHASE0_REFERENCE_JUDGE_AXIS_SET,
    _SECRETISH_RE,
    load_golden_pair_spec,
)

VERSION = 1
REFERENCE_JUDGE_PROMPT_KIND = "quality_safety_phase0_reference_judge_prompt"
REFERENCE_JUDGE_RESULT_KIND = "quality_safety_phase0_reference_judge_result"

# Re-exported closed contract surface (single source of truth lives in the harness).
AXES = PHASE0_REFERENCE_JUDGE_AXES
AXIS_SET = PHASE0_REFERENCE_JUDGE_AXIS_SET
AXIS_SCORE_MIN = PHASE0_REFERENCE_AXIS_SCORE_MIN
AXIS_SCORE_MAX = PHASE0_REFERENCE_AXIS_SCORE_MAX
REFERENCE_CALIBRATION_MIN = PHASE0_REFERENCE_CALIBRATION_MIN
EVIDENCE_QUOTE_MAX_WORDS = PHASE0_EVIDENCE_QUOTE_MAX_WORDS

RESULT_STATUSES = frozenset(
    {"not_run", "ok", "miscalibrated", "invalid_output", "blocked", "skipped"}
)
CALIBRATION_STATUSES = frozenset({"not_run", "ok", "miscalibrated"})


def _judge_instruction() -> str:
    """Build the closed judge instruction string from the contract constants."""
    axes = ", ".join(AXES)
    return (
        "You are a strict study-guide evaluation judge. "
        "The REFERENCE guide is the 9-10 benchmark; treat it as the gold standard. "
        "Score the CANDIDATE guide relative to the REFERENCE on each axis. "
        f"Axes: {axes}. "
        f"Each axis is scored as an integer from {AXIS_SCORE_MIN} to {AXIS_SCORE_MAX}. "
        "Calibration requirement: you must ALSO score the REFERENCE itself on every "
        f"axis; the reference must score at least {REFERENCE_CALIBRATION_MIN} on every "
        "axis or the run is miscalibrated and your candidate scores are discarded. "
        "Respond with strict JSON only -- no prose and no markdown fences. "
        f"For each axis include a short evidence quote of at most "
        f"{EVIDENCE_QUOTE_MAX_WORDS} words."
    )


def build_phase0_reference_judge_prompt(
    reference_text: Any, candidate_text: Any, golden_spec: Any
) -> dict[str, Any]:
    """Construct the Layer-2 reference-anchored judge prompt for one golden pair.

    Pure prompt construction only: it validates the golden-pair spec (so the
    lecture id stays within the closed ``{nn3, ensemble}`` set), then returns a
    messages object a caller can later send to a model with their own key. It
    performs NO provider/model call and writes NO file. The reference/candidate
    text is embedded in-memory because that is what a caller would send; it must
    never be a committed test/doc value other than tiny synthetic strings.
    """
    spec = load_golden_pair_spec(golden_spec)
    reference = reference_text if isinstance(reference_text, str) else ""
    candidate = candidate_text if isinstance(candidate_text, str) else ""
    instruction = _judge_instruction()
    user_content = (
        "Evaluate the CANDIDATE guide against the REFERENCE guide.\n"
        f"=== REFERENCE (benchmark; must score >= {REFERENCE_CALIBRATION_MIN} "
        "on every axis) ===\n"
        f"{reference}\n"
        "=== CANDIDATE (scored relative to the reference) ===\n"
        f"{candidate}\n"
    )
    return {
        "kind": REFERENCE_JUDGE_PROMPT_KIND,
        "version": VERSION,
        "lecture_id": spec["lecture_id"],
        "axes": list(AXES),
        "axis_score_min": AXIS_SCORE_MIN,
        "axis_score_max": AXIS_SCORE_MAX,
        "reference_calibration_min": REFERENCE_CALIBRATION_MIN,
        "evidence_quote_max_words": EVIDENCE_QUOTE_MAX_WORDS,
        "response_format": "strict_json",
        "messages": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": user_content},
        ],
        "judge_ready": False,
        "repair_ready": False,
    }


def sanitize_phase0_reference_judge_output(
    raw: Any, golden_spec: Any
) -> dict[str, Any]:
    """Validate and sanitize a parsed Layer-2 judge output into a closed result.

    ``raw`` is expected to be a parsed JSON-like dict carrying ``candidate_scores``
    and ``reference_scores`` (axis -> integer 0..5) plus an optional ``evidence``
    (axis -> short quote). Only those known fields are read; every other field is
    dropped, so no raw model output, prompt, provider payload, path, filename,
    hash, or byte count can survive. Unknown axis names and out-of-range scores
    classify the output as ``invalid_output``. Evidence quotes over
    ``EVIDENCE_QUOTE_MAX_WORDS`` words (or any secret-ish/path-ish quote) are
    dropped and counted. If any reference axis is below
    ``REFERENCE_CALIBRATION_MIN`` (or the reference is incomplete) the result is
    ``miscalibrated`` and candidate scores are not retained. ``judge_ready`` and
    ``repair_ready`` are always ``False``.
    """
    spec = load_golden_pair_spec(golden_spec)
    warnings: set[str] = set()

    if not isinstance(raw, dict):
        return _invalid_result(spec, {"non_dict_output"})

    candidate_scores, candidate_ok = _parse_axis_scores(
        raw.get("candidate_scores"), warnings, role="candidate"
    )
    reference_scores, reference_ok = _parse_axis_scores(
        raw.get("reference_scores"), warnings, role="reference"
    )
    if not candidate_ok or not reference_ok:
        warnings.add("invalid_axis_scores")
        return _invalid_result(spec, warnings)
    if set(candidate_scores) != AXIS_SET:
        warnings.add("incomplete_candidate_axes")
        return _invalid_result(spec, warnings)

    evidence, dropped = _sanitize_evidence(raw.get("evidence"), warnings)

    calibration_ok = set(reference_scores) == AXIS_SET and all(
        score >= REFERENCE_CALIBRATION_MIN for score in reference_scores.values()
    )
    if calibration_ok:
        status = "ok"
        calibration_status = "ok"
        included = True
    else:
        status = "miscalibrated"
        calibration_status = "miscalibrated"
        included = False
        warnings.add("reference_below_calibration_floor")

    result: dict[str, Any] = {
        "kind": REFERENCE_JUDGE_RESULT_KIND,
        "version": VERSION,
        "lecture_id": spec["lecture_id"],
        "status": status,
        "calibration_status": calibration_status,
        "layer2_judge_included": included,
        "axes": list(AXES),
        "reference_axis_scores": reference_scores,
        "axis_count": len(candidate_scores),
        "evidence_quote_dropped_count": dropped,
        "judge_ready": False,
        "repair_ready": False,
        "warnings": sorted(warnings),
    }
    # Candidate scores (and any short evidence quotes) are retained only when the
    # run is calibrated; a miscalibrated run discards them for scoring.
    if included:
        result["candidate_axis_scores"] = candidate_scores
        if evidence:
            result["evidence"] = evidence
    return result


def phase0_reference_judge_regression_summary(sanitized: Any) -> dict[str, Any]:
    """Adapt a sanitized Layer-2 result into a record-safe closed summary.

    Drops evidence quotes entirely (regression records forbid quote fields) and
    keeps only closed statuses, the included flag, and bounded integer axis scores.
    Suitable to hand to
    ``quality_safety_eval_harness.build_phase0_regression_record`` via its
    ``reference_judge_summary`` argument. ``layer2_judge_included`` is ``True`` only
    when the result is fully calibrated and ``ok``.
    """
    data = sanitized if isinstance(sanitized, dict) else {}
    status = data.get("status")
    if status not in RESULT_STATUSES:
        status = "invalid_output"
    calibration = data.get("calibration_status")
    if calibration not in CALIBRATION_STATUSES:
        calibration = "not_run"
    included = status == "ok" and calibration == "ok"

    summary: dict[str, Any] = {
        "status": status,
        "calibration_status": calibration,
        "layer2_judge_included": included,
    }
    candidate = _closed_scores(data.get("candidate_axis_scores"))
    reference = _closed_scores(data.get("reference_axis_scores"))
    if included and candidate:
        summary["candidate_axis_scores"] = candidate
    if reference:
        summary["reference_axis_scores"] = reference
    return summary


def _parse_axis_scores(
    raw: Any, warnings: set[str], *, role: str
) -> tuple[dict[str, int], bool]:
    if not isinstance(raw, dict):
        warnings.add(f"{role}_scores_missing")
        return {}, False
    scores: dict[str, int] = {}
    for axis, value in raw.items():
        if axis not in AXIS_SET:
            warnings.add("unknown_axis")
            return {}, False
        if not _valid_score(value):
            warnings.add("score_out_of_range")
            return {}, False
        scores[axis] = int(value)
    return scores, True


def _sanitize_evidence(raw: Any, warnings: set[str]) -> tuple[dict[str, str], int]:
    if not isinstance(raw, dict):
        return {}, 0
    evidence: dict[str, str] = {}
    dropped = 0
    for axis, quote in raw.items():
        if axis not in AXIS_SET:
            warnings.add("unknown_axis_evidence_dropped")
            continue
        if not isinstance(quote, str):
            dropped += 1
            warnings.add("invalid_evidence_quote_dropped")
            continue
        cleaned = " ".join(quote.split())
        if not cleaned:
            continue
        if len(cleaned.split()) > EVIDENCE_QUOTE_MAX_WORDS:
            dropped += 1
            warnings.add("evidence_quote_too_long_dropped")
            continue
        if _SECRETISH_RE.search(cleaned):
            dropped += 1
            warnings.add("evidence_quote_unsafe_dropped")
            continue
        evidence[axis] = cleaned
    return evidence, dropped


def _closed_scores(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, int] = {}
    for axis in AXES:
        score = value.get(axis)
        if _valid_score(score):
            out[axis] = int(score)
    return out


def _valid_score(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and AXIS_SCORE_MIN <= value <= AXIS_SCORE_MAX
    )


def _invalid_result(spec: dict[str, Any], warnings: set[str]) -> dict[str, Any]:
    return {
        "kind": REFERENCE_JUDGE_RESULT_KIND,
        "version": VERSION,
        "lecture_id": spec["lecture_id"],
        "status": "invalid_output",
        "calibration_status": "not_run",
        "layer2_judge_included": False,
        "axes": list(AXES),
        "axis_count": 0,
        "evidence_quote_dropped_count": 0,
        "judge_ready": False,
        "repair_ready": False,
        "warnings": sorted(warnings),
    }
