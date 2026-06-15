"""Ask Guide **coverage grounding** builder (Slice 98).

Full Material Coverage capstone for Ask Your Guide. Slices 82–97 taught the
generated guide and the JobDetails final panel about material coverage — which
pages/slides were included vs. excluded, what source coverage exists, which
non-table visuals were planned, which table-like candidates exist and their
reconstruction policy, what missing-material guidance applies, and the Slice 96
guide-quality-v2 signal checks.

Slice 98 makes **Ask Your Guide** aware of the same safe coverage signals so a
user can ask meta questions ("were any pages excluded?", "did the guide include
all figures?", "were tables reconstructed?", "can I trust the coverage?") and get
honest, closed answers. This builder turns the already-sanitized exact-name
artifacts plus the job's safe page-selection fields into a short, leak-free
grounding block that is injected into the model-facing Ask context preamble.

Product goal
------------
``When a user asks questions in Ask Guide, the answer should be grounded not only
in clean.md chunks, but also in sanitized material coverage signals: included /
excluded pages, source coverage gaps, planned / inserted figures, table candidate
/ policy status, missing-material notes, and guide quality v2 checks.``

This grounding is **meta-context**, not course-content evidence. It tells the
local answer model what is true *about the coverage* (counts/statuses only). Course
content must still come from the retrieved guide/source chunks and their citations;
the model must never answer factual course questions from coverage signals alone,
and must never invent figure or table details.

Scope (Slice 98 = Ask grounding only)
-------------------------------------
Pure derivation only. It does NOT change extraction/OCR, inspect PDFs/images, read
image bytes, reconstruct a table, extract table text, render, export, change figure
insertion semantics, change material page selection, change visual-manifest
filtering, change provider/model selection, add UI, or call a provider / model /
VLM / Chandra / Mistral / Gemini / cloud. It reads ONLY the already-sanitized
page-selection fields and artifact dicts and returns a sanitized grounding dict
whose ``grounding_text`` is safe to inject into the Ask Guide model context.

Purity & safety
---------------
stdlib-only (imports nothing from ``pipeline`` and no provider/model/OCR/renderer/
FastAPI/frontend module). The grounding emits **only** closed tokens, ints,
``None``, bools, fixed instruction strings built from those, and a safe generated
``item_id`` of the fixed shape ``ask_grounding_NNNN``. No filename, path, source
title, caption, document / OCR / table text, image ref, asset ref / asset id, image
byte, base64 / data URI, provider payload, token, URL, argv, socket path, model
path, or raw exception string can survive into it: input fields are read for
*decisions only* and never echoed. Never raises; any malformed input degrades to a
safe ``skipped`` / empty grounding.
"""
from __future__ import annotations

from typing import Any

GROUNDING_VERSION = 1
GROUNDING_KIND = "ask_coverage_grounding"

# --- Closed grounding-signal / item kinds ------------------------------------
KIND_MATERIAL_SELECTION = "material_selection"
KIND_SOURCE_COVERAGE = "source_coverage"
KIND_VISUAL_COVERAGE = "visual_coverage"
KIND_TABLE_POLICY = "table_policy"
KIND_MISSING_MATERIAL = "missing_material"
KIND_GUIDE_QUALITY = "guide_quality"

# Deterministic emission order of the closed signal items.
_SIGNAL_ORDER = (
    KIND_MATERIAL_SELECTION,
    KIND_SOURCE_COVERAGE,
    KIND_VISUAL_COVERAGE,
    KIND_TABLE_POLICY,
    KIND_MISSING_MATERIAL,
    KIND_GUIDE_QUALITY,
)

# --- Closed warning vocabulary (this module owns what it emits) --------------
ALL_INPUTS_MISSING = "all_inputs_missing"
JOB_REQUEST_MALFORMED = "job_request_malformed"
SOURCE_COVERAGE_MALFORMED = "source_coverage_malformed"
VISUAL_PLAN_MALFORMED = "visual_plan_malformed"
TABLE_MANIFEST_MALFORMED = "table_manifest_malformed"
TABLE_POLICY_MALFORMED = "table_policy_malformed"
GUIDE_QUALITY_MALFORMED = "guide_quality_malformed"
MAX_ITEMS_APPLIED = "max_items_applied"

