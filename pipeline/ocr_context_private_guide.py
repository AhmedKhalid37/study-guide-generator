"""OCR-context private guide preview + closed score/comparison (Slice 176L).

The **first student-visible artifact** after the local-OCR breakthrough. Slices
176G–176I proved the deck's text layer is near-empty but the local structured OCR
producer recovers real slide content (dense grids, a patient-dataset table) into a
**private, gitignored** artifact; Slice 176K selected a tiny set of student-visible
display assets from it. 176L is the product step: it **assembles a private student
guide preview from that OCR-extracted content** (optionally embedding the 176K
visible assets) and **scores it against the existing baseline guide** using the
already-committed deterministic guide-quality contract lint — no new judge, no LLM,
no provider/model generation.

What this module IS:
  * a pure, offline **preview builder** that turns 176I manifest entries (+ an
    optional 176K visible-asset payload) into a comprehensive-style guide-preview
    **markdown string** — the real thing a student would read;
  * a thin wrapper over the committed, deterministic
    ``guide_quality_contract_lint`` scorer (counts only, no LLM) plus a deterministic
    **closed** baseline comparison (improved / unchanged / regressed / unavailable).

What this module is **NOT** (do not grow it into any of these here):
  * a new evaluator / judge, a Layer-2 judge, repair, numeric-recompute wiring,
    provider/model generation, guide-generation wiring into normal app behavior,
    frontend/API integration, full ingestion rollout, or cloud OCR.
    ``judge_ready=false``; ``repair_ready=false``.

Privacy / anti-laundering rules (non-negotiable):
  * The assembled guide-preview markdown carries reconstructed OCR table content and
    is written **only** into the confirmed-private (gitignored / temp) artifact
    directory — it is never committed or printed. The committed summary carries
    **closed tokens / bools** only; every ``*_committed`` flag is hardwired ``False``
    and the summary builder accepts no raw text / path / size / count-of-values
    argument.
  * The embedded visible assets are **display / study assets** only. Nothing is fed
    into recompute; ``numeric_verification_claimed`` is a hardwired ``False``.
  * Scoring uses **only** the existing deterministic contract lint. If a baseline is
    not available privately, the comparison is honestly ``unavailable`` — never an
    invented score.

The core API (:func:`build_ocr_context_guide_markdown`,
:func:`score_guide_markdown`, :func:`derive_baseline_comparison`,
:func:`build_closed_score_summary`) is pure and consumes only in-memory values; a
thin env-driven :func:`main` reads the private 176I manifest + optional baseline
markdown, writes the private preview, and prints the **closed** summary.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.guide_quality_contract_lint import (  # noqa: E402
    build_guide_quality_contract_lint_report,
)
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402
from pipeline.visible_table_figure_pilot import (  # noqa: E402
    _CATEGORY_MAP,
    _grid_to_markdown,
    extract_layout_tables_from_html,
)

ARTIFACT_NAME = "ocr_context_private_guide_score"
SOURCE_LABEL_DEFAULT = "ensemble"

# ── Closed vocabularies (this module owns what it emits) ─────────────────────
STATUSES = frozenset({"completed", "degraded", "blocked", "skipped"})
GENERATION_MODES = frozenset(
    {
        "existing_local_provider",
        "existing_configured_provider",
        "deterministic_stub_preview",
        "not_run",
    }
)
GUIDE_ARTIFACT_STATUSES = frozenset({"generated", "preview_generated", "blocked", "not_run"})
RENDER_STATUSES = frozenset({"rendered", "not_run", "failed", "not_supported"})
SCORE_STATUSES = frozenset({"scored", "not_available", "failed", "not_run"})
COMPARISON_STATUSES = frozenset(
    {"improved", "unchanged", "regressed", "unavailable", "not_run"}
)
SIGNAL_STATUSES = COMPARISON_STATUSES
VISIBLE_ASSETS_USED = frozenset({"yes", "no", "partial", "not_available"})
VISIBLE_ASSET_CATEGORIES = frozenset(
    {
        "proximity_matrix",
        "patient_dataset_table",
        "decision_tree_or_split_diagram",
        "mixed",
        "none",
    }
)
BLOCKED_BY = frozenset(
    {
        "none",
        "private_artifact_missing",
        "generation_unavailable",
        "render_unavailable",
        "score_unavailable",
        "privacy_boundary",
        "scope_too_large",
    }
)
NEXT_STEPS = frozenset(
    {
        "inspect_private_ocr_context_guide",
        "wire_visible_assets_into_private_guide_preview",
        "run_existing_eval_on_private_guide",
        "build_off_by_default_ocr_context_generation_path",
        "improve_prompt_context_packaging",
        "blocked",
    }
)

# Closed display titles for the (private) preview headings. These are generic domain
# labels keyed by closed category token — never source text.
_CATEGORY_TITLE = {
    "ensemble_proximity_matrix": "Proximity Matrix",
    "ensemble_patient_dataset_table": "Patient Dataset Table",
    "ensemble_decision_tree_or_split_diagram": "Decision Tree / Split Diagram",
    "ensemble_gini_or_leaf_count": "Gini / Leaf-Count Summary",
    "ensemble_weighted_frequency_or_total_error": "Weighted Frequency / Total Error",
}
# Categories that map into the closed visible-asset category vocabulary (the 176K set).
_VISIBLE_CATEGORY_TOKEN = {
    "proximity_matrix": "proximity_matrix",
    "patient_dataset_table": "patient_dataset_table",
    "decision_tree_or_split_diagram": "decision_tree_or_split_diagram",
}

# Comprehensive-style scaffold headings so the preview reads as a real study guide and
# the existing contract lint can measure required structure on both candidate/baseline.
_PREVIEW_BANNER = (
    "> Private, off-by-default preview assembled from locally OCR-extracted slide "
    "content (Slice 176L). Display/study material only — not numeric verification."
)


# ── Preview builder (private markdown; raw OCR content stays private) ─────────


def build_ocr_context_guide_markdown(
    entries: Any,
    *,
    source_label: str = SOURCE_LABEL_DEFAULT,
    visible_payload: Any = None,
) -> tuple[str, dict[str, Any]]:
    """Assemble a private student guide-preview markdown from 176I manifest entries.

    Returns ``(markdown, build_stats)``. ``markdown`` carries reconstructed OCR table
    content and MUST be written only to the private artifact dir (never committed).
    ``build_stats`` is closed (counts / closed tokens) for summary derivation. Pure /
    total; never raises.
    """
    label = _safe_label(source_label)
    visible_md = _visible_markdown_by_category(visible_payload)

    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        raw_cat = entry.get("slide_category")
        token = _CATEGORY_MAP.get(raw_cat) if isinstance(raw_cat, str) else None
        if token is None or raw_cat in seen:
            continue
        seen.add(raw_cat)
        ordered.append(entry)

    lines: list[str] = []
    lines.append(f"# Study Guide Preview — {label} (OCR context)")
    lines.append("")
    lines.append(_PREVIEW_BANNER)
    lines.append("")
    lines.append("## Overview")
    lines.append(
        "This preview is built from slide content recovered by local structured OCR "
        "on content-bearing slides whose text layer was otherwise near-empty."
    )
    lines.append("")
    lines.append("## Key Concepts")
    lines.append(
        "Each recovered content slide is surfaced below as a labelled reference table "
        "with supporting context so the material is studiable rather than missing."
    )
    lines.append("")

    table_count = 0
    caption_count = 0
    visible_used: list[str] = []
    section_categories: list[str] = []

    lines.append("## Reference Tables")
    lines.append("")
    for entry in ordered:
        raw_cat = entry.get("slide_category")
        token = _CATEGORY_MAP.get(raw_cat)
        title = _CATEGORY_TITLE.get(raw_cat, "Recovered Slide")
        section_categories.append(token)
        lines.append(f"### {title}")
        # Prefer the 176K visible-asset markdown if present; otherwise reconstruct from
        # the entry's raw layout HTML.
        md_tables = visible_md.get(token) or _entry_table_markdown(entry)
        if md_tables:
            for md in md_tables:
                lines.append("")
                lines.append(md)
                table_count += 1
            if token in _VISIBLE_CATEGORY_TOKEN and visible_md.get(token):
                visible_used.append(_VISIBLE_CATEGORY_TOKEN[token])
        else:
            lines.append("")
            lines.append("_Structured table not recovered for this slide._")
        context = _entry_context_line(entry)
        if context:
            caption_count += 1
            lines.append("")
            lines.append(f"*Context: {context}*")
        lines.append("")

    lines.append("## Worked Examples")
    lines.append(
        "Use the recovered reference tables above to work through the split / impurity "
        "and ensemble-voting steps shown in lecture."
    )
    lines.append("")
    lines.append("## ⚠️ EXAM ALERT")
    lines.append(
        "These recovered tables are high-yield; values are shown for study and are not "
        "independently recomputed here."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append(
        "The OCR-recovered slide content is now present in the guide instead of being "
        "dropped with the near-empty text layer."
    )
    lines.append("")

    markdown = "\n".join(lines)
    stats = {
        "section_count": len(ordered),
        "table_count": table_count,
        "caption_count": caption_count,
        "visible_asset_categories": _dedupe_closed(visible_used, _VISIBLE_CATEGORY_TOKEN.values()),
        "section_categories": [c for c in section_categories if c],
    }
    return markdown, stats


def _entry_table_markdown(entry: dict[str, Any]) -> list[str]:
    grids = extract_layout_tables_from_html(entry.get("raw_layout_html"))
    return [_grid_to_markdown(g) for g in grids if g]


def _entry_context_line(entry: dict[str, Any]) -> str:
    """A short, generic context note. Never echoes raw OCR text into committed output.

    The returned string lives only in the PRIVATE preview markdown; the committed
    summary derives only counts/bools from it.
    """
    signals = entry.get("signals") if isinstance(entry.get("signals"), dict) else {}
    if signals.get("caption_count") or signals.get("text_block_count"):
        return "recovered slide caption / context available"
    return ""


def _visible_markdown_by_category(visible_payload: Any) -> dict[str, list[str]]:
    """Pull reconstructed table markdown from a 176K visible-asset payload, by token."""
    out: dict[str, list[str]] = {}
    assets = visible_payload.get("assets") if isinstance(visible_payload, dict) else None
    for asset in assets if isinstance(assets, list) else []:
        if not isinstance(asset, dict):
            continue
        token = asset.get("asset_category")
        md = asset.get("table_markdown")
        if isinstance(token, str) and isinstance(md, list):
            cleaned = [m for m in md if isinstance(m, str) and m.strip()]
            if cleaned:
                out.setdefault(token, []).extend(cleaned)
    return out


# ── Scoring (existing deterministic contract lint only; no LLM) ──────────────


def score_guide_markdown(markdown: Any) -> dict[str, Any]:
    """Score one guide markdown with the existing deterministic contract lint.

    Returns the committed-safe lint report (closed counts/tokens only). Never an LLM
    judge. Pure / total.
    """
    return build_guide_quality_contract_lint_report(markdown, comprehensive=True)


def _lint_metrics(report: Any) -> dict[str, int] | None:
    if not isinstance(report, dict):
        return None
    if report.get("status") == "skipped":
        return None
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return None
    return {
        "table_count": _safe_count(summary.get("table_count")),
        "present_sections": _safe_count(summary.get("required_section_present_count")),
        "exam_alert_count": _safe_count(summary.get("exam_alert_count")),
        "reasoning_leak_count": _safe_count(summary.get("reasoning_leak_count")),
        "warning_count": _safe_count(summary.get("warning_count")),
    }


def derive_baseline_comparison(
    candidate_report: Any, baseline_report: Any
) -> dict[str, str]:
    """Deterministic closed comparison of candidate vs baseline lint reports.

    Emits closed tokens only — never raw counts. ``score_status=scored`` iff the
    candidate lint produced usable metrics; baseline-dependent signals fall back to
    ``unavailable`` when no usable baseline is present. Pure / total.
    """
    cand = _lint_metrics(candidate_report)
    base = _lint_metrics(baseline_report)

    if cand is None:
        return {
            "score_status": "not_available",
            "baseline_comparison_status": "unavailable",
            "coverage_signal": "unavailable",
            "figure_table_signal": "unavailable",
        }

    if base is None:
        return {
            "score_status": "scored",
            "baseline_comparison_status": "unavailable",
            "coverage_signal": "unavailable",
            "figure_table_signal": "unavailable",
        }

    figure_table_signal = _direction(cand["table_count"], base["table_count"])
    # Coverage proxy: present required sections + reference tables surfaced.
    coverage_signal = _direction(
        cand["present_sections"] + cand["table_count"],
        base["present_sections"] + base["table_count"],
    )
    # Overall: more reference tables / present sections is better; more lint warnings
    # is worse. Honest tie -> unchanged. Warnings regressing overrides a content gain
    # only when content did not improve.
    content_dir = _direction(
        cand["present_sections"] + cand["table_count"],
        base["present_sections"] + base["table_count"],
    )
    warning_dir = _direction(base["warning_count"], cand["warning_count"])  # fewer is better
    overall = _combine(content_dir, warning_dir)
    return {
        "score_status": "scored",
        "baseline_comparison_status": overall,
        "coverage_signal": coverage_signal,
        "figure_table_signal": figure_table_signal,
    }


def _direction(candidate: int, baseline: int) -> str:
    if candidate > baseline:
        return "improved"
    if candidate < baseline:
        return "regressed"
    return "unchanged"


def _combine(primary: str, secondary: str) -> str:
    if primary == "improved":
        return "improved"
    if primary == "regressed":
        return "regressed"
    # primary unchanged -> let the warning direction break the tie.
    return secondary


# ── Closed summary builder (committed-safe; no raw content) ──────────────────


def build_closed_score_summary(
    *,
    status: str,
    source_label: str = SOURCE_LABEL_DEFAULT,
    private_ocr_artifact_available: bool,
    private_ocr_artifact_gitignored: bool,
    private_visible_artifact_available: bool = False,
    private_visible_artifact_gitignored: bool = False,
    private_guide_artifact_written: bool = False,
    private_guide_artifact_gitignored: bool = False,
    generation_mode: str = "not_run",
    visible_assets_used: str = "no",
    selected_visible_asset_categories: list[str] | None = None,
    guide_artifact_status: str = "not_run",
    render_status: str = "not_run",
    score_status: str = "not_run",
    baseline_comparison_status: str = "not_run",
    coverage_signal: str = "not_run",
    figure_table_signal: str = "not_run",
    blocked_by: str = "none",
    recommended_next_step: str | None = None,
) -> dict[str, Any]:
    """Assemble the committed-safe closed score/comparison summary.

    All fields are coerced into closed sets; raw guide / OCR / table / caption text,
    prompts, responses, provider payloads, rendered files, source PDFs, model
    files/caches, and private paths are structurally excluded (the ``*_committed``
    flags are hardwired ``False`` and no text/path/size argument is accepted).
    ``numeric_verification_claimed`` is hardwired ``False``.
    """
    coerced_status = _coerce(status, STATUSES, "blocked")
    cats = _safe_visible_categories(selected_visible_asset_categories)

    if recommended_next_step is None:
        recommended_next_step = _default_next_step(
            coerced_status, _coerce(score_status, SCORE_STATUSES, "not_run"),
            _coerce(baseline_comparison_status, COMPARISON_STATUSES, "not_run"),
            _coerce(visible_assets_used, VISIBLE_ASSETS_USED, "no"),
            _coerce(generation_mode, GENERATION_MODES, "not_run"),
        )

    return {
        "artifact_name": ARTIFACT_NAME,
        "status": coerced_status,
        "source_label": _safe_label(source_label),
        "private_ocr_artifact_available": bool(private_ocr_artifact_available),
        "private_ocr_artifact_gitignored": bool(private_ocr_artifact_gitignored),
        "private_visible_artifact_available": bool(private_visible_artifact_available),
        "private_visible_artifact_gitignored": bool(private_visible_artifact_gitignored),
        "private_guide_artifact_written": bool(private_guide_artifact_written),
        "private_guide_artifact_gitignored": bool(private_guide_artifact_gitignored),
        "raw_ocr_committed": False,
        "raw_guide_text_committed": False,
        "raw_table_text_committed": False,
        "raw_caption_text_committed": False,
        "rendered_guide_committed": False,
        "source_pdf_committed": False,
        "prompts_committed": False,
        "responses_committed": False,
        "provider_payloads_committed": False,
        "cloud_ocr_used": False,
        "generation_mode": _coerce(generation_mode, GENERATION_MODES, "not_run"),
        "generation_behavior_changed": False,
        "frontend_api_changed": False,
        "visible_assets_used": _coerce(visible_assets_used, VISIBLE_ASSETS_USED, "no"),
        "selected_visible_asset_categories": cats,
        "guide_artifact_status": _coerce(guide_artifact_status, GUIDE_ARTIFACT_STATUSES, "not_run"),
        "render_status": _coerce(render_status, RENDER_STATUSES, "not_run"),
        "score_status": _coerce(score_status, SCORE_STATUSES, "not_run"),
        "baseline_comparison_status": _coerce(baseline_comparison_status, COMPARISON_STATUSES, "not_run"),
        "coverage_signal": _coerce(coverage_signal, SIGNAL_STATUSES, "not_run"),
        "figure_table_signal": _coerce(figure_table_signal, SIGNAL_STATUSES, "not_run"),
        "numeric_verification_claimed": False,
        "judge_ready": False,
        "repair_ready": False,
        "blocked_by": _coerce(blocked_by, BLOCKED_BY, "none"),
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "inspect_private_ocr_context_guide"),
    }


def _default_next_step(
    status: str, score_status: str, comparison: str, visible: str, generation_mode: str
) -> str:
    if status in {"blocked", "skipped"}:
        return "blocked"
    if score_status != "scored":
        return "run_existing_eval_on_private_guide"
    if comparison == "improved":
        return "build_off_by_default_ocr_context_generation_path"
    # A deterministic stub preview is known-thin vs a full generated guide, so a
    # regressed/unchanged contract-lint comparison is a stub-vs-full-guide confound,
    # NOT evidence that OCR content hurts. The fair next measurement is to feed the
    # OCR content through the real (off-by-default) generation path and re-score.
    if generation_mode == "deterministic_stub_preview" and comparison in {"regressed", "unchanged"}:
        return "build_off_by_default_ocr_context_generation_path"
    if visible in {"no", "not_available"}:
        return "wire_visible_assets_into_private_guide_preview"
    return "inspect_private_ocr_context_guide"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def _safe_label(value: Any) -> str:
    import re

    text = str(value or "unknown")
    cleaned = re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")
    return (cleaned or "unknown")[:40]


def _safe_count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _dedupe_closed(values: Any, allowed: Any) -> list[str]:
    allowed_set = set(allowed)
    out: list[str] = []
    for v in values if isinstance(values, list) else []:
        if v in allowed_set and v not in out:
            out.append(v)
    return out


def _safe_visible_categories(categories: Any) -> list[str]:
    out: list[str] = []
    for c in categories if isinstance(categories, list) else []:
        token = c if c in VISIBLE_ASSET_CATEGORIES else "none"
        if token != "none" and token not in out:
            out.append(token)
    return out or ["none"]


def visible_assets_token(categories: list[str]) -> str:
    """Closed ``visible_assets_used`` token from the included visible categories."""
    real = [c for c in categories if c in _VISIBLE_CATEGORY_TOKEN.values()]
    if not real:
        return "no"
    if len(set(real)) >= 2:
        return "yes"
    return "partial"


# ── Env-driven private runner (no committed path; closed output only) ────────


def _read_private_markdown(path: Any) -> str | None:
    """Read a guide markdown only from a confirmed-private (gitignored) location."""
    if not isinstance(path, str) or not path:
        return None
    if not os.path.isfile(path):
        return None
    if not is_private_artifact_dir(os.path.dirname(os.path.abspath(path))):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return None


def main() -> int:
    """Build the private OCR-context guide preview and print the closed score summary.

    Env:
      PRIVATE_OCR_DIR        gitignored/temp dir with 176I's manifest (+176K payload)
      SOURCE_LABEL           closed source label (default "ensemble")
      BASELINE_GUIDE_MD      optional path to the private baseline guide markdown
                             (must live in a gitignored/temp dir)
      INCLUDE_VISIBLE_ASSETS "1" (default) to embed 176K visible assets if present
    """
    private_dir = os.environ.get("PRIVATE_OCR_DIR")
    source_label = os.environ.get("SOURCE_LABEL", SOURCE_LABEL_DEFAULT)
    baseline_md_path = os.environ.get("BASELINE_GUIDE_MD")
    include_visible = os.environ.get("INCLUDE_VISIBLE_ASSETS", "1") == "1"

    def blocked(reason: str) -> int:
        summary = build_closed_score_summary(
            status="blocked",
            source_label=source_label,
            private_ocr_artifact_available=False,
            private_ocr_artifact_gitignored=False,
            blocked_by=reason,
            recommended_next_step="blocked",
        )
        print(json.dumps(summary, indent=2))
        return 2

    if not private_dir:
        return blocked("private_artifact_missing")
    gitignored = is_private_artifact_dir(private_dir)
    if not gitignored:
        return blocked("privacy_boundary")

    manifest_path = os.path.join(private_dir, "extracted_content_manifest.json")
    if not os.path.isfile(manifest_path):
        return blocked("private_artifact_missing")
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        entries = manifest.get("entries", []) if isinstance(manifest, dict) else []
    except Exception:
        return blocked("private_artifact_missing")

    if not entries:
        return blocked("private_artifact_missing")

    # Optional 176K visible-asset payload (private).
    visible_payload = None
    visible_available = False
    if include_visible:
        vp = os.path.join(private_dir, "visible_table_figure_pilot.json")
        if os.path.isfile(vp):
            try:
                with open(vp, encoding="utf-8") as fh:
                    visible_payload = json.load(fh)
                visible_available = isinstance(visible_payload, dict)
            except Exception:
                visible_payload = None

    markdown, stats = build_ocr_context_guide_markdown(
        entries, source_label=source_label, visible_payload=visible_payload
    )

    # Write the private preview markdown ONLY into the private dir.
    guide_written = False
    if is_private_artifact_dir(private_dir):
        try:
            out_path = os.path.join(private_dir, "ocr_context_private_guide.md")
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(markdown)
            guide_written = bool(markdown.strip())
        except Exception:
            guide_written = False

    # Score with the existing deterministic contract lint (no LLM).
    candidate_report = score_guide_markdown(markdown)
    baseline_markdown = _read_private_markdown(baseline_md_path)
    baseline_report = score_guide_markdown(baseline_markdown) if baseline_markdown else None
    signals = derive_baseline_comparison(candidate_report, baseline_report)

    visible_cats = stats.get("visible_asset_categories", [])
    visible_used = visible_assets_token(visible_cats) if visible_available else (
        "not_available" if include_visible else "no"
    )

    status = "completed" if guide_written else "degraded"
    summary = build_closed_score_summary(
        status=status,
        source_label=source_label,
        private_ocr_artifact_available=True,
        private_ocr_artifact_gitignored=gitignored,
        private_visible_artifact_available=visible_available,
        private_visible_artifact_gitignored=is_private_artifact_dir(private_dir) if visible_available else False,
        private_guide_artifact_written=guide_written,
        private_guide_artifact_gitignored=is_private_artifact_dir(private_dir),
        generation_mode="deterministic_stub_preview",
        visible_assets_used=visible_used,
        selected_visible_asset_categories=visible_cats,
        guide_artifact_status="preview_generated" if guide_written else "blocked",
        render_status="not_run",
        score_status=signals["score_status"],
        baseline_comparison_status=signals["baseline_comparison_status"],
        coverage_signal=signals["coverage_signal"],
        figure_table_signal=signals["figure_table_signal"],
        blocked_by="none",
    )
    # Print ONLY the closed summary. The private preview markdown is never printed.
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
