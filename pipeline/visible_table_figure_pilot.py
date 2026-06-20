"""Visible table/figure pilot over the private 176I OCR artifact (Slice 176K).

Slice 176I ran the proven local structured OCR producer on real content slides and
wrote a **private, gitignored** extracted-content artifact; Slice 176J tried to parse
**raw Gini class-count input cells** out of that artifact and found the representative
Gini slide is a per-split **answer summary**, not a raw class-count grid — so it routed
the project away from numerics to ``pivot_to_visible_table_pilot``. This module is that
pilot: the **first product-facing downstream consumer** of the private 176I artifact.

What this module IS:
  * a minimal selector that picks a **very small** set (max 3) of high-value,
    student-visible assets (proximity matrix, patient-dataset table, optional
    decision-tree/split diagram) out of the already-extracted private OCR content;
  * a private packager that writes reconstructed table markdown / structured table
    JSON / caption-context / a placement hint **only** into a confirmed-private
    (gitignored / temp) artifact directory, and emits a **committed-safe closed
    summary** for a later off-by-default private guide-preview pilot.

What this module is **NOT** (do not grow it into any of these here):
  * a numeric parser, numeric-recompute wiring, a broad table engine, guide-generation
    wiring, frontend/API integration, full ingestion rollout, a Layer-2 judge, repair,
    cloud OCR, or provider/model generation. ``judge_ready=false``;
    ``repair_ready=false``.

Anti-laundering / privacy rules (non-negotiable):
  * Visible table/figure assets are **display / study assets only**. They do **not**
    prove numeric correctness. They are never fed into recompute, never marked
    ``verifier_input``, and ``numeric_recompute_claimed`` is a hardwired ``False``. An
    asset that happens to carry a computed-answer table is ``numeric_verification_role
    = display_only`` at most — never a verifier input.
  * Raw reconstructed tables, OCR captions, rendered crops, source PDFs, model
    files/caches, and private paths are **never** committed. They live only inside the
    private artifact directory. The committed summary carries closed tokens / counts /
    bools only — the ``*_committed`` flags are hardwired ``False`` and no raw-text /
    path / size argument is accepted by the summary builder.
  * If the private artifact directory is missing or **not** confirmed private, the
    pilot **blocks** instead of writing anything.

The core API (:func:`select_candidate_descriptors`, :func:`build_closed_pilot_summary`)
is pure, offline, and consumes only **closed structural descriptors** (category token +
table/figure shape counts) — it reads no files and carries no private path. A thin
env-driven :func:`main` reads the private 176I manifest (``PRIVATE_OCR_DIR`` only; never
a committed path), selects assets, writes the private pilot payload, and prints the
**closed** summary.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402

ARTIFACT_NAME = "visible_table_figure_pilot_private_ocr"
SOURCE_LABEL_DEFAULT = "ensemble"
MAX_ASSETS_ALLOWED = 3

# ── Closed vocabularies (this module owns what it emits) ─────────────────────
STATUSES = frozenset({"completed", "degraded", "blocked", "skipped"})
ASSET_KINDS = frozenset({"table", "figure", "diagram"})
SUMMARY_ASSET_KINDS = frozenset({"table", "figure", "diagram", "mixed", "none"})
ASSET_CATEGORIES = frozenset(
    {
        "proximity_matrix",
        "patient_dataset_table",
        "decision_tree_or_split_diagram",
        "gini_or_leaf_count_answer_summary",
        "weighted_frequency_or_total_error",
        "none",
    }
)
SOURCE_ORIGINS = frozenset(
    {"private_ocr_artifact", "private_rendered_slide", "mixed_private_artifact", "none"}
)
DISPLAY_ROLES = frozenset(
    {"student_visible_reference", "explanation_support", "numeric_verification"}
)
ASSET_STATUSES = frozenset({"ready", "partial", "rejected"})
SLOT_STATUSES = frozenset({"ready", "partial", "unavailable", "not_attempted"})
GUIDE_READINESS = frozenset(
    {
        "ready_for_off_by_default_private_pilot",
        "needs_caption_policy",
        "needs_placement_policy",
        "needs_cleanup",
        "blocked",
    }
)
NUMERIC_ROLES = frozenset({"none", "display_only", "verifier_input"})
WARNINGS = frozenset(
    {
        "none",
        "private_artifact_missing",
        "unsafe_private_artifact_path",
        "no_visible_assets",
        "selection_capped_at_max",
        "diagram_recovered_as_table",
        "figure_unavailable",
        "extraction_quality_partial",
        "private_write_refused",
        "private_write_failed",
    }
)
BLOCKED_BY = frozenset(
    {
        "none",
        "private_artifact_missing",
        "no_visible_assets",
        "unsafe_private_artifact_path",
        "extraction_quality",
        "scope_too_large",
    }
)
NEXT_STEPS = frozenset(
    {
        "wire_visible_assets_into_private_guide_preview",
        "add_caption_policy",
        "add_placement_policy",
        "expand_visible_asset_selection",
        "use_private_extracted_content_for_guide_pilot",
        "blocked",
    }
)

# Manifest category -> closed summary category token. Title/intro categories never
# appear here (176I already excludes them).
_CATEGORY_MAP = {
    "ensemble_proximity_matrix": "proximity_matrix",
    "ensemble_patient_dataset_table": "patient_dataset_table",
    "ensemble_decision_tree_or_split_diagram": "decision_tree_or_split_diagram",
    "ensemble_gini_or_leaf_count": "gini_or_leaf_count_answer_summary",
    "ensemble_weighted_frequency_or_total_error": "weighted_frequency_or_total_error",
}

# High-value student-visible asset categories, in selection priority. Capped to
# MAX_ASSETS_ALLOWED. The Gini/weighted answer-summary categories are deliberately NOT
# in the priority set (176J showed Gini is an answer summary, not a reference table).
_PRIORITY = (
    "proximity_matrix",
    "patient_dataset_table",
    "decision_tree_or_split_diagram",
)

# Per-category presentation intent (display assets only; never numeric_verification).
_KIND_BY_CATEGORY = {
    "proximity_matrix": "table",
    "patient_dataset_table": "table",
    "decision_tree_or_split_diagram": "diagram",
    "gini_or_leaf_count_answer_summary": "table",
    "weighted_frequency_or_total_error": "table",
}
_ROLE_BY_CATEGORY = {
    "proximity_matrix": "student_visible_reference",
    "patient_dataset_table": "student_visible_reference",
    "decision_tree_or_split_diagram": "explanation_support",
    "gini_or_leaf_count_answer_summary": "student_visible_reference",
    "weighted_frequency_or_total_error": "student_visible_reference",
}
# Numeric-bearing display tables (numbers are shown to students, never recomputed).
_NUMERIC_DISPLAY_CATEGORIES = frozenset(
    {
        "proximity_matrix",
        "patient_dataset_table",
        "gini_or_leaf_count_answer_summary",
        "weighted_frequency_or_total_error",
    }
)

_MIN_TABLE_ROWS = 2
_MIN_TABLE_COLS = 2


# ── Closed structural descriptor from one manifest entry (no raw text) ───────


def descriptor_from_entry(entry: Any) -> dict[str, Any] | None:
    """Build a closed structural descriptor from one 176I manifest entry.

    Reads only ``slide_category`` and the closed ``signals`` shape counts (table
    rows/cols, figure/caption/text-block counts) — never ``raw_layout_html`` or any
    cell text. Returns ``None`` for entries outside the known content categories.
    Pure / total; never raises.
    """
    if not isinstance(entry, dict):
        return None
    raw_category = entry.get("slide_category")
    category = _CATEGORY_MAP.get(raw_category) if isinstance(raw_category, str) else None
    if category is None:
        return None
    signals = entry.get("signals") if isinstance(entry.get("signals"), dict) else {}
    rows = _safe_count(signals.get("max_table_rows"))
    cols = _safe_count(signals.get("max_table_cols"))
    has_table = bool(signals.get("has_table")) or (rows >= 1 and cols >= 1)
    has_figure = _safe_count(signals.get("figure_or_diagram_count")) > 0
    caption_present = (
        _safe_count(signals.get("caption_count")) > 0
        or _safe_count(signals.get("text_block_count")) > 0
    )
    dense_ok = has_table and rows >= _MIN_TABLE_ROWS and cols >= _MIN_TABLE_COLS
    return {
        "asset_category": category,
        "rows": rows,
        "cols": cols,
        "has_table": has_table,
        "has_figure": has_figure,
        "caption_present": caption_present,
        "dense_ok": dense_ok,
    }


def _classify_descriptor(desc: dict[str, Any]) -> dict[str, Any]:
    """Attach closed kind / role / status to a structural descriptor (display-only)."""
    category = desc["asset_category"]
    kind = _KIND_BY_CATEGORY.get(category, "table")
    display_role = _ROLE_BY_CATEGORY.get(category, "student_visible_reference")
    if kind == "diagram":
        # 176I recovered the decision-tree slide as a table grid, not a true figure
        # image — honest status is partial (structure captured, not a rendered figure).
        asset_status = "partial"
    elif desc["dense_ok"]:
        asset_status = "ready"
    elif desc["has_table"]:
        asset_status = "partial"
    else:
        asset_status = "rejected"
    return {
        "asset_category": category,
        "asset_kind": kind,
        "source_origin": "private_ocr_artifact",
        # Display-only invariant: never numeric_verification in this slice.
        "display_role": display_role,
        "asset_status": asset_status,
        "raw_content_committed": False,
        "image_bytes_committed": False,
        "private_path_committed": False,
        # internal-only hints (dropped from the committed record by _asset_record)
        "_caption_present": bool(desc.get("caption_present")),
        "_has_figure": bool(desc.get("has_figure")),
    }


# ── Selection (pure; closed descriptors only) ────────────────────────────────


def select_candidate_descriptors(
    entries: Any, *, max_assets: int = MAX_ASSETS_ALLOWED
) -> tuple[list[dict[str, Any]], list[str]]:
    """Select up to ``max_assets`` high-value student-visible assets (priority order).

    Consumes a list of 176I manifest entries (or pre-built structural descriptors),
    keeps only the priority content categories, and caps the result. Returns
    ``(classified_descriptors, warnings)``. Pure / total; never raises.
    """
    cap = max(1, min(int(max_assets) if isinstance(max_assets, int) else MAX_ASSETS_ALLOWED, MAX_ASSETS_ALLOWED))
    warnings: list[str] = []
    by_category: dict[str, dict[str, Any]] = {}
    for entry in entries if isinstance(entries, list) else []:
        desc = entry if _looks_like_descriptor(entry) else descriptor_from_entry(entry)
        if not desc:
            continue
        category = desc.get("asset_category")
        if category in _PRIORITY and category not in by_category:
            by_category[category] = desc
    ordered = [by_category[c] for c in _PRIORITY if c in by_category]
    if len(ordered) > cap:
        ordered = ordered[:cap]
        warnings.append("selection_capped_at_max")
    classified = [_classify_descriptor(d) for d in ordered]
    if any(d["asset_kind"] == "diagram" for d in classified):
        warnings.append("diagram_recovered_as_table")
    if not any(d.get("_has_figure") for d in classified):
        warnings.append("figure_unavailable")
    if any(d["asset_status"] == "partial" and d["asset_kind"] != "diagram" for d in classified):
        warnings.append("extraction_quality_partial")
    return classified, warnings


def _looks_like_descriptor(value: Any) -> bool:
    return isinstance(value, dict) and "asset_category" in value and "has_table" in value


# ── Closed summary builder (committed-safe; no raw content) ──────────────────


def build_closed_pilot_summary(
    *,
    status: str,
    source_label: str = SOURCE_LABEL_DEFAULT,
    selected: list[dict[str, Any]] | None = None,
    private_artifact_available: bool,
    private_artifact_gitignored: bool,
    private_visible_artifact_written: bool = False,
    private_visible_artifact_gitignored: bool = False,
    blocked_by: str = "none",
    recommended_next_step: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble the committed-safe closed pilot summary. All fields coerced to closed sets.

    Raw OCR / table / caption text, rendered images, source PDFs, and model
    files/caches are structurally excluded (the ``*_committed`` flags are hardwired
    ``False`` and no text/path/size argument is accepted). ``numeric_recompute_claimed``
    is hardwired ``False`` and no asset display_role may be ``numeric_verification``.
    """
    assets = [a for a in (selected or []) if isinstance(a, dict)]
    asset_records = [_asset_record(a) for a in assets]
    kinds = {a["asset_kind"] for a in asset_records}
    categories = [a["asset_category"] for a in asset_records]

    if not asset_records:
        kinds_token = "none"
    elif len(kinds) == 1:
        kinds_token = next(iter(kinds))
    else:
        kinds_token = "mixed"

    table_assets = [a for a in asset_records if a["asset_kind"] == "table"]
    figure_assets = [a for a in asset_records if a["asset_kind"] in {"figure", "diagram"}]

    table_asset_status = _slot_status(table_assets)
    figure_asset_status = _slot_status(figure_assets)
    caption_status = _caption_slot_status(assets)

    numeric_role = (
        "display_only"
        if any(a["asset_category"] in _NUMERIC_DISPLAY_CATEGORIES for a in asset_records)
        else "none"
    )

    coerced_status = _coerce(status, STATUSES, "blocked")
    if coerced_status in {"blocked", "skipped"}:
        guide_readiness = "blocked"
    elif table_asset_status == "ready" and caption_status in {"ready", "partial"}:
        guide_readiness = "ready_for_off_by_default_private_pilot"
    elif table_asset_status in {"ready", "partial"}:
        guide_readiness = "needs_placement_policy"
    else:
        guide_readiness = "needs_cleanup"

    if recommended_next_step is None:
        if coerced_status in {"blocked", "skipped"}:
            recommended_next_step = "blocked"
        elif guide_readiness == "ready_for_off_by_default_private_pilot":
            recommended_next_step = "wire_visible_assets_into_private_guide_preview"
        else:
            recommended_next_step = "add_placement_policy"

    return {
        "artifact_name": ARTIFACT_NAME,
        "status": coerced_status,
        "source_label": _safe_label(source_label),
        "private_artifact_available": bool(private_artifact_available),
        "private_artifact_gitignored": bool(private_artifact_gitignored),
        "selected_assets_count": len(asset_records),
        "max_assets_allowed": MAX_ASSETS_ALLOWED,
        "selected_asset_kinds": _coerce(kinds_token, SUMMARY_ASSET_KINDS, "none"),
        "selected_asset_categories": _safe_category_list(categories),
        "private_visible_artifact_written": bool(private_visible_artifact_written),
        "private_visible_artifact_gitignored": bool(private_visible_artifact_gitignored),
        "raw_ocr_committed": False,
        "raw_table_text_committed": False,
        "raw_caption_text_committed": False,
        "rendered_images_committed": False,
        "source_pdf_committed": False,
        "model_files_committed": False,
        "model_cache_committed": False,
        "cloud_ocr_used": False,
        "table_asset_status": _coerce(table_asset_status, SLOT_STATUSES, "not_attempted"),
        "figure_asset_status": _coerce(figure_asset_status, SLOT_STATUSES, "not_attempted"),
        "caption_or_context_status": _coerce(caption_status, SLOT_STATUSES, "not_attempted"),
        "guide_insertion_readiness": _coerce(guide_readiness, GUIDE_READINESS, "blocked"),
        "numeric_verification_role": _coerce(numeric_role, NUMERIC_ROLES, "none"),
        "numeric_recompute_claimed": False,
        "warnings": _safe_warnings(warnings),
        "blocked_by": _coerce(blocked_by, BLOCKED_BY, "none"),
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "blocked"),
        "assets": asset_records,
    }