# Deterministic emitted warning ordering (closed tokens only, never raw text).
WARNING_ORDER = [
    ALL_INPUTS_MISSING,
    JOB_REQUEST_MALFORMED,
    SOURCE_COVERAGE_MALFORMED,
    VISUAL_PLAN_MALFORMED,
    TABLE_MANIFEST_MALFORMED,
    TABLE_POLICY_MALFORMED,
    GUIDE_QUALITY_MALFORMED,
    MAX_ITEMS_APPLIED,
]

# Safe generated item-id shape.
ITEM_ID_PREFIX = "ask_grounding_"

# Defensive ceiling — guards a pathological ``max_items``, NOT a product cap. The
# real signal count is bounded by ``len(_SIGNAL_ORDER)``.
_GROUNDING_ITEM_HARD_CEILING = 500

# Static, leak-free framing lines that open/close every non-empty grounding block.
_HEADER_LINES = (
    "Material coverage summary (meta-context about how this guide was built; "
    "it is not course content):",
    "- Use these coverage facts only to answer questions about coverage, "
    "figures, tables, and completeness. For course content, rely on the retrieved "
    "guide and source chunks and cite them as usual.",
)
_CLOSING_LINES = (
    "- These coverage checks are deterministic signal checks over safe counts, "
    "not semantic proof that the guide is complete or correct.",
    "- Do not invent figure or table details. If a visual or table is "
    "unavailable, state that it is unavailable rather than guessing.",
)

# Closed per-item instruction per active grounding signal (never source content).
_SIGNAL_INSTRUCTION = {
    KIND_MATERIAL_SELECTION: (
        "Material page or slide selections were active for this guide; treat "
        "excluded pages as not part of the guide and do not claim coverage of "
        "excluded material."
    ),
    KIND_SOURCE_COVERAGE: (
        "Source coverage was measured for the included material and some source "
        "pages may have been empty or unreadable; report coverage gaps generically "
        "and page-based, and never fill them with invented content."
    ),
    KIND_VISUAL_COVERAGE: (
        "Non-table visuals were planned and the guide quality report counted "
        "observed safe figure references; do not invent diagram labels, figure "
        "captions, or figure contents, and if a diagram is unavailable say so "
        "rather than guessing."
    ),
    KIND_TABLE_POLICY: (
        "Table-like candidates were detected and have reconstruction policy "
        "guidance; tables are not screenshots, a table may be reconstructed only "
        "from available source text, never from an image, and table rows, cells, "
        "labels, and values must never be invented."
    ),
    KIND_MISSING_MATERIAL: (
        "Some detected visual or table material could not be inserted or "
        "reconstructed; explain missing material honestly instead of guessing its "
        "contents."
    ),
    KIND_GUIDE_QUALITY: (
        "Guide quality checks are deterministic signal checks over safe counts, "
        "not semantic proof that the guide is complete or correct; describe them as "
        "checks, not guarantees."
    ),
}


# =============================================================================
# Public API
# =============================================================================


