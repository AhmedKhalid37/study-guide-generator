"""Deterministic guide-quality scoring core (Slice 20 — eval harness Phase 1).

This is the *measurement spine* for GuideForge guide quality. It scores a guide
Markdown string against a golden spec using only the pure correctness modules
shipped in earlier slices:

  * :func:`pipeline.math_verifier.verify_math_claims` (Slice 18 — numeric math)
  * :func:`pipeline.guide_lint.lint_guide_markdown`   (Slice 19 — structure/lint)

plus two simple, deterministic string checks defined here (concept coverage and
must-not-claim). **No** embeddings, **no** LLM judges, **no** retrieval, **no**
OCR, **no** network. Everything here is pure: given the same spec + guide text it
always returns the same scores.

Scope (Slice 20): this module does not touch generation prompts, provider
behavior, ``/api/jobs/llm`` fields, the Builder/JobDetails UI, or job artifacts.
It is a standalone scoring library consumed by ``run_eval.py``.

Scoring metrics (all in ``[0.0, 1.0]``, higher is better):

  concepts        coverage of ``required_concepts`` by normalized substring match
                  = found / total           (1.0 when none required)
  must_not_claim  1.0 minus the fraction of forbidden phrases that appear
                  = (total - violations) / total   (1.0 when none specified)
  math            credit over extracted numeric claims, where a ``mismatch`` earns
                  no credit and an ``unparseable`` claim earns partial credit so
                  mismatches are penalized harder than claims we could not parse:
                  = (ok + UNPARSEABLE_CREDIT * unparseable) / total
                    (1.0 when no claims are found — never fails on unparseable)
  lint            1.0 minus a weighted penalty where lint *errors* cost more than
                  *warnings* (``info`` is ignored), clamped to ``[0, 1]``:
                  = clamp(1 - (ERROR_WEIGHT*errors + WARNING_WEIGHT*warnings))
  artifacts       present / expected in live mode; ``None`` (not applicable)
                  in offline mode

  overall         weighted average of the non-null component scores, with the
                  weights renormalized over whichever components are present
                  (so offline runs — where ``artifacts`` is ``None`` — are not
                  penalized for the missing component).
"""
from __future__ import annotations

import os
import re
import sys

# Make ``pipeline`` importable when this file is run/loaded from anywhere.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pipeline.guide_lint import lint_guide_markdown  # noqa: E402
from pipeline.math_verifier import verify_math_claims  # noqa: E402

VERSION = 1

# ── Tunable scoring constants (documented above; keep in sync with the README) ─
UNPARSEABLE_CREDIT = 0.75   # partial credit for an unparseable math claim
LINT_ERROR_WEIGHT = 0.20    # penalty per lint error
LINT_WARNING_WEIGHT = 0.05  # penalty per lint warning
MAX_TOP_FINDINGS = 5        # lint findings echoed into the result detail
MAX_VIOLATION_EXCERPTS = 5  # must-not-claim excerpts echoed into the result
EXCERPT_LEN = 160

# Relative importance of each component in the overall score. Components that are
# ``None`` for a given run are dropped and the remaining weights renormalized.
DEFAULT_WEIGHTS = {
    "concepts": 0.30,
    "math": 0.25,
    "lint": 0.20,
    "must_not_claim": 0.15,
    "artifacts": 0.10,
}

REQUIRED_SPEC_FIELDS = ("id",)
# Spec list fields that, when present, must be lists of strings.
_STR_LIST_FIELDS = ("expected_sections", "required_concepts", "must_not_claim")


class SpecError(ValueError):
    """Raised when a golden spec is structurally invalid."""


# ── Normalization for plain string matching ───────────────────────────────────

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_text(text: str) -> str:
    """Lowercase, collapse every non-alphanumeric run to a single space, strip.

    Deterministic and punctuation/casing tolerant — the basis for concept and
    must-not-claim matching. No stemming, no embeddings.
    """
    if not isinstance(text, str):
        return ""
    return _NON_ALNUM_RE.sub(" ", text.lower()).strip()


