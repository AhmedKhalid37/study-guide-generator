"""Closed flat-score diagnostic for Slice 176O.

This module diagnoses why Slice 176N's real OCR-context generation scored
``unchanged`` against the private baseline. It reads private guide artifacts only at
runtime, emits closed labels/counts/statuses only, and never runs generation.

It is diagnostic, not an official score, scorer replacement, judge, repair path, or
threshold tuning surface.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.guide_quality_contract_lint import (  # noqa: E402
    build_guide_quality_contract_lint_report,
)
from pipeline.ocr_context_private_guide import derive_baseline_comparison  # noqa: E402
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402

ARTIFACT_NAME = "flat_score_diagnostic"

STATUSES = frozenset({"completed", "degraded", "blocked", "skipped"})
DIFF_LEVELS = frozenset({"high", "medium", "low", "unavailable"})
ADDED_LEVELS = frozenset({"yes", "partial", "no", "unavailable"})
SCORER_SEMANTICS = frozenset({"deck_specific", "structural_contract", "mixed", "unknown"})
WEIGHTS = frozenset({"high", "medium", "low", "unknown"})
LIKELIHOODS = frozenset({"low", "medium", "high", "unknown"})
EXPLANATIONS = frozenset(
    {"packaging_weak", "model_already_knew", "eval_insensitive", "mixed", "inconclusive"}
)
NEXT_STEPS = frozenset(
    {
        "run_packaging_v2_generation",
        "add_deck_specific_coverage_eval",
        "pivot_to_visible_asset_rendered_guide",
        "test_on_uncommon_deck",
        "manual_private_guide_inspection",
        "blocked",
    }
)

_GENERATED_GUIDE_FILENAME = "real_ocr_context_generated_guide.md"
_GENERATED_SOURCE_FILENAME = "real_ocr_context_source.md"
_VISIBLE_PAYLOAD_FILENAME = "visible_table_figure_pilot.json"

_CATEGORY_MARKERS: dict[str, tuple[str, ...]] = {
    "patient_dataset_table": (
        "patient dataset",
        "chest pain",
        "blocked arteries",
        "blood circulation",
    ),
    "proximity_matrix": (
        "proximity matrix",
        "proximity score",
        "same terminal",
        "terminal node",
    ),
    "decision_tree_or_split_diagram": (
        "decision tree",
        "split diagram",
        "root node",
        "leaf node",
    ),
    "weighted_frequency_or_total_error": (
        "weighted frequency",
        "total error",
        "amount of say",
        "stump",
    ),
}

_STRUCTURE_TOKENS = (
    "required_section_present_count",
    "required_section_count",
    "table_count",
    "warning_count",
    "exam_alert_count",
)
_DECK_SPECIFIC_TOKENS = (
    "source_coverage",
    "coverage_signal_count",
    "golden_pair",
    "target_id",
    "canonical_matcher",
    "deck_specific",
)


def build_closed_flat_score_summary(
    *,
    status: str,
    private_baseline_guide_available: bool = False,
    private_baseline_guide_gitignored: bool = False,
    private_176n_guide_available: bool = False,
    private_176n_guide_gitignored: bool = False,
    private_score_artifacts_available: bool = False,
    private_score_artifacts_gitignored: bool = False,
    guide_content_difference: str = "unavailable",
    ocr_specific_content_added: str = "unavailable",
    visible_asset_difference: str = "unavailable",
    scorer_coverage_semantics: str = "unknown",
    scorer_structure_weight: str = "unknown",
    scorer_deck_specific_weight: str = "unknown",
    eval_insensitive_likelihood: str = "unknown",
    model_prior_likelihood: str = "unknown",
    packaging_weak_likelihood: str = "unknown",
    flat_score_explanation: str = "inconclusive",
    recommended_next_step: str = "blocked",
) -> dict[str, Any]:
    """Return a committed-safe closed summary.

    Raw guide/OCR/table/caption text, prompts, responses, provider payloads, and
    private paths are structurally excluded.
    """
    return {
        "artifact_name": ARTIFACT_NAME,
        "status": _coerce(status, STATUSES, "blocked"),
        "private_baseline_guide_available": bool(private_baseline_guide_available),
        "private_baseline_guide_gitignored": bool(private_baseline_guide_gitignored),
        "private_176n_guide_available": bool(private_176n_guide_available),
        "private_176n_guide_gitignored": bool(private_176n_guide_gitignored),
        "private_score_artifacts_available": bool(private_score_artifacts_available),
        "private_score_artifacts_gitignored": bool(private_score_artifacts_gitignored),
        "raw_baseline_guide_committed": False,
        "raw_176n_guide_committed": False,
        "raw_ocr_committed": False,
        "raw_table_text_committed": False,
        "raw_caption_text_committed": False,
        "prompts_committed": False,
        "responses_committed": False,
        "provider_payloads_committed": False,
        "generation_rerun": False,
        "provider_call_made": False,
        "guide_content_difference": _coerce(guide_content_difference, DIFF_LEVELS, "unavailable"),
        "ocr_specific_content_added": _coerce(ocr_specific_content_added, ADDED_LEVELS, "unavailable"),
        "visible_asset_difference": _coerce(visible_asset_difference, DIFF_LEVELS, "unavailable"),
        "scorer_coverage_semantics": _coerce(
            scorer_coverage_semantics, SCORER_SEMANTICS, "unknown"
        ),
        "scorer_structure_weight": _coerce(scorer_structure_weight, WEIGHTS, "unknown"),
        "scorer_deck_specific_weight": _coerce(
            scorer_deck_specific_weight, WEIGHTS, "unknown"
        ),
        "eval_insensitive_likelihood": _coerce(
            eval_insensitive_likelihood, LIKELIHOODS, "unknown"
        ),
        "model_prior_likelihood": _coerce(model_prior_likelihood, LIKELIHOODS, "unknown"),
        "packaging_weak_likelihood": _coerce(
            packaging_weak_likelihood, LIKELIHOODS, "unknown"
        ),
        "flat_score_explanation": _coerce(
            flat_score_explanation, EXPLANATIONS, "inconclusive"
        ),
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "blocked"),
    }


def run_flat_score_diagnostic(
    *,
    baseline_guide_path: str | None = None,
    baseline_guide_dir: str | None = None,
    guide_176n_path: str | None = None,
    private_ocr_dir: str | None = None,
    private_score_artifact_dir: str | None = None,
) -> dict[str, Any]:
    """Run the private diagnostic and return closed labels only."""
    guide_path = _resolve_176n_guide_path(guide_176n_path, private_ocr_dir)
    baseline_path = _safe_private_file(baseline_guide_path)
    score_dir = _safe_private_dir(private_score_artifact_dir or private_ocr_dir)

    guide_text = _read_private_markdown(guide_path)
    if baseline_path is None and guide_text is not None:
        baseline_path = _discover_private_baseline_guide(baseline_guide_dir, guide_text)
    baseline_text = _read_private_markdown(baseline_path)

    guide_available = guide_text is not None
    baseline_available = baseline_text is not None
    guide_gitignored = _is_private_file(guide_path)
    baseline_gitignored = _is_private_file(baseline_path)
    score_available = _private_score_artifacts_available(score_dir)
    score_gitignored = score_dir is not None and is_private_artifact_dir(score_dir)

    if not guide_available or not baseline_available:
        return build_closed_flat_score_summary(
            status="blocked",
            private_baseline_guide_available=baseline_available,
            private_baseline_guide_gitignored=baseline_gitignored,
            private_176n_guide_available=guide_available,
            private_176n_guide_gitignored=guide_gitignored,
            private_score_artifacts_available=score_available,
            private_score_artifacts_gitignored=score_gitignored,
            recommended_next_step="blocked",
        )

    guide_markers = _category_presence(guide_text)
    baseline_markers = _category_presence(baseline_text)
    source_markers = _source_category_presence(private_ocr_dir)

    guide_diff = _guide_content_difference(guide_text, baseline_text, guide_markers, baseline_markers)
    ocr_added = _ocr_specific_added(guide_markers, baseline_markers, source_markers)
    visible_diff = _visible_asset_difference(guide_markers, baseline_markers, private_ocr_dir)
    scorer = inspect_existing_scorer_semantics()

    routing = _route_explanation(
        guide_content_difference=guide_diff,
        ocr_specific_content_added=ocr_added,
        scorer_coverage_semantics=scorer["scorer_coverage_semantics"],
        scorer_deck_specific_weight=scorer["scorer_deck_specific_weight"],
        baseline_text=baseline_text,
        guide_text=guide_text,
    )

    return build_closed_flat_score_summary(
        status="completed",
        private_baseline_guide_available=True,
        private_baseline_guide_gitignored=baseline_gitignored,
        private_176n_guide_available=True,
        private_176n_guide_gitignored=guide_gitignored,
        private_score_artifacts_available=score_available,
        private_score_artifacts_gitignored=score_gitignored,
        guide_content_difference=guide_diff,
        ocr_specific_content_added=ocr_added,
        visible_asset_difference=visible_diff,
        scorer_coverage_semantics=scorer["scorer_coverage_semantics"],
        scorer_structure_weight=scorer["scorer_structure_weight"],
        scorer_deck_specific_weight=scorer["scorer_deck_specific_weight"],
        eval_insensitive_likelihood=routing["eval_insensitive_likelihood"],
        model_prior_likelihood=routing["model_prior_likelihood"],
        packaging_weak_likelihood=routing["packaging_weak_likelihood"],
        flat_score_explanation=routing["flat_score_explanation"],
        recommended_next_step=routing["recommended_next_step"],
    )


def inspect_existing_scorer_semantics() -> dict[str, str]:
    """Classify the committed scorer semantics from code/config shape.

    The Slice 176N comparison is derived from contract-lint structural counts:
    required sections, table count, exam alerts, warning count. It does not compare
    deck-specific concepts, values, table labels, or source-aligned claims.
    """
    scorer_blob = _read_repo_text("pipeline/ocr_context_private_guide.py") + "\n" + _read_repo_text(
        "pipeline/guide_quality_contract_lint.py"
    )
    structure_hits = sum(1 for token in _STRUCTURE_TOKENS if token in scorer_blob)
    deck_hits = sum(1 for token in _DECK_SPECIFIC_TOKENS if token in scorer_blob)
    if structure_hits >= 4 and deck_hits <= 2:
        return {
            "scorer_coverage_semantics": "structural_contract",
            "scorer_structure_weight": "high",
            "scorer_deck_specific_weight": "low",
        }
    if structure_hits >= 3 and deck_hits >= 3:
        return {
            "scorer_coverage_semantics": "mixed",
            "scorer_structure_weight": "medium",
            "scorer_deck_specific_weight": "medium",
        }
    if deck_hits >= 3:
        return {
            "scorer_coverage_semantics": "deck_specific",
            "scorer_structure_weight": "low",
            "scorer_deck_specific_weight": "high",
        }
    return {
        "scorer_coverage_semantics": "unknown",
        "scorer_structure_weight": "unknown",
        "scorer_deck_specific_weight": "unknown",
    }


def _route_explanation(
    *,
    guide_content_difference: str,
    ocr_specific_content_added: str,
    scorer_coverage_semantics: str,
    scorer_deck_specific_weight: str,
    baseline_text: str,
    guide_text: str,
) -> dict[str, str]:
    similar = _similarity_ratio(baseline_text, guide_text) >= 0.82
    scorer_structural = (
        scorer_coverage_semantics == "structural_contract"
        or scorer_deck_specific_weight == "low"
    )

    if guide_content_difference in {"high", "medium"} and ocr_specific_content_added in {"yes", "partial"}:
        if scorer_structural:
            return {
                "eval_insensitive_likelihood": "high",
                "model_prior_likelihood": "low",
                "packaging_weak_likelihood": "low",
                "flat_score_explanation": "eval_insensitive",
                "recommended_next_step": "add_deck_specific_coverage_eval",
            }
        return {
            "eval_insensitive_likelihood": "medium",
            "model_prior_likelihood": "unknown",
            "packaging_weak_likelihood": "low",
            "flat_score_explanation": "inconclusive",
            "recommended_next_step": "manual_private_guide_inspection",
        }

    if guide_content_difference == "low" or similar:
        if ocr_specific_content_added in {"no", "unavailable"}:
            return {
                "eval_insensitive_likelihood": "medium" if scorer_structural else "low",
                "model_prior_likelihood": "medium",
                "packaging_weak_likelihood": "high",
                "flat_score_explanation": "packaging_weak",
                "recommended_next_step": "run_packaging_v2_generation",
            }
        return {
            "eval_insensitive_likelihood": "medium" if scorer_structural else "low",
            "model_prior_likelihood": "high",
            "packaging_weak_likelihood": "medium",
            "flat_score_explanation": "model_already_knew",
            "recommended_next_step": "test_on_uncommon_deck",
        }

    if scorer_structural:
        return {
            "eval_insensitive_likelihood": "high",
            "model_prior_likelihood": "medium",
            "packaging_weak_likelihood": "medium",
            "flat_score_explanation": "mixed",
            "recommended_next_step": "add_deck_specific_coverage_eval",
        }

    return {
        "eval_insensitive_likelihood": "unknown",
        "model_prior_likelihood": "unknown",
        "packaging_weak_likelihood": "unknown",
        "flat_score_explanation": "inconclusive",
        "recommended_next_step": "manual_private_guide_inspection",
    }


def _guide_content_difference(
    guide_text: str,
    baseline_text: str,
    guide_markers: dict[str, bool],
    baseline_markers: dict[str, bool],
) -> str:
    added = sum(1 for key, value in guide_markers.items() if value and not baseline_markers.get(key))
    removed = sum(1 for key, value in baseline_markers.items() if value and not guide_markers.get(key))
    marker_delta = added + removed
    similarity = _similarity_ratio(guide_text, baseline_text)
    if marker_delta >= 3 or similarity < 0.45:
        return "high"
    if marker_delta >= 1 or similarity < 0.82:
        return "medium"
    return "low"


def _ocr_specific_added(
    guide_markers: dict[str, bool],
    baseline_markers: dict[str, bool],
    source_markers: dict[str, bool],
) -> str:
    source_keys = [key for key, present in source_markers.items() if present]
    if not source_keys:
        return "unavailable"
    added = [key for key in source_keys if guide_markers.get(key) and not baseline_markers.get(key)]
    carried = [key for key in source_keys if guide_markers.get(key)]
    if added:
        return "yes"
    if carried:
        return "partial"
    return "no"


def _visible_asset_difference(
    guide_markers: dict[str, bool],
    baseline_markers: dict[str, bool],
    private_ocr_dir: str | None,
) -> str:
    visible_path = _safe_private_file(
        os.path.join(private_ocr_dir, _VISIBLE_PAYLOAD_FILENAME)
        if isinstance(private_ocr_dir, str)
        else None
    )
    if not visible_path:
        return "unavailable"
    visible_cats = _visible_categories(visible_path)
    if not visible_cats:
        return "unavailable"
    added = sum(1 for key in visible_cats if guide_markers.get(key) and not baseline_markers.get(key))
    carried = sum(1 for key in visible_cats if guide_markers.get(key))
    if added >= 2:
        return "high"
    if added == 1 or carried >= 2:
        return "medium"
    if carried == 1:
        return "low"
    return "unavailable"


def _category_presence(text: str) -> dict[str, bool]:
    lowered = text.lower()
    return {
        key: any(re.search(r"\b" + re.escape(marker) + r"\b", lowered) for marker in markers)
        for key, markers in _CATEGORY_MARKERS.items()
    }


def _source_category_presence(private_ocr_dir: str | None) -> dict[str, bool]:
    source_path = _safe_private_file(
        os.path.join(private_ocr_dir, _GENERATED_SOURCE_FILENAME)
        if isinstance(private_ocr_dir, str)
        else None
    )
    source_text = _read_private_markdown(source_path)
    if source_text:
        return _category_presence(source_text)
    return {key: False for key in _CATEGORY_MARKERS}


def _visible_categories(path: str) -> set[str]:
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception:
        return set()
    assets = payload.get("assets") if isinstance(payload, dict) else None
    out: set[str] = set()
    for asset in assets if isinstance(assets, list) else []:
        if not isinstance(asset, dict):
            continue
        token = asset.get("asset_category")
        if token in _CATEGORY_MARKERS:
            out.add(token)
    return out


def _resolve_176n_guide_path(path: str | None, private_ocr_dir: str | None) -> str | None:
    explicit = _safe_private_file(path)
    if explicit:
        return explicit
    if isinstance(private_ocr_dir, str):
        return _safe_private_file(os.path.join(private_ocr_dir, _GENERATED_GUIDE_FILENAME))
    return None


def _discover_private_baseline_guide(directory: str | None, guide_text: str) -> str | None:
    root = _safe_private_dir(directory)
    if root is None:
        return None
    candidate_report = build_guide_quality_contract_lint_report(guide_text, comprehensive=True)
    first: str | None = None
    unchanged: str | None = None
    try:
        for walk_root, _dirs, files in os.walk(root):
            if not is_private_artifact_dir(walk_root):
                continue
            for name in sorted(files):
                lowered = name.lower()
                if not lowered.endswith(".md"):
                    continue
                if lowered in {_GENERATED_GUIDE_FILENAME, _GENERATED_SOURCE_FILENAME}:
                    continue
                path = _safe_private_file(os.path.join(walk_root, name))
                text = _read_private_markdown(path)
                if text is None:
                    continue
                first = first or path
                baseline_report = build_guide_quality_contract_lint_report(
                    text, comprehensive=True
                )
                signals = derive_baseline_comparison(candidate_report, baseline_report)
                if signals.get("baseline_comparison_status") == "unchanged":
                    unchanged = path
                    break
            if unchanged is not None:
                break
    except Exception:
        return first
    return unchanged or first


def _read_private_markdown(path: str | None) -> str | None:
    if not _is_private_file(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except Exception:
        return None
    return text if text.strip() else None


def _private_score_artifacts_available(path: str | None) -> bool:
    if path is None or not is_private_artifact_dir(path) or not os.path.isdir(path):
        return False
    try:
        for _root, _dirs, files in os.walk(path):
            for name in files:
                lowered = name.lower()
                if lowered.endswith(".json") and ("score" in lowered or "result" in lowered):
                    return True
    except Exception:
        return False
    return False


def _safe_private_file(path: str | None) -> str | None:
    if not isinstance(path, str) or not path:
        return None
    abs_path = os.path.abspath(path)
    if os.path.isfile(abs_path) and is_private_artifact_dir(os.path.dirname(abs_path)):
        return abs_path
    return None


def _safe_private_dir(path: str | None) -> str | None:
    if not isinstance(path, str) or not path:
        return None
    abs_path = os.path.abspath(path)
    if os.path.isdir(abs_path) and is_private_artifact_dir(abs_path):
        return abs_path
    return None


def _is_private_file(path: str | None) -> bool:
    return bool(path and os.path.isfile(path) and is_private_artifact_dir(os.path.dirname(path)))


def _similarity_ratio(left: str, right: str) -> float:
    left_terms = set(_tokenize(left))
    right_terms = set(_tokenize(right))
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / max(1, len(left_terms | right_terms))


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9_]{3,}", text.lower()) if not token.isdigit()]


def _read_repo_text(path: str) -> str:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    abs_path = os.path.join(repo_root, path)
    try:
        with open(abs_path, encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return ""


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def main() -> int:
    summary = run_flat_score_diagnostic(
        baseline_guide_path=os.environ.get("BASELINE_GUIDE_MD"),
        baseline_guide_dir=os.environ.get("BASELINE_GUIDE_DIR"),
        guide_176n_path=os.environ.get("REAL_OCR_CONTEXT_GUIDE_MD"),
        private_ocr_dir=os.environ.get("PRIVATE_OCR_DIR"),
        private_score_artifact_dir=os.environ.get("PRIVATE_SCORE_ARTIFACT_DIR"),
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] in {"completed", "degraded"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
