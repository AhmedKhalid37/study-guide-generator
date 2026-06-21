"""Closed uncommon-deck OCR value diagnostic for Slice 176Q.

This module inventories existing private/gitignored artifacts and decides whether an
uncommon-deck OCR-context coverage test can be run without another provider
generation or OCR campaign. It emits closed labels only: no filenames, paths, source
text, OCR text, guide text, prompts, responses, or payloads.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402

ARTIFACT_NAME = "uncommon_deck_ocr_value_diagnostic"
SOURCE_LABEL_DEFAULT = "candidate_1"

STATUSES = frozenset({"completed", "degraded", "blocked", "skipped"})
CANDIDATE_TYPES = frozenset(
    {
        "uncommon_course_deck",
        "private_project_deck",
        "public_common_deck",
        "statquest_like",
        "unknown",
    }
)
CANDIDATE_READINESS = frozenset(
    {
        "ready_existing_artifacts",
        "needs_ocr_artifact",
        "needs_baseline_guide",
        "needs_both",
        "unsuitable",
        "unavailable",
    }
)
MARKER_STATUSES = frozenset({"available", "partial", "unavailable"})
MARKER_SOURCES = frozenset(
    {"private_artifact_categories", "closed_static_ids", "mixed_closed_ids", "unavailable"}
)
NEXT_TEST_READINESS = frozenset(
    {
        "ready_for_uncommon_deck_coverage_eval",
        "ready_for_uncommon_deck_ocr_extraction",
        "ready_for_uncommon_deck_baseline_generation",
        "not_ready",
    }
)
NEXT_STEPS = frozenset(
    {
        "run_uncommon_deck_coverage_eval_existing_artifacts",
        "run_uncommon_deck_ocr_extraction",
        "run_uncommon_deck_baseline_generation",
        "collect_uncommon_deck_fixture",
        "pivot_to_rendered_visible_asset_insertion",
        "stop_ocr_coverage_campaign",
        "blocked",
    }
)

_SOURCE_SUFFIXES = frozenset({"." + "pdf", "." + "ppt", "." + "pptx"})
_GUIDE_SUFFIXES = frozenset({"." + "md", "." + "txt", "." + "pdf"})
_OCR_FILENAMES = frozenset(
    {
        "extracted_content_manifest.json",
        "closed_extraction_summary.json",
        "real_ocr_context_source.md",
    }
)
_VISIBLE_FILENAMES = frozenset({"visible_table_figure_pilot.json"})
_GENERATED_GUIDE_FILENAMES = frozenset(
    {
        "real_ocr_context_generated_guide.md",
        "ocr_context_private_guide.md",
    }
)
_COMMON_TOKENS = frozenset({"statquest", "ensemble"})
_BASELINE_TOKENS = frozenset({"baseline", "reference", "claude", "clean", "latest"})


@dataclass
class _CandidateInventory:
    key: str
    common_hits: int = 0
    private_source_available: bool = False
    private_source_gitignored: bool = False
    private_ocr_artifact_available: bool = False
    private_ocr_artifact_gitignored: bool = False
    private_baseline_guide_available: bool = False
    private_baseline_guide_gitignored: bool = False
    private_generated_guide_available: bool = False
    private_generated_guide_gitignored: bool = False
    private_visible_artifact_available: bool = False
    private_visible_artifact_gitignored: bool = False
    marker_candidate_status: str = "unavailable"
    marker_source: str = "unavailable"
    score: int = 0
    marker_categories: set[str] = field(default_factory=set)


def build_closed_uncommon_deck_ocr_value_summary(
    *,
    status: str,
    source_label: str = SOURCE_LABEL_DEFAULT,
    uncommon_candidate_available: bool = False,
    candidate_type: str = "unknown",
    candidate_readiness: str = "unavailable",
    private_source_available: bool = False,
    private_source_gitignored: bool = False,
    private_ocr_artifact_available: bool = False,
    private_ocr_artifact_gitignored: bool = False,
    private_baseline_guide_available: bool = False,
    private_baseline_guide_gitignored: bool = False,
    private_generated_guide_available: bool = False,
    private_generated_guide_gitignored: bool = False,
    marker_candidate_status: str = "unavailable",
    marker_source: str = "unavailable",
    next_test_readiness: str = "not_ready",
    recommended_next_step: str = "blocked",
) -> dict[str, Any]:
    """Return a committed-safe closed diagnostic summary."""
    return {
        "artifact_name": ARTIFACT_NAME,
        "status": _coerce(status, STATUSES, "blocked"),
        "source_label": _safe_label(source_label),
        "uncommon_candidate_available": bool(uncommon_candidate_available),
        "candidate_type": _coerce(candidate_type, CANDIDATE_TYPES, "unknown"),
        "candidate_readiness": _coerce(candidate_readiness, CANDIDATE_READINESS, "unavailable"),
        "private_source_available": bool(private_source_available),
        "private_source_gitignored": bool(private_source_gitignored),
        "private_ocr_artifact_available": bool(private_ocr_artifact_available),
        "private_ocr_artifact_gitignored": bool(private_ocr_artifact_gitignored),
        "private_baseline_guide_available": bool(private_baseline_guide_available),
        "private_baseline_guide_gitignored": bool(private_baseline_guide_gitignored),
        "private_generated_guide_available": bool(private_generated_guide_available),
        "private_generated_guide_gitignored": bool(private_generated_guide_gitignored),
        "marker_candidate_status": _coerce(marker_candidate_status, MARKER_STATUSES, "unavailable"),
        "marker_source": _coerce(marker_source, MARKER_SOURCES, "unavailable"),
        "provider_call_made": False,
        "generation_rerun": False,
        "ocr_rerun": False,
        "raw_source_committed": False,
        "raw_ocr_committed": False,
        "raw_guide_text_committed": False,
        "raw_table_text_committed": False,
        "raw_caption_text_committed": False,
        "prompts_committed": False,
        "responses_committed": False,
        "provider_payloads_committed": False,
        "next_test_readiness": _coerce(next_test_readiness, NEXT_TEST_READINESS, "not_ready"),
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "blocked"),
    }


def run_uncommon_deck_ocr_value_diagnostic(
    *,
    inventory_roots: list[str] | None = None,
    source_label: str = SOURCE_LABEL_DEFAULT,
) -> dict[str, Any]:
    """Inventory private artifacts and choose a closed next route."""
    candidates = _discover_candidate_inventories(inventory_roots)
    if not candidates:
        return build_closed_uncommon_deck_ocr_value_summary(
            status="blocked",
            source_label=source_label,
            uncommon_candidate_available=False,
            candidate_type="unknown",
            candidate_readiness="unavailable",
            recommended_next_step="collect_uncommon_deck_fixture",
        )

    selected = _select_candidate(candidates)
    candidate_type = _candidate_type(selected)
    readiness = _candidate_readiness(selected, candidate_type)
    next_readiness, next_step = _route_next(readiness)
    uncommon_available = candidate_type in {"uncommon_course_deck", "private_project_deck"}
    status = "completed" if uncommon_available else "degraded"

    return build_closed_uncommon_deck_ocr_value_summary(
        status=status,
        source_label=source_label,
        uncommon_candidate_available=uncommon_available,
        candidate_type=candidate_type,
        candidate_readiness=readiness,
        private_source_available=selected.private_source_available,
        private_source_gitignored=selected.private_source_gitignored,
        private_ocr_artifact_available=selected.private_ocr_artifact_available,
        private_ocr_artifact_gitignored=selected.private_ocr_artifact_gitignored,
        private_baseline_guide_available=selected.private_baseline_guide_available,
        private_baseline_guide_gitignored=selected.private_baseline_guide_gitignored,
        private_generated_guide_available=selected.private_generated_guide_available,
        private_generated_guide_gitignored=selected.private_generated_guide_gitignored,
        marker_candidate_status=selected.marker_candidate_status,
        marker_source=selected.marker_source,
        next_test_readiness=next_readiness,
        recommended_next_step=next_step,
    )


def _discover_candidate_inventories(roots: list[str] | None) -> list[_CandidateInventory]:
    inventories: dict[str, _CandidateInventory] = {}
    for path in _private_files_from_roots(roots):
        key = _candidate_key(path)
        inv = inventories.setdefault(key, _CandidateInventory(key=key))
        _absorb_private_file(inv, path)
    _finalize_candidates(inventories.values())
    return list(inventories.values())


def _private_files_from_roots(roots: list[str] | None) -> list[Path]:
    selected_roots = roots or [os.getcwd()]
    out: list[Path] = []
    for root in selected_roots:
        if not isinstance(root, str) or not root:
            continue
        root_path = Path(root)
        if not root_path.exists():
            continue
        if root_path.is_file():
            if is_private_artifact_dir(root_path.parent):
                out.append(root_path)
            continue
        for walk_root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", ".venv", "__pycache__"}]
            if not is_private_artifact_dir(walk_root):
                continue
            for name in files:
                path = Path(walk_root) / name
                if is_private_artifact_dir(path.parent):
                    out.append(path)
    return out


def _candidate_key(path: Path) -> str:
    tokens = _path_tokens(path)
    if _COMMON_TOKENS & tokens:
        return "common"
    return "uncommon"


def _absorb_private_file(inv: _CandidateInventory, path: Path) -> None:
    tokens = _path_tokens(path)
    suffix = path.suffix.lower()
    name = path.name.lower()
    gitignored = is_private_artifact_dir(path.parent)
    if _COMMON_TOKENS & tokens:
        inv.common_hits += 1
    if suffix in _SOURCE_SUFFIXES:
        inv.private_source_available = True
        inv.private_source_gitignored = inv.private_source_gitignored or gitignored
        inv.score += 3
    if name in _OCR_FILENAMES:
        inv.private_ocr_artifact_available = True
        inv.private_ocr_artifact_gitignored = inv.private_ocr_artifact_gitignored or gitignored
        inv.score += 4
        inv.marker_categories |= _closed_marker_categories(path)
    if name in _VISIBLE_FILENAMES:
        inv.private_visible_artifact_available = True
        inv.private_visible_artifact_gitignored = inv.private_visible_artifact_gitignored or gitignored
        inv.score += 1
        inv.marker_categories |= _closed_visible_categories(path)
    if _is_generated_guide(path):
        inv.private_generated_guide_available = True
        inv.private_generated_guide_gitignored = inv.private_generated_guide_gitignored or gitignored
        inv.score += 2
    elif _is_baseline_guide(path):
        inv.private_baseline_guide_available = True
        inv.private_baseline_guide_gitignored = inv.private_baseline_guide_gitignored or gitignored
        inv.score += 2


def _finalize_candidates(candidates: Any) -> None:
    for inv in candidates:
        if inv.marker_categories and inv.private_ocr_artifact_available:
            inv.marker_candidate_status = "available"
            inv.marker_source = "private_artifact_categories"
        elif inv.private_ocr_artifact_available or inv.private_visible_artifact_available:
            inv.marker_candidate_status = "partial"
            inv.marker_source = "mixed_closed_ids"
        else:
            inv.marker_candidate_status = "unavailable"
            inv.marker_source = "unavailable"


def _select_candidate(candidates: list[_CandidateInventory]) -> _CandidateInventory:
    uncommon = [c for c in candidates if _candidate_type(c) in {"uncommon_course_deck", "private_project_deck"}]
    pool = uncommon or candidates
    return sorted(pool, key=lambda c: (c.score, c.private_source_available, c.private_ocr_artifact_available), reverse=True)[0]


def _candidate_type(candidate: _CandidateInventory) -> str:
    if candidate.common_hits > 0 and candidate.key == "common":
        return "statquest_like"
    if candidate.private_source_available or candidate.private_baseline_guide_available:
        return "uncommon_course_deck"
    return "unknown"


def _candidate_readiness(candidate: _CandidateInventory, candidate_type: str) -> str:
    if candidate_type in {"statquest_like", "public_common_deck"}:
        return "unsuitable"
    if candidate_type == "unknown":
        return "unavailable"
    has_source = candidate.private_source_available
    has_ocr = candidate.private_ocr_artifact_available
    has_baseline = candidate.private_baseline_guide_available
    has_generated = candidate.private_generated_guide_available
    has_markers = candidate.marker_candidate_status == "available"
    if has_source and has_ocr and has_baseline and has_generated and has_markers:
        return "ready_existing_artifacts"
    if has_source and not has_ocr:
        return "needs_ocr_artifact"
    if has_ocr and not has_baseline:
        return "needs_baseline_guide"
    if has_source and (not has_ocr or not has_baseline):
        return "needs_both"
    return "unavailable"


def _route_next(readiness: str) -> tuple[str, str]:
    if readiness == "ready_existing_artifacts":
        return "ready_for_uncommon_deck_coverage_eval", "run_uncommon_deck_coverage_eval_existing_artifacts"
    if readiness == "needs_ocr_artifact":
        return "ready_for_uncommon_deck_ocr_extraction", "run_uncommon_deck_ocr_extraction"
    if readiness == "needs_baseline_guide":
        return "ready_for_uncommon_deck_baseline_generation", "run_uncommon_deck_baseline_generation"
    if readiness == "unsuitable":
        return "not_ready", "pivot_to_rendered_visible_asset_insertion"
    if readiness == "unavailable":
        return "not_ready", "collect_uncommon_deck_fixture"
    return "not_ready", "collect_uncommon_deck_fixture"


def _is_generated_guide(path: Path) -> bool:
    name = path.name.lower()
    tokens = _path_tokens(path)
    if name in _GENERATED_GUIDE_FILENAMES:
        return True
    return path.suffix.lower() in _GUIDE_SUFFIXES and "guideforge" in tokens


def _is_baseline_guide(path: Path) -> bool:
    tokens = _path_tokens(path)
    return path.suffix.lower() in _GUIDE_SUFFIXES and bool(tokens & _BASELINE_TOKENS)


def _closed_marker_categories(path: Path) -> set[str]:
    payload = _read_json(path)
    entries = payload.get("entries") if isinstance(payload, dict) else None
    out: set[str] = set()
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        token = _safe_label(entry.get("slide_category"))
        if token:
            out.add(token)
    return out


def _closed_visible_categories(path: Path) -> set[str]:
    payload = _read_json(path)
    assets = payload.get("assets") if isinstance(payload, dict) else None
    out: set[str] = set()
    for asset in assets if isinstance(assets, list) else []:
        if not isinstance(asset, dict):
            continue
        token = _safe_label(asset.get("asset_category"))
        if token:
            out.add(token)
    return out


def _read_json(path: Path) -> Any:
    if not is_private_artifact_dir(path.parent):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _path_tokens(path: Path) -> set[str]:
    text = " ".join(part.lower() for part in path.parts[-6:])
    return {t for t in re.split(r"[^a-z0-9]+", text) if t}


def _safe_label(value: Any) -> str:
    text = str(value or "unknown")
    cleaned = re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")
    return (cleaned or "unknown")[:40]


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def _env_roots() -> list[str] | None:
    raw = os.environ.get("PRIVATE_INVENTORY_ROOTS")
    if not raw:
        return None
    roots = [p for p in raw.split(os.pathsep) if p]
    return roots or None


def main() -> int:
    summary = run_uncommon_deck_ocr_value_diagnostic(
        inventory_roots=_env_roots(),
        source_label=os.environ.get("SOURCE_LABEL", SOURCE_LABEL_DEFAULT),
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] in {"completed", "degraded"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