def _asset_record(asset: dict[str, Any]) -> dict[str, Any]:
    role = asset.get("display_role")
    # Display-only invariant: refuse a numeric_verification role this slice.
    if role == "numeric_verification" or role not in DISPLAY_ROLES:
        role = "student_visible_reference"
    return {
        "asset_category": _coerce(asset.get("asset_category"), ASSET_CATEGORIES, "none"),
        "asset_kind": _coerce(asset.get("asset_kind"), ASSET_KINDS, "table"),
        "source_origin": _coerce(asset.get("source_origin"), SOURCE_ORIGINS, "private_ocr_artifact"),
        "display_role": role,
        "asset_status": _coerce(asset.get("asset_status"), ASSET_STATUSES, "rejected"),
        "raw_content_committed": False,
        "image_bytes_committed": False,
        "private_path_committed": False,
    }


def _slot_status(assets: list[dict[str, Any]]) -> str:
    if not assets:
        return "unavailable"
    statuses = {a["asset_status"] for a in assets}
    if statuses == {"ready"}:
        return "ready"
    if "ready" in statuses or "partial" in statuses:
        return "partial"
    return "unavailable"


def _caption_slot_status(assets: list[dict[str, Any]]) -> str:
    if not assets:
        return "not_attempted"
    present = sum(1 for a in assets if a.get("_caption_present"))
    if present == len(assets):
        return "ready"
    if present > 0:
        return "partial"
    return "unavailable"