def _excerpt(text: str, limit: int = EXCERPT_LEN) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


# ── Spec validation ────────────────────────────────────────────────────────────

def validate_spec(spec: object) -> dict:
    """Return *spec* unchanged if structurally valid, else raise :class:`SpecError`."""
    if not isinstance(spec, dict):
        raise SpecError("spec must be a JSON object / mapping")
    for field in REQUIRED_SPEC_FIELDS:
        if not spec.get(field) or not isinstance(spec[field], str):
            raise SpecError(f"spec is missing required string field '{field}'")
    for field in _STR_LIST_FIELDS:
        value = spec.get(field)
        if value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise SpecError(f"spec field '{field}' must be a list of strings")
    guides = spec.get("offline_guides")
    if guides is not None and (
        not isinstance(guides, list) or not all(isinstance(v, str) for v in guides)
    ):
        raise SpecError("spec field 'offline_guides' must be a list of paths")
    return spec


# ── Metric 1: concept coverage ─────────────────────────────────────────────────

def score_concepts(guide_text: str, required_concepts: list[str] | None) -> tuple[float, list[str]]:
    """Fraction of required concepts found by normalized substring match.

    Returns ``(score, missing_concepts)``. With no required concepts the score is
    ``1.0`` and nothing is missing.
    """
    concepts = [c for c in (required_concepts or []) if isinstance(c, str) and c.strip()]
    if not concepts:
        return 1.0, []
    haystack = normalize_text(guide_text)
    missing: list[str] = []
    for concept in concepts:
        needle = normalize_text(concept)
        if needle and needle in haystack:
            continue
        missing.append(concept.strip())
    found = len(concepts) - len(missing)
    return found / len(concepts), missing


# ── Metric 2: must-not-claim ────────────────────────────────────────────────────

def score_must_not_claim(
    guide_text: str, must_not_claim: list[str] | None
) -> tuple[float, list[dict]]:
    """Penalize forbidden phrases that appear (normalized substring match).

    Returns ``(score, violations)`` where each violation is
    ``{"phrase": ..., "excerpt": ...}``. With nothing forbidden the score is 1.0.
    """
    phrases = [p for p in (must_not_claim or []) if isinstance(p, str) and p.strip()]
    if not phrases:
        return 1.0, []
    haystack = normalize_text(guide_text)
    violations: list[dict] = []
    for phrase in phrases:
        needle = normalize_text(phrase)
        if needle and needle in haystack:
            violations.append({"phrase": phrase.strip(), "excerpt": _excerpt(phrase)})
    score = (len(phrases) - len(violations)) / len(phrases)
    return score, violations[:MAX_VIOLATION_EXCERPTS]


# ── Metric 3: math correctness (reuses Slice 18) ────────────────────────────────

def score_math(guide_text: str) -> tuple[float, dict]:
    """Run the deterministic math verifier and turn its summary into a score.

    Mismatches earn no credit; unparseable claims earn ``UNPARSEABLE_CREDIT`` so
    they are penalized far less than real errors. No claims → ``1.0`` (the harness
    never fails just because a guide has no checkable numbers).
    """
    report = verify_math_claims(guide_text)
    summary = dict(report.summary)
    total = summary.get("total", 0)
    if total <= 0:
        return 1.0, summary
    ok = summary.get("ok", 0)
    unparseable = summary.get("unparseable", 0)
    score = (ok + UNPARSEABLE_CREDIT * unparseable) / total
    return _clamp01(score), summary


# ── Metric 4: structure / lint (reuses Slice 19) ────────────────────────────────

