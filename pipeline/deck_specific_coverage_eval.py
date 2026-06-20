"""Closed deterministic deck-specific coverage eval for Slice 176P.

This module compares a private baseline guide with the private Slice 176N OCR-context
guide against closed deck-specific marker IDs derived from existing private OCR and
visible-asset artifact categories. It reads guide/OCR text only at runtime, emits
closed statuses only, and never runs generation, a provider, a judge, repair, or the
official contract scorer.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402

ARTIFACT_NAME = "deck_specific_coverage_eval"
SOURCE_LABEL_DEFAULT = "ensemble"

STATUSES = frozenset({"completed", "degraded", "blocked", "skipped"})
MARKER_SOURCES = frozenset(
    {"private_artifact_categories", "closed_static_ids", "mixed_closed_ids", "unavailable"}
)
COUNT_BUCKETS = frozenset({"low", "medium", "high", "unknown"})
COVERAGE_BUCKETS = frozenset({"high", "medium", "low", "unknown"})
DELTAS = frozenset({"improved", "unchanged", "regressed", "unavailable"})
ROLES = frozenset({"diagnostic", "official_candidate", "not_official"})
SCORER_MUTATION = frozenset({"yes", "no", "not_yet"})
NEXT_STEPS = frozenset(
    {
        "integrate_deck_specific_coverage_as_advisory_eval",
        "inspect_private_guide_for_content_quality",
        "run_packaging_v2_generation",
        "pivot_to_rendered_visible_asset_insertion",
        "test_on_uncommon_deck",
        "blocked",
    }
)
MARKER_STATUSES = frozenset({"present", "partial", "absent", "not_checked"})

_GENERATED_GUIDE_FILENAME = "real_ocr_context_generated_guide.md"
_GENERATED_SOURCE_FILENAME = "real_ocr_context_source.md"
_MANIFEST_FILENAME = "extracted_content_manifest.json"
_VISIBLE_PAYLOAD_FILENAME = "visible_table_figure_pilot.json"

_CATEGORY_MAP = {
    "ensemble_proximity_matrix": "proximity_matrix",
    "ensemble_patient_dataset_table": "patient_dataset_table",
    "ensemble_decision_tree_or_split_diagram": "decision_tree_or_split_diagram",
    "ensemble_gini_or_leaf_count": "gini_or_leaf_count_answer_summary",
    "ensemble_weighted_frequency_or_total_error": "weighted_frequency_or_total_error",
}

_CLOSED_MARKERS: dict[str, dict[str, Any]] = {
    "patient_dataset_table": {
        "source_categories": ("patient_dataset_table",),
        "term_groups": (("patient dataset", "patient table"), ("table", "dataset")),
    },
    "proximity_matrix": {
        "source_categories": ("proximity_matrix",),
        "term_groups": (("proximity matrix", "proximity score"), ("terminal node", "same terminal")),
    },
    "decision_tree_or_split_diagram": {
        "source_categories": ("decision_tree_or_split_diagram",),
        "term_groups": (("decision tree", "split diagram"), ("root node", "leaf node", "split")),
    },
    "weighted_frequency_or_total_error": {
        "source_categories": ("weighted_frequency_or_total_error",),
        "term_groups": (("weighted frequency", "total error"), ("stump", "amount of say")),
    },
    "gini_or_leaf_count_answer_summary": {
        "source_categories": ("gini_or_leaf_count_answer_summary",),
        "term_groups": (("gini", "leaf count"), ("split", "impurity", "leaf")),
    },
    "ensemble_core_terms": {
        "source_categories": tuple(_CATEGORY_MAP.values()),
        "term_groups": (("ensemble", "random forest", "boosting"), ("tree", "stump", "vote")),
    },
    "visible_table_asset_reference": {
        "source_categories": ("patient_dataset_table", "proximity_matrix"),
        "visible_categories": ("patient_dataset_table", "proximity_matrix"),
        "term_groups": (("table", "reference table"), ("patient dataset", "proximity matrix")),
    },
    "visible_diagram_asset_reference": {
        "source_categories": ("decision_tree_or_split_diagram",),
        "visible_categories": ("decision_tree_or_split_diagram",),
        "term_groups": (("diagram", "figure", "split diagram"), ("decision tree", "split")),
    },
    "active_recall_from_recovered_content": {
        "source_categories": tuple(_CATEGORY_MAP.values()),
        "term_groups": (("self-test", "active recall", "practice", "check yourself"), ("recovered", "table", "diagram")),
    },
    "explanation_of_recovered_table_or_diagram": {
        "source_categories": tuple(_CATEGORY_MAP.values()),
        "term_groups": (("explain", "interpret", "use the"), ("table", "diagram", "matrix")),
    },
}


def build_closed_deck_specific_coverage_summary(
    *,
    status: str,
    source_label: str = SOURCE_LABEL_DEFAULT,
    private_baseline_guide_available: bool = False,
    private_baseline_guide_gitignored: bool = False,
    private_176n_guide_available: bool = False,
    private_176n_guide_gitignored: bool = False,
    private_ocr_artifact_available: bool = False,
    private_ocr_artifact_gitignored: bool = False,
    private_visible_artifact_available: bool = False,
    private_visible_artifact_gitignored: bool = False,
    marker_source: str = "unavailable",
    markers: list[dict[str, str]] | None = None,
    recommended_next_step: str | None = None,
) -> dict[str, Any]:
    """Return a committed-safe closed summary.

    Raw guide/OCR/table/caption text, prompts, responses, provider payloads, and
    private paths are structurally excluded.
    """
    safe_markers = [_safe_marker_record(m) for m in (markers or []) if isinstance(m, dict)]
    marker_count_bucket = _count_bucket(len(safe_markers))
    baseline_coverage = _coverage_bucket(_coverage_ratio(safe_markers, "baseline_status"))
    ocr_coverage = _coverage_bucket(_coverage_ratio(safe_markers, "ocr_context_status"))
    deck_delta = _delta_from_ratios(
        _coverage_ratio(safe_markers, "baseline_status"),
        _coverage_ratio(safe_markers, "ocr_context_status"),
    )
    visible_delta = _delta_for_subset(safe_markers, {"visible_table_asset_reference", "visible_diagram_asset_reference"})
    recovered_delta = _delta_for_subset(
        safe_markers,
        {
            "patient_dataset_table",
            "proximity_matrix",
            "decision_tree_or_split_diagram",
            "weighted_frequency_or_total_error",
            "gini_or_leaf_count_answer_summary",
            "explanation_of_recovered_table_or_diagram",
        },
    )
    active_delta = _delta_for_subset(safe_markers, {"active_recall_from_recovered_content"})

    coerced_status = _coerce(status, STATUSES, "blocked")
    if recommended_next_step is None:
        recommended_next_step = _route_next_step(
            status=coerced_status,
            baseline_coverage=baseline_coverage,
            ocr_coverage=ocr_coverage,
            deck_delta=deck_delta,
            visible_delta=visible_delta,
            recovered_delta=recovered_delta,
        )

    return {
        "artifact_name": ARTIFACT_NAME,
        "status": coerced_status,
        "source_label": _safe_label(source_label),
        "private_baseline_guide_available": bool(private_baseline_guide_available),
        "private_baseline_guide_gitignored": bool(private_baseline_guide_gitignored),
        "private_176n_guide_available": bool(private_176n_guide_available),
        "private_176n_guide_gitignored": bool(private_176n_guide_gitignored),
        "private_ocr_artifact_available": bool(private_ocr_artifact_available),
        "private_ocr_artifact_gitignored": bool(private_ocr_artifact_gitignored),
        "private_visible_artifact_available": bool(private_visible_artifact_available),
        "private_visible_artifact_gitignored": bool(private_visible_artifact_gitignored),
        "raw_baseline_guide_committed": False,
        "raw_176n_guide_committed": False,
        "raw_ocr_committed": False,
        "raw_table_text_committed": False,
        "raw_caption_text_committed": False,
        "prompts_committed": False,
        "responses_committed": False,
        "provider_payloads_committed": False,
        "provider_call_made": False,
        "generation_rerun": False,
        "marker_source": _coerce(marker_source, MARKER_SOURCES, "unavailable"),
        "marker_count_bucket": _coerce(marker_count_bucket, COUNT_BUCKETS, "unknown"),
        "baseline_deck_specific_coverage": _coerce(baseline_coverage, COVERAGE_BUCKETS, "unknown"),
        "ocr_context_deck_specific_coverage": _coerce(ocr_coverage, COVERAGE_BUCKETS, "unknown"),
        "deck_specific_coverage_delta": _coerce(deck_delta, DELTAS, "unavailable"),
        "visible_asset_coverage_delta": _coerce(visible_delta, DELTAS, "unavailable"),
        "recovered_content_usage_delta": _coerce(recovered_delta, DELTAS, "unavailable"),
        "active_recall_from_recovered_content_delta": _coerce(active_delta, DELTAS, "unavailable"),
        "coverage_eval_role": "diagnostic",
        "should_modify_contract_scorer": "no",
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "blocked"),
        "markers": safe_markers,
    }


def run_deck_specific_coverage_eval(
    *,
    baseline_guide_path: str | None = None,
    guide_176n_path: str | None = None,
    private_ocr_dir: str | None = None,
    visible_artifact_path: str | None = None,
    source_label: str = SOURCE_LABEL_DEFAULT,
) -> dict[str, Any]:
    """Run the private eval and return closed marker coverage only."""
    private_dir = _safe_private_dir(private_ocr_dir)
    baseline_path = _safe_private_file(baseline_guide_path)
    guide_path = _resolve_176n_guide_path(guide_176n_path, private_dir)
    visible_path = _resolve_visible_path(visible_artifact_path, private_dir)
    manifest_path = _safe_private_file(
        os.path.join(private_dir, _MANIFEST_FILENAME) if private_dir else None
    )
    source_path = _safe_private_file(
        os.path.join(private_dir, _GENERATED_SOURCE_FILENAME) if private_dir else None
    )

    baseline_text = _read_private_markdown(baseline_path)
    guide_text = _read_private_markdown(guide_path)
    source_text = _read_private_markdown(source_path)
    manifest_categories = _manifest_categories(manifest_path)
    source_categories = _source_categories(source_text)
    visible_categories = _visible_categories(visible_path)

    baseline_available = baseline_text is not None
    guide_available = guide_text is not None
    ocr_available = bool(manifest_categories or source_categories or source_path)
    visible_available = bool(visible_categories or visible_path)

    if not baseline_available or not guide_available or not ocr_available:
        return build_closed_deck_specific_coverage_summary(
            status="blocked",
            source_label=source_label,
            private_baseline_guide_available=baseline_available,
            private_baseline_guide_gitignored=_is_private_file(baseline_path),
            private_176n_guide_available=guide_available,
            private_176n_guide_gitignored=_is_private_file(guide_path),
            private_ocr_artifact_available=ocr_available,
            private_ocr_artifact_gitignored=private_dir is not None and is_private_artifact_dir(private_dir),
            private_visible_artifact_available=visible_available,
            private_visible_artifact_gitignored=_is_private_file(visible_path),
            marker_source="unavailable",
            recommended_next_step="blocked",
        )

    expected_categories = set(manifest_categories) | set(source_categories)
    marker_ids = _select_marker_ids(expected_categories, set(visible_categories))
    markers = [
        _evaluate_marker(marker_id, baseline_text or "", guide_text or "", expected_categories, set(visible_categories))
        for marker_id in marker_ids
    ]
    marker_source = "private_artifact_categories" if expected_categories else "closed_static_ids"

    return build_closed_deck_specific_coverage_summary(
        status="completed" if markers else "degraded",
        source_label=source_label,
        private_baseline_guide_available=True,
        private_baseline_guide_gitignored=_is_private_file(baseline_path),
        private_176n_guide_available=True,
        private_176n_guide_gitignored=_is_private_file(guide_path),
        private_ocr_artifact_available=True,
        private_ocr_artifact_gitignored=private_dir is not None and is_private_artifact_dir(private_dir),
        private_visible_artifact_available=visible_available,
        private_visible_artifact_gitignored=_is_private_file(visible_path),
        marker_source=marker_source,
        markers=markers,
    )


def _select_marker_ids(categories: set[str], visible_categories: set[str]) -> list[str]:
    selected: list[str] = []
    for marker_id, spec in _CLOSED_MARKERS.items():
        source_hits = set(spec.get("source_categories", ())) & categories
        visible_hits = set(spec.get("visible_categories", ())) & visible_categories
        if source_hits or visible_hits:
            selected.append(marker_id)
    return selected


def _evaluate_marker(
    marker_id: str,
    baseline_text: str,
    guide_text: str,
    expected_categories: set[str],
    visible_categories: set[str],
) -> dict[str, str]:
    spec = _CLOSED_MARKERS.get(marker_id, {})
    source_ok = bool(set(spec.get("source_categories", ())) & expected_categories)
    visible_spec = set(spec.get("visible_categories", ()))
    visible_ok = not visible_spec or bool(visible_spec & visible_categories)
    if not source_ok and not visible_ok:
        baseline_status = "not_checked"
        guide_status = "not_checked"
    else:
        groups = spec.get("term_groups", ())
        baseline_status = _coverage_status(baseline_text, groups)
        guide_status = _coverage_status(guide_text, groups)
    return {
        "marker_id": marker_id,
        "marker_source": "private_artifact_categories",
        "baseline_status": baseline_status,
        "ocr_context_status": guide_status,
        "delta": _status_delta(baseline_status, guide_status),
    }


def _coverage_status(text: str, groups: Any) -> str:
    if not isinstance(text, str) or not text.strip() or not groups:
        return "absent"
    matched = 0
    total = 0
    for group in groups:
        if not isinstance(group, tuple):
            continue
        total += 1
        if any(_contains_term(text, term) for term in group if isinstance(term, str)):
            matched += 1
    if total == 0:
        return "not_checked"
    if matched == total:
        return "present"
    if matched > 0:
        return "partial"
    return "absent"


def _contains_term(text: str, term: str) -> bool:
    return re.search(r"\b" + re.escape(term.lower()) + r"\b", text.lower()) is not None


def _status_delta(baseline_status: str, guide_status: str) -> str:
    if baseline_status == "not_checked" or guide_status == "not_checked":
        return "unavailable"
    before = _status_score(baseline_status)
    after = _status_score(guide_status)
    if after > before:
        return "improved"
    if after < before:
        return "regressed"
    return "unchanged"


def _status_score(status: str) -> float:
    return {"present": 1.0, "partial": 0.5, "absent": 0.0}.get(status, 0.0)


def _coverage_ratio(markers: list[dict[str, str]], field: str) -> float | None:
    checked = [m for m in markers if m.get(field) in {"present", "partial", "absent"}]
    if not checked:
        return None
    return sum(_status_score(m.get(field, "absent")) for m in checked) / len(checked)


def _coverage_bucket(ratio: float | None) -> str:
    if ratio is None:
        return "unknown"
    if ratio >= 0.75:
        return "high"
    if ratio >= 0.40:
        return "medium"
    return "low"


def _delta_from_ratios(before: float | None, after: float | None) -> str:
    if before is None or after is None:
        return "unavailable"
    if after - before >= 0.15:
        return "improved"
    if before - after >= 0.15:
        return "regressed"
    return "unchanged"


def _delta_for_subset(markers: list[dict[str, str]], marker_ids: set[str]) -> str:
    subset = [m for m in markers if m.get("marker_id") in marker_ids]
    return _delta_from_ratios(
        _coverage_ratio(subset, "baseline_status"),
        _coverage_ratio(subset, "ocr_context_status"),
    )


def _count_bucket(count: int) -> str:
    if count <= 0:
        return "unknown"
    if count <= 3:
        return "low"
    if count <= 7:
        return "medium"
    return "high"


def _route_next_step(
    *,
    status: str,
    baseline_coverage: str,
    ocr_coverage: str,
    deck_delta: str,
    visible_delta: str,
    recovered_delta: str,
) -> str:
    if status in {"blocked", "skipped"}:
        return "blocked"
    if deck_delta == "improved" or recovered_delta == "improved":
        return "integrate_deck_specific_coverage_as_advisory_eval"
    if deck_delta == "unchanged" and visible_delta == "improved":
        return "pivot_to_rendered_visible_asset_insertion"
    if deck_delta == "unchanged" and baseline_coverage == "high" and ocr_coverage == "high":
        return "test_on_uncommon_deck"
    if deck_delta == "regressed":
        return "inspect_private_guide_for_content_quality"
    if deck_delta == "unchanged":
        return "test_on_uncommon_deck"
    return "blocked"


def _safe_marker_record(marker: dict[str, str]) -> dict[str, str]:
    marker_id = marker.get("marker_id")
    if marker_id not in _CLOSED_MARKERS:
        marker_id = "ensemble_core_terms"
    baseline_status = _coerce(marker.get("baseline_status"), MARKER_STATUSES, "not_checked")
    guide_status = _coerce(marker.get("ocr_context_status"), MARKER_STATUSES, "not_checked")
    return {
        "marker_id": marker_id,
        "marker_source": _coerce(marker.get("marker_source"), MARKER_SOURCES, "closed_static_ids"),
        "baseline_status": baseline_status,
        "ocr_context_status": guide_status,
        "delta": _coerce(marker.get("delta"), DELTAS, _status_delta(baseline_status, guide_status)),
    }


def _manifest_categories(path: str | None) -> set[str]:
    payload = _read_json(path)
    entries = payload.get("entries") if isinstance(payload, dict) else None
    out: set[str] = set()
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        token = _CATEGORY_MAP.get(entry.get("slide_category"))
        if token:
            out.add(token)
    return out


def _source_categories(text: str | None) -> set[str]:
    if not isinstance(text, str) or not text.strip():
        return set()
    out: set[str] = set()
    for marker_id, spec in _CLOSED_MARKERS.items():
        if marker_id not in _CATEGORY_MAP.values():
            continue
        if _coverage_status(text, spec.get("term_groups", ())) in {"present", "partial"}:
            out.add(marker_id)
    return out


def _visible_categories(path: str | None) -> set[str]:
    payload = _read_json(path)
    assets = payload.get("assets") if isinstance(payload, dict) else None
    out: set[str] = set()
    for asset in assets if isinstance(assets, list) else []:
        if not isinstance(asset, dict):
            continue
        token = asset.get("asset_category")
        if token in _CATEGORY_MAP.values():
            out.add(token)
    return out


def _read_json(path: str | None) -> Any:
    if not _is_private_file(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _read_private_markdown(path: str | None) -> str | None:
    if not _is_private_file(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except Exception:
        return None
    return text if text.strip() else None


def _resolve_176n_guide_path(path: str | None, private_dir: str | None) -> str | None:
    explicit = _safe_private_file(path)
    if explicit:
        return explicit
    if private_dir:
        return _safe_private_file(os.path.join(private_dir, _GENERATED_GUIDE_FILENAME))
    return None


def _resolve_visible_path(path: str | None, private_dir: str | None) -> str | None:
    explicit = _safe_private_file(path)
    if explicit:
        return explicit
    if private_dir:
        return _safe_private_file(os.path.join(private_dir, _VISIBLE_PAYLOAD_FILENAME))
    return None


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


def _safe_label(value: Any) -> str:
    text = str(value or "unknown")
    cleaned = re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")
    return (cleaned or "unknown")[:40]


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def main() -> int:
    summary = run_deck_specific_coverage_eval(
        baseline_guide_path=os.environ.get("BASELINE_GUIDE_MD"),
        guide_176n_path=os.environ.get("REAL_OCR_CONTEXT_GUIDE_MD"),
        private_ocr_dir=os.environ.get("PRIVATE_OCR_DIR"),
        visible_artifact_path=os.environ.get("PRIVATE_VISIBLE_ARTIFACT_JSON"),
        source_label=os.environ.get("SOURCE_LABEL", SOURCE_LABEL_DEFAULT),
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] in {"completed", "degraded"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