# ── Private payload (raw content; written ONLY to the private artifact dir) ───


def extract_layout_tables_from_html(html: Any) -> list[list[list[str]]]:
    """Extract tables as grids of **tag-stripped** cell strings from layout HTML.

    Used only by :func:`main` against the private artifact; the stripped strings are
    written into the private pilot payload and never committed. Pure / total.
    """
    if not isinstance(html, str) or not html:
        return []
    grids: list[list[list[str]]] = []
    for table in re.findall(r"<table\b.*?</table>", html, flags=re.I | re.S):
        rows: list[list[str]] = []
        for tr in re.findall(r"<tr\b.*?</tr>", table, flags=re.I | re.S):
            cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", tr, flags=re.I | re.S)
            rows.append([_strip_tags(c) for c in cells])
        if rows:
            grids.append(rows)
    return grids


def _strip_tags(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment or "")).strip()


def _grid_to_markdown(grid: list[list[str]]) -> str:
    """Render one stripped cell grid as a markdown table (private artifact only)."""
    if not grid:
        return ""
    width = max(len(r) for r in grid)
    norm = [[(r[c] if c < len(r) else "") for c in range(width)] for r in grid]
    header = norm[0]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for row in norm[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_private_asset_payload(entry: dict[str, Any], category_token: str) -> dict[str, Any]:
    """Build the RAW per-asset pilot payload (markdown / JSON / caption / placement).

    The return value carries reconstructed table content and is written **only** into
    the private artifact directory — it must never be committed or printed. Pure / total.
    """
    html = entry.get("raw_layout_html") if isinstance(entry, dict) else None
    grids = extract_layout_tables_from_html(html)
    normalized = entry.get("normalized") if isinstance(entry, dict) else None
    return {
        "asset_category": category_token,
        "table_markdown": [_grid_to_markdown(g) for g in grids],
        "table_json": grids,
        "normalized_context": normalized,
        # closed placement hint for a future off-by-default private guide preview
        "placement_hint": f"private_preview_after:{category_token}",
        "display_role": _ROLE_BY_CATEGORY.get(category_token, "student_visible_reference"),
        "numeric_verification_role": "display_only"
        if category_token in _NUMERIC_DISPLAY_CATEGORIES
        else "none",
    }


# ── Helpers ──────────────────────────────────────────────────────────────────


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def _safe_label(value: Any) -> str:
    text = str(value or "unknown")
    cleaned = re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")
    return (cleaned or "unknown")[:40]


def _safe_count(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _safe_category_list(categories: Any) -> list[str]:
    out: list[str] = []
    for c in categories if isinstance(categories, list) else []:
        token = c if c in ASSET_CATEGORIES else "none"
        out.append(token)
    return out or ["none"]


def _safe_warnings(warnings: Any) -> list[str]:
    if not isinstance(warnings, list):
        return ["none"]
    seen: list[str] = []
    for w in warnings:
        if w in WARNINGS and w not in seen and w != "none":
            seen.append(w)
    return seen or ["none"]


# ── Env-driven private runner (no committed path; closed output only) ────────


def _public(summary: dict[str, Any]) -> dict[str, Any]:
    """The committed-safe view: the closed summary with the per-asset records inline."""
    return summary


def main() -> int:
    """Run the pilot against the private 176I artifact; print the closed summary.

    Env:
      PRIVATE_OCR_DIR   gitignored/temp dir holding 176I's manifest (required, private)
      SOURCE_LABEL      closed source label (default "ensemble")
      MAX_PILOT_ASSETS  cap on selected assets (default/ceiling 3)
    """
    private_dir = os.environ.get("PRIVATE_OCR_DIR")
    source_label = os.environ.get("SOURCE_LABEL", SOURCE_LABEL_DEFAULT)
    try:
        max_assets = int(os.environ.get("MAX_PILOT_ASSETS", str(MAX_ASSETS_ALLOWED)))
    except ValueError:
        max_assets = MAX_ASSETS_ALLOWED

    # No private dir at all -> honest hard blocker, nothing written.
    if not private_dir:
        summary = build_closed_pilot_summary(
            status="blocked",
            source_label=source_label,
            selected=[],
            private_artifact_available=False,
            private_artifact_gitignored=False,
            blocked_by="private_artifact_missing",
            warnings=["private_artifact_missing"],
        )
        print(json.dumps(summary, indent=2))
        return 2

    gitignored = is_private_artifact_dir(private_dir)
    if not gitignored:
        summary = build_closed_pilot_summary(
            status="blocked",
            source_label=source_label,
            selected=[],
            private_artifact_available=False,
            private_artifact_gitignored=False,
            blocked_by="unsafe_private_artifact_path",
            warnings=["unsafe_private_artifact_path"],
        )
        print(json.dumps(summary, indent=2))
        return 2

    manifest_path = os.path.join(private_dir, "extracted_content_manifest.json")
    available = os.path.isfile(manifest_path)
    entries: list[Any] = []
    if available:
        try:
            with open(manifest_path, encoding="utf-8") as fh:
                manifest = json.load(fh)
            entries = manifest.get("entries", []) if isinstance(manifest, dict) else []
        except Exception:
            available = False

    if not available:
        summary = build_closed_pilot_summary(
            status="blocked",
            source_label=source_label,
            selected=[],
            private_artifact_available=False,
            private_artifact_gitignored=gitignored,
            blocked_by="private_artifact_missing",
            warnings=["private_artifact_missing"],
        )
        print(json.dumps(summary, indent=2))
        return 2

    selected, warnings = select_candidate_descriptors(entries, max_assets=max_assets)

    if not selected:
        summary = build_closed_pilot_summary(
            status="blocked",
            source_label=source_label,
            selected=[],
            private_artifact_available=True,
            private_artifact_gitignored=gitignored,
            blocked_by="no_visible_assets",
            warnings=["no_visible_assets"],
        )
        print(json.dumps(summary, indent=2))
        return 0

    # Build the RAW private pilot payload for each selected asset and write it ONLY to
    # the private dir. The raw payload never enters the committed summary.
    by_category_entry: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        token = _CATEGORY_MAP.get(entry.get("slide_category"))
        if token and token not in by_category_entry:
            by_category_entry[token] = entry

    private_payloads = []
    for desc in selected:
        token = desc["asset_category"]
        entry = by_category_entry.get(token)
        if entry is not None:
            private_payloads.append(build_private_asset_payload(entry, token))

    private_written = False
    if is_private_artifact_dir(private_dir):
        try:
            pilot_path = os.path.join(private_dir, "visible_table_figure_pilot.json")
            with open(pilot_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {"source_label": source_label, "assets": private_payloads},
                    fh,
                    ensure_ascii=False,
                )
            private_written = bool(private_payloads)
        except Exception:
            warnings.append("private_write_failed")
    else:
        warnings.append("private_write_refused")

    summary = build_closed_pilot_summary(
        status="completed" if private_written else "degraded",
        source_label=source_label,
        selected=selected,
        private_artifact_available=True,
        private_artifact_gitignored=gitignored,
        private_visible_artifact_written=private_written,
        private_visible_artifact_gitignored=is_private_artifact_dir(private_dir),
        warnings=warnings,
    )
    # Print ONLY the closed summary (closed tokens / counts / bools). The raw private
    # payload is never printed or committed.
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