def score_lint(
    guide_text: str, expected_sections: list[str] | None, *, run_katex: bool = False
) -> tuple[float, dict, list[dict]]:
    """Run the advisory linter and turn its severity counts into a score.

    KaTeX is **off by default** here so offline scoring stays fast and
    dependency-free; ``run_katex=True`` opts into the Node/KaTeX bridge (which
    still degrades to an info finding when unavailable). Errors are penalized
    harder than warnings; info findings are ignored.
    """
    report = lint_guide_markdown(
        guide_text, expected_sections=expected_sections, run_katex=run_katex
    )
    summary = dict(report.summary)
    errors = summary.get("error", 0)
    warnings = summary.get("warning", 0)
    penalty = LINT_ERROR_WEIGHT * errors + LINT_WARNING_WEIGHT * warnings
    score = _clamp01(1.0 - penalty)
    top = [
        {
            "rule": f.rule,
            "severity": f.severity,
            "line": f.line,
            "message": f.message,
        }
        for f in report.findings[:MAX_TOP_FINDINGS]
    ]
    return score, summary, top


# ── Metric 5: artifacts (live mode only) ────────────────────────────────────────

def score_artifacts(artifacts: dict | None) -> tuple[float | None, dict | None]:
    """Score artifact presence for live mode.

    *artifacts* maps an artifact name (``"markdown"``, ``"html"``, ``"pdf"``,
    ``"docx"``) to a truthy "present" flag. Returns ``(None, None)`` when no
    artifact info is supplied (offline mode → not applicable).
    """
    if not artifacts:
        return None, None
    present = sum(1 for ok in artifacts.values() if ok)
    total = len(artifacts)
    score = present / total if total else 1.0
    return _clamp01(score), {"present": present, "expected": total, "by_name": dict(artifacts)}


# ── Overall score ────────────────────────────────────────────────────────────────

def compute_overall(scores: dict) -> float:
    """Weighted average over the non-null component scores (weights renormalized)."""
    num = 0.0
    den = 0.0
    for name, weight in DEFAULT_WEIGHTS.items():
        value = scores.get(name)
        if value is None:
            continue
        num += weight * value
        den += weight
    if den == 0:
        return 0.0
    return _clamp01(num / den)


# ── Top-level result builder ──────────────────────────────────────────────────

def build_result(
    spec: dict,
    guide_text: str,
    *,
    guide_path: str | None = None,
    mode: str = "offline",
    artifacts: dict | None = None,
    run_katex: bool = False,
) -> dict:
    """Score *guide_text* against *spec* and return a JSON-serializable result.

    The ``run_id`` is intentionally left out here so this function stays pure and
    deterministic (the CLI stamps it). Contains only derived metrics and short
    excerpts from the guide/spec — never provider keys, tokens, URLs, or argv.
    """
    validate_spec(spec)

    concept_score, missing_concepts = score_concepts(
        guide_text, spec.get("required_concepts")
    )
    must_score, violations = score_must_not_claim(guide_text, spec.get("must_not_claim"))
    math_score, math_summary = score_math(guide_text)
    lint_score, lint_summary, lint_top = score_lint(
        guide_text, spec.get("expected_sections"), run_katex=run_katex
    )
    artifact_score, artifact_detail = score_artifacts(artifacts)

    scores = {
        "concepts": concept_score,
        "math": math_score,
        "lint": lint_score,
        "must_not_claim": must_score,
        "artifacts": artifact_score,
    }
    overall = compute_overall(scores)

    return {
        "version": VERSION,
        "mode": mode,
        "spec_id": spec.get("id"),
        "spec_title": spec.get("title"),
        "guide_path": guide_path,
        "scores": {
            "overall": _round(overall),
            "concepts": _round(concept_score),
            "math": _round(math_score),
            "lint": _round(lint_score),
            "must_not_claim": _round(must_score),
            "artifacts": _round(artifact_score),
        },
        "details": {
            "missing_concepts": missing_concepts,
            "must_not_claim_violations": violations,
            "math_summary": math_summary,
            "lint_summary": lint_summary,
            "lint_top_findings": lint_top,
            "artifacts": artifact_detail,
        },
    }