def build_ask_coverage_grounding(
    *,
    job: dict | None = None,
    source_coverage_report: dict | None = None,
    visual_inclusion_plan: dict | None = None,
    table_candidates_manifest: dict | None = None,
    table_reconstruction_policy: dict | None = None,
    guide_quality_report_v2: dict | None = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Pure builder: sanitized coverage signals -> Ask Guide coverage grounding.

    Reads only the already-sanitized job page-selection fields
    (``material_page_selection`` / ``material_page_selections``) and the Slice
    84/92/96 artifact dicts. Produces a short, summarising ``grounding_text`` block
    plus one closed *signal item* per active coverage signal (material selections,
    source coverage, visual coverage, table policy, missing material, guide quality).

    ``max_items`` is an optional **defensive ceiling**, NOT a product cap. Returns a
    grounding dict with ``version``, ``kind``, ``status``
    (``completed``/``partial``/``skipped``), ``summary``, ``grounding_text``,
    ``items``, ``warnings``. Pure and total: never raises, inspects no PDF/image,
    OCRs nothing, reconstructs no table, and calls no provider. On any unexpected
    input it degrades to a safe ``skipped`` grounding with an empty ``grounding_text``.
    """
    try:
        return _build(
            job,
            source_coverage_report,
            visual_inclusion_plan,
            table_candidates_manifest,
            table_reconstruction_policy,
            guide_quality_report_v2,
            max_items,
        )
    except Exception:
        return _skipped_grounding({ALL_INPUTS_MISSING}, _blank_summary())


# =============================================================================
# Builder
# =============================================================================


def _build(
    job: Any,
    source_coverage_report: Any,
    visual_inclusion_plan: Any,
    table_candidates_manifest: Any,
    table_reconstruction_policy: Any,
    guide_quality_report_v2: Any,
    max_items: Any,
) -> dict[str, Any]:
    warnings: set[str] = set()

    if all(
        value is None
        for value in (
            job,
            source_coverage_report,
            visual_inclusion_plan,
            table_candidates_manifest,
            table_reconstruction_policy,
            guide_quality_report_v2,
        )
    ):
        return _skipped_grounding({ALL_INPUTS_MISSING}, _blank_summary())

    # --- Read every input for DECISIONS ONLY (never echo a raw field) ---------
    has_selections = _has_material_selections(job, warnings)
    source_count, unreadable_pages = _coverage_counts(source_coverage_report, warnings)
    planned_visual_count = _plan_count(visual_inclusion_plan, warnings)
    table_candidate_count = _table_candidate_count(table_candidates_manifest, warnings)
    table_policy_item_count = _table_policy_count(table_reconstruction_policy, warnings)
    (
        quality_present,
        observed_figure_refs,
        missing_material_signals,
        quality_warnings,
    ) = _guide_quality_counts(guide_quality_report_v2, warnings)

    summary = {
        "has_material_page_selections": has_selections,
        "source_count": source_count,
        "unreadable_page_count": unreadable_pages,
        "planned_visual_count": planned_visual_count,
        "observed_safe_figure_ref_count": observed_figure_refs,
        "table_candidate_count": table_candidate_count,
        "table_policy_item_count": table_policy_item_count,
        "missing_material_signal_count": missing_material_signals,
        "quality_warning_count": quality_warnings,
        "grounding_item_count": 0,
    }

    # --- Decide which closed coverage signals are active ----------------------
    active: dict[str, bool] = {
        KIND_MATERIAL_SELECTION: has_selections,
        KIND_SOURCE_COVERAGE: source_count > 0 or unreadable_pages > 0,
        KIND_VISUAL_COVERAGE: planned_visual_count > 0 or observed_figure_refs > 0,
        KIND_TABLE_POLICY: table_candidate_count > 0 or table_policy_item_count > 0,
        KIND_MISSING_MATERIAL: missing_material_signals > 0,
        KIND_GUIDE_QUALITY: quality_present or quality_warnings > 0,
    }
    signals = [kind for kind in _SIGNAL_ORDER if active.get(kind)]

    status_token = "completed"
    ceiling = _GROUNDING_ITEM_HARD_CEILING
    if isinstance(max_items, int) and not isinstance(max_items, bool) and max_items >= 0:
        ceiling = min(ceiling, max_items)
    if len(signals) > ceiling:
        signals = signals[:ceiling]
        warnings.add(MAX_ITEMS_APPLIED)
        status_token = "partial"

    if not signals:
        # Nothing useful and safe to ground on (all coverage signals inactive).
        return _skipped_grounding(warnings, summary)

    items: list[dict[str, Any]] = []
    for index, kind in enumerate(signals, start=1):
        items.append(
            {
                "item_id": f"{ITEM_ID_PREFIX}{index:04d}",
                # Coverage signals are aggregate, not page-anchored, so there is no
                # single verifiable source page.
                "source_page": None,
                "kind": kind,
                "instruction": _SIGNAL_INSTRUCTION[kind],
                "warnings": [],
            }
        )

    summary["grounding_item_count"] = len(items)
    grounding_text = _grounding_text(signals, summary)
    return _finalize(status_token, summary, items, grounding_text, warnings)


# =============================================================================
# Input extraction (read for decisions; never echo raw input)
# =============================================================================


def _has_material_selections(job: Any, warnings: set[str]) -> bool:
    """True when a global or per-attachment page selection actually limits pages."""
    if job is None:
        return False
    if not isinstance(job, dict):
        warnings.add(JOB_REQUEST_MALFORMED)
        return False
    if _selection_active(job.get("material_page_selection")):
        return True
    per = job.get("material_page_selections")
    if isinstance(per, dict):
        # The envelope may nest per-attachment selections under "attachments".
        candidates = per.get("attachments") if isinstance(per.get("attachments"), dict) else per
        if isinstance(candidates, dict):
            for selection in candidates.values():
                if _selection_active(selection):
                    return True
    return False


def _selection_active(selection: Any) -> bool:
    if not isinstance(selection, dict):
        return False
    for key in ("include_pages", "exclude_pages"):
        pages = selection.get(key)
        if isinstance(pages, list) and any(_is_positive_int(page) for page in pages):
            return True
    return _token(selection.get("mode")) in ("include", "exclude")


def _coverage_counts(report: Any, warnings: set[str]) -> tuple[int, int]:
    """Return (source_count, unreadable_page_count) from the source coverage report."""
    if report is None:
        return 0, 0
    if not isinstance(report, dict):
        warnings.add(SOURCE_COVERAGE_MALFORMED)
        return 0, 0
    if _token(report.get("status")) == "skipped":
        return 0, 0
    summary = report.get("summary")
    if not isinstance(summary, dict):
        warnings.add(SOURCE_COVERAGE_MALFORMED)
        return 0, 0
    return (
        _safe_count(summary.get("source_count")),
        _safe_count(summary.get("empty_or_unreadable_pages")),
    )


def _plan_count(plan: Any, warnings: set[str]) -> int:
    return _artifact_count(
        plan,
        summary_keys=("non_table_planned_count", "planned_count"),
        list_key="items",
        malformed=VISUAL_PLAN_MALFORMED,
        warnings=warnings,
    )


def _table_candidate_count(manifest: Any, warnings: set[str]) -> int:
    return _artifact_count(
        manifest,
        summary_keys=("table_like_candidate_count", "candidate_count"),
        list_key="candidates",
        malformed=TABLE_MANIFEST_MALFORMED,
        warnings=warnings,
    )


def _table_policy_count(policy: Any, warnings: set[str]) -> int:
    return _artifact_count(
        policy,
        summary_keys=("policy_item_count",),
        list_key="items",
        malformed=TABLE_POLICY_MALFORMED,
        warnings=warnings,
    )


def _guide_quality_counts(report: Any, warnings: set[str]) -> tuple[bool, int, int, int]:
    """Return (present, observed_safe_figure_refs, missing_material_signals, warnings)."""
    if report is None:
        return False, 0, 0, 0
    if not isinstance(report, dict):
        warnings.add(GUIDE_QUALITY_MALFORMED)
        return False, 0, 0, 0
    if _token(report.get("status")) == "skipped":
        return False, 0, 0, 0
    summary = report.get("summary")
    if not isinstance(summary, dict):
        warnings.add(GUIDE_QUALITY_MALFORMED)
        return False, 0, 0, 0
    present = summary.get("guide_present") is True
    return (
        present,
        _safe_count(summary.get("safe_image_ref_count")),
        _safe_count(summary.get("missing_material_item_count")),
        _safe_count(summary.get("warning_count")),
    )


def _artifact_count(
    artifact: Any,
    *,
    summary_keys: tuple[str, ...],
    list_key: str,
    malformed: str,
    warnings: set[str],
) -> int:
    """Count items in a sanitized artifact: summary count first, list len fallback."""
    if artifact is None:
        return 0
    if not isinstance(artifact, dict):
        warnings.add(malformed)
        return 0
    if _token(artifact.get("status")) == "skipped":
        return 0
    summary = artifact.get("summary")
    if isinstance(summary, dict):
        for key in summary_keys:
            count = _safe_count(summary.get(key), default=None)
            if count is not None:
                return count
    listed = artifact.get(list_key)
    if isinstance(listed, list):
        return len(listed)
    return 0


# =============================================================================
# Grounding text (closed; never echoes raw input)
# =============================================================================


def _grounding_text(signals: list[str], summary: dict[str, Any]) -> str:
    lines = list(_HEADER_LINES)
    active = set(signals)

    if KIND_MATERIAL_SELECTION in active:
        lines.append("- Material page or slide exclusions: active.")
    else:
        lines.append("- No material page or slide exclusions were recorded.")

    if KIND_SOURCE_COVERAGE in active:
        lines.append(
            f"- Source coverage: {summary['source_count']} source(s); "
            f"{summary['unreadable_page_count']} page(s) were empty or unreadable."
        )
    if KIND_VISUAL_COVERAGE in active:
        lines.append(
            f"- Non-table visuals planned: {summary['planned_visual_count']}. "
            "Observed safe figure references in the guide quality report: "
            f"{summary['observed_safe_figure_ref_count']}."
        )
    if KIND_TABLE_POLICY in active:
        lines.append(
            f"- Table-like candidates detected: {summary['table_candidate_count']}, "
            f"with {summary['table_policy_item_count']} table policy action(s). "
            "Tables are not screenshots; reconstruct a table only from available "
            "source text and never invent rows, cells, labels, or values."
        )
    if KIND_MISSING_MATERIAL in active:
        lines.append(
            "- Missing-material notes available: "
            f"{summary['missing_material_signal_count']}. When a diagram or table "
            "could not be included, note it honestly instead of guessing."
        )
    if KIND_GUIDE_QUALITY in active:
        lines.append(
            f"- Guide quality checks raised {summary['quality_warning_count']} "
            "warning(s)."
        )

    lines.extend(_CLOSING_LINES)
    return "\n".join(lines)


# =============================================================================
# Field coercion
# =============================================================================


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _safe_count(value: Any, *, default: int | None = 0) -> int | None:
    # A safe count is a non-negative int (never a float/str/bool).
    if not isinstance(value, int) or isinstance(value, bool):
        return default
    return value if value >= 0 else default


def _token(value: Any) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


# =============================================================================
# Assembly
# =============================================================================


def _blank_summary() -> dict[str, Any]:
    return {
        "has_material_page_selections": False,
        "source_count": 0,
        "unreadable_page_count": 0,
        "planned_visual_count": 0,
        "observed_safe_figure_ref_count": 0,
        "table_candidate_count": 0,
        "table_policy_item_count": 0,
        "missing_material_signal_count": 0,
        "quality_warning_count": 0,
        "grounding_item_count": 0,
    }


def _finalize(
    status: str,
    summary: dict[str, Any],
    items: list[dict[str, Any]],
    grounding_text: str,
    warnings: set[str],
) -> dict[str, Any]:
    return {
        "version": GROUNDING_VERSION,
        "kind": GROUNDING_KIND,
        "status": status,
        "summary": summary,
        "grounding_text": grounding_text,
        "items": items,
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


def _skipped_grounding(warnings: set[str], summary: dict[str, Any]) -> dict[str, Any]:
    safe_summary = dict(summary)
    safe_summary["grounding_item_count"] = 0
    return _finalize("skipped", safe_summary, [], "", warnings)
