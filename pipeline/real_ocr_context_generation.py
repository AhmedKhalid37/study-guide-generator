"""Real (off-by-default, private) OCR-context guide generation + closed score (Slice 176N).

Slice 176L produced the **first** student-visible artifact after the local-OCR
breakthrough, but only as a ``deterministic_stub_preview`` — recovered OCR tables under a
generic scaffold. Scoring that thin stub against the *full, LLM-generated* baseline guide
with the contract lint was a **stub-vs-full-guide confound**, not evidence that OCR
content helps. 176L said so explicitly and named the fair next measurement:
feed the OCR-extracted content through the **real generation path** and re-score.

This module is that fair measurement. It:
  * assembles the private 176I OCR-extracted slide content (optionally the 176K visible
    assets) into **source material** — the "pasted source text" a student would feed the
    Builder — with ``## Page N`` anchors so the existing citation directive fires;
  * runs the **existing** generation path (``orchestrator.generate_study_guide`` →
    ``llm_client.generate_chat_completion``) against an **existing configured/local
    provider** to produce a **real** generated guide markdown (NOT a stub);
  * writes that guide **only** into the confirmed-private (gitignored/temp) artifact dir;
  * scores it against the private baseline guide with the **already-committed**
    deterministic ``guide_quality_contract_lint`` (no LLM judge, no Layer-2 judge), and
    emits a **committed-safe closed** score/comparison.

What this module is **NOT** (do not grow it into any of these here):
  * a new evaluator / judge, a Layer-2 judge, repair, numeric-recompute wiring, a NEW
    provider integration, guide-generation wiring into normal app behavior, frontend/API
    integration, the animation-frame selection pipeline, or cloud OCR. ``judge_ready=false``;
    ``repair_ready=false``.

Hard rules (mirrors the house posture in :mod:`pipeline.ocr_context_private_guide`):
  * **Real or honest-block.** The final fair candidate MUST come from a real provider
    generation. If no existing provider/local path is available (no client, no key, no
    reachable server), the run BLOCKS with ``generation_mode=generation_unavailable`` —
    it never falls back to a deterministic stub and calls it fair. ``deterministic_stub``
    is not in this module's mode vocabulary at all.
  * **Private + leak-free.** The assembled source text and the generated guide carry raw
    OCR/guide content and are written **only** into the private artifact dir — never
    committed or printed. The committed summary is closed tokens / bools / coarse signals
    only; every ``*_committed`` flag is hardwired ``False`` and the summary builder accepts
    no raw text / path / size argument.
  * **No normal-behavior change.** Reuses existing generation/scoring functions read-only;
    changes no normal generation path, no frontend, no API. ``numeric_verification_claimed``
    is hardwired ``False``.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.ocr_context_private_guide import (  # noqa: E402
    derive_baseline_comparison,
    score_guide_markdown,
    visible_assets_token,
)
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402
from pipeline.visible_table_figure_pilot import (  # noqa: E402
    _CATEGORY_MAP,
    _grid_to_markdown,
    extract_layout_tables_from_html,
)

ARTIFACT_NAME = "real_ocr_context_generation_score"
SOURCE_LABEL_DEFAULT = "ensemble"

# Filenames inside the PRIVATE artifact dir (never committed paths).
_GENERATED_GUIDE_FILENAME = "real_ocr_context_generated_guide.md"
_GENERATED_SOURCE_FILENAME = "real_ocr_context_source.md"

# ── Closed vocabularies (this module owns what it emits) ─────────────────────
STATUSES = frozenset({"completed", "degraded", "blocked", "skipped"})
# NOTE: deterministic_stub_preview is DELIBERATELY ABSENT — a stub may never be the
# fair candidate for this slice (see module docstring).
GENERATION_MODES = frozenset(
    {
        "existing_local_provider",
        "existing_configured_provider",
        "generation_unavailable",
        "not_run",
    }
)
GUIDE_ARTIFACT_STATUSES = frozenset({"generated", "blocked", "not_run"})
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
        "provider_unavailable",
        "render_unavailable",
        "score_unavailable",
        "privacy_boundary",
        "scope_too_large",
    }
)
NEXT_STEPS = frozenset(
    {
        "inspect_private_real_ocr_context_guide",
        "wire_visible_assets_into_private_guide_preview",
        "harden_off_by_default_ocr_context_generation_path",
        "improve_prompt_context_packaging",
        "run_existing_eval_on_private_guide",
        "blocked",
    }
)

# Generic, source-free display titles keyed by the closed manifest category token.
_CATEGORY_TITLE = {
    "proximity_matrix": "Proximity Matrix",
    "patient_dataset_table": "Patient Dataset Table",
    "decision_tree_or_split_diagram": "Decision Tree / Split Diagram",
    "gini_or_leaf_count_answer_summary": "Gini / Leaf-Count Summary",
    "weighted_frequency_or_total_error": "Weighted Frequency / Total Error",
}
# Tokens that map into the closed visible-asset category vocabulary (the 176K set).
_VISIBLE_CATEGORY_TOKEN = {
    "proximity_matrix": "proximity_matrix",
    "patient_dataset_table": "patient_dataset_table",
    "decision_tree_or_split_diagram": "decision_tree_or_split_diagram",
}


# ── Source-material assembly (private input to real generation) ───────────────


def build_ocr_context_source_text(
    entries: Any,
    *,
    source_label: str = SOURCE_LABEL_DEFAULT,
    visible_payload: Any = None,
) -> tuple[str, dict[str, Any]]:
    """Assemble the private SOURCE MATERIAL fed to the real generation path.

    This is the equivalent of the text a student would paste into the Builder: the
    recovered slide content, one ``## Page N`` block per content slide, with the
    reconstructed table(s) under a generic label. It is NOT a guide — the real LLM
    turns it into one. The returned markdown carries reconstructed OCR table content
    and MUST be written only to the private artifact dir (never committed). Returns
    ``(source_text, stats)``. Pure / total; never raises.
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

    lines: list[str] = [f"# Lecture source material — {label} (recovered slide content)", ""]
    lines.append(
        "The following slide content was recovered by local structured OCR from "
        "content-bearing slides whose original text layer was near-empty. Each block is "
        "one slide."
    )
    lines.append("")

    table_count = 0
    caption_count = 0
    visible_used: list[str] = []
    section_categories: list[str] = []

    for index, entry in enumerate(ordered, start=1):
        raw_cat = entry.get("slide_category")
        token = _CATEGORY_MAP.get(raw_cat)
        title = _CATEGORY_TITLE.get(token, "Recovered Slide")
        page = _safe_int(entry.get("page"), default=index)
        section_categories.append(token)
        lines.append(f"## Page {page}")
        lines.append(f"### {title}")
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
            lines.append("_(structured table not recovered for this slide)_")
        if _entry_has_context(entry):
            caption_count += 1
            lines.append("")
            lines.append("*This slide also carried caption / context text.*")
        lines.append("")

    source_text = "\n".join(lines)
    stats = {
        "section_count": len(ordered),
        "table_count": table_count,
        "caption_count": caption_count,
        "visible_asset_categories": _dedupe_closed(
            visible_used, _VISIBLE_CATEGORY_TOKEN.values()
        ),
        "section_categories": [c for c in section_categories if c],
        "source_chars": len(source_text),
    }
    return source_text, stats


def _entry_table_markdown(entry: dict[str, Any]) -> list[str]:
    grids = extract_layout_tables_from_html(entry.get("raw_layout_html"))
    return [_grid_to_markdown(g) for g in grids if g]


def _entry_has_context(entry: dict[str, Any]) -> bool:
    signals = entry.get("signals") if isinstance(entry.get("signals"), dict) else {}
    return bool(signals.get("caption_count") or signals.get("text_block_count"))


def _visible_markdown_by_category(visible_payload: Any) -> dict[str, list[str]]:
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


# ── Provider resolution (existing paths only; closed mode token) ──────────────


def generation_mode_for_provider(provider_id: Any) -> str:
    """Map a resolved provider id to the closed generation-mode token.

    ``local`` → ``existing_local_provider``; ``deepseek`` / ``qwen`` →
    ``existing_configured_provider``; anything else → ``generation_unavailable``.
    Pure / total.
    """
    if provider_id == "local":
        return "existing_local_provider"
    if provider_id in {"deepseek", "qwen"}:
        return "existing_configured_provider"
    return "generation_unavailable"


# ── Closed summary builder (committed-safe; no raw content) ──────────────────


def build_closed_generation_summary(
    *,
    status: str,
    source_label: str = SOURCE_LABEL_DEFAULT,
    private_ocr_artifact_available: bool,
    private_ocr_artifact_gitignored: bool,
    private_visible_artifact_available: bool = False,
    private_visible_artifact_gitignored: bool = False,
    private_generated_guide_written: bool = False,
    private_generated_guide_gitignored: bool = False,
    generation_mode: str = "not_run",
    visible_assets_used: str = "no",
    selected_visible_asset_categories: list[str] | None = None,
    guide_artifact_status: str = "not_run",
    render_status: str = "not_run",
    score_status: str = "not_run",
    baseline_comparison_status: str = "not_run",
    coverage_signal: str = "not_run",
    figure_table_signal: str = "not_run",
    stub_vs_full_confounded: bool = False,
    blocked_by: str = "none",
    recommended_next_step: str | None = None,
) -> dict[str, Any]:
    """Assemble the committed-safe closed real-generation score/comparison summary.

    All fields are coerced to closed sets; raw guide / OCR / table / caption text,
    prompts, responses, provider payloads, rendered files, source PDFs, model
    files/caches, and private paths are structurally excluded (the ``*_committed``
    flags are hardwired ``False`` and no text/path/size argument is accepted).
    ``numeric_verification_claimed`` / ``judge_ready`` / ``repair_ready`` are hardwired
    ``False``.
    """
    coerced_status = _coerce(status, STATUSES, "blocked")
    coerced_mode = _coerce(generation_mode, GENERATION_MODES, "not_run")
    coerced_score = _coerce(score_status, SCORE_STATUSES, "not_run")
    coerced_comparison = _coerce(baseline_comparison_status, COMPARISON_STATUSES, "not_run")
    coerced_visible = _coerce(visible_assets_used, VISIBLE_ASSETS_USED, "no")
    cats = _safe_visible_categories(selected_visible_asset_categories)

    if recommended_next_step is None:
        recommended_next_step = _default_next_step(
            coerced_status, coerced_mode, coerced_score, coerced_comparison, coerced_visible
        )

    return {
        "artifact_name": ARTIFACT_NAME,
        "status": coerced_status,
        "source_label": _safe_label(source_label),
        "private_ocr_artifact_available": bool(private_ocr_artifact_available),
        "private_ocr_artifact_gitignored": bool(private_ocr_artifact_gitignored),
        "private_visible_artifact_available": bool(private_visible_artifact_available),
        "private_visible_artifact_gitignored": bool(private_visible_artifact_gitignored),
        "private_generated_guide_written": bool(private_generated_guide_written),
        "private_generated_guide_gitignored": bool(private_generated_guide_gitignored),
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
        "generation_mode": coerced_mode,
        "generation_behavior_changed": False,
        "frontend_api_changed": False,
        "visible_assets_used": coerced_visible,
        "selected_visible_asset_categories": cats,
        "guide_artifact_status": _coerce(guide_artifact_status, GUIDE_ARTIFACT_STATUSES, "not_run"),
        "render_status": _coerce(render_status, RENDER_STATUSES, "not_run"),
        "score_status": coerced_score,
        "baseline_comparison_status": coerced_comparison,
        "coverage_signal": _coerce(coverage_signal, SIGNAL_STATUSES, "not_run"),
        "figure_table_signal": _coerce(figure_table_signal, SIGNAL_STATUSES, "not_run"),
        # A real generation path is never a stub-vs-full confound; only True if a
        # deterministic stub were ever scored as the candidate (this module forbids it).
        "stub_vs_full_confounded": bool(stub_vs_full_confounded),
        "numeric_verification_claimed": False,
        "judge_ready": False,
        "repair_ready": False,
        "blocked_by": _coerce(blocked_by, BLOCKED_BY, "none"),
        "recommended_next_step": _coerce(
            recommended_next_step, NEXT_STEPS, "inspect_private_real_ocr_context_guide"
        ),
    }


def _default_next_step(
    status: str, mode: str, score_status: str, comparison: str, visible: str
) -> str:
    if status in {"blocked", "skipped"}:
        return "blocked"
    if mode == "generation_unavailable":
        return "blocked"
    if score_status != "scored":
        return "run_existing_eval_on_private_guide"
    if comparison == "improved":
        return "harden_off_by_default_ocr_context_generation_path"
    # A REAL generated guide that scores unchanged/regressed vs the baseline is no
    # longer a stub-vs-full confound. This token records the suspected packaging
    # lever; follow-up work must still diagnose scorer sensitivity/model prior
    # knowledge before spending another provider-generation run.
    if comparison in {"regressed", "unchanged"}:
        return "improve_prompt_context_packaging"
    if visible in {"no", "not_available"}:
        return "wire_visible_assets_into_private_guide_preview"
    return "inspect_private_real_ocr_context_guide"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def _safe_label(value: Any) -> str:
    import re

    text = str(value or "unknown")
    cleaned = re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")
    return (cleaned or "unknown")[:40]


def _safe_int(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        out = int(value)
        return out if out > 0 else default
    except (TypeError, ValueError):
        return default


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


# ── Provider resolution + real generation (existing paths only) ───────────────


def _resolve_generation_config(preferred: str | None) -> tuple[Any, str, str | None]:
    """Resolve an LLMConfig from an EXISTING provider path. No new provider.

    Tries, in order: an explicit ``preferred`` provider, configured providers
    ``deepseek`` / ``qwen``, then the on-machine ``local`` server. Returns
    ``(config_or_None, provider_id, error_token)``. ``error_token`` is a closed
    BLOCKED_BY token when no usable provider/client is available. Never raises.
    """
    # The generation client itself (openai) must be importable, or the existing path
    # cannot run at all in this environment — honest provider_unavailable.
    try:
        import openai  # noqa: F401
    except Exception:
        return None, "none", "provider_unavailable"

    try:
        from pipeline.llm_client import MissingLLMConfigError
        from pipeline.provider_config import build_provider_config, get_provider_entry
    except Exception:
        return None, "none", "provider_unavailable"

    order: list[str] = []
    if isinstance(preferred, str) and preferred:
        order.append(preferred)
    for pid in ("deepseek", "qwen", "local"):
        if pid not in order:
            order.append(pid)

    for pid in order:
        try:
            entry = get_provider_entry(pid, discover_local=(pid == "local"))
        except Exception:
            entry = None
        if entry is None or not getattr(entry, "configured", False):
            continue
        try:
            config = build_provider_config(pid, "Use environment default")
        except MissingLLMConfigError:
            continue
        except Exception:
            continue
        return config, pid, None

    return None, "none", "provider_unavailable"


def _run_real_generation(source_text: str, *, title: str, config: Any) -> tuple[str | None, str | None]:
    """Run the EXISTING generation path once. Returns ``(guide_markdown, error_token)``.

    Reuses ``orchestrator.generate_study_guide`` with the comprehensive ``claude_review``
    preset and exhaustive depth (a legitimate generation setting, not score tuning).
    Any provider/transport failure returns ``(None, "generation_unavailable")`` — never a
    stub. Never raises.
    """
    preset = os.environ.get("GENERATION_PRESET", "claude_review")
    depth = os.environ.get("GENERATION_DEPTH", "exhaustive")
    difficulty = os.environ.get("GENERATION_DIFFICULTY", "exam_level")
    try:
        from pipeline.orchestrator import generate_study_guide

        markdown = generate_study_guide(
            source_text,
            title=title,
            generator_preset=preset or None,
            output_depth=depth or None,
            difficulty=difficulty or None,
            config=config,
        )
        if isinstance(markdown, str) and markdown.strip():
            return markdown, None
        return None, "generation_unavailable"
    except Exception:
        return None, "generation_unavailable"


def main() -> int:
    """Produce a real private OCR-context guide via the existing path and score it.

    Env:
      PRIVATE_OCR_DIR        gitignored/temp dir with 176I's manifest (+176K payload)
      SOURCE_LABEL           closed source label (default "ensemble")
      BASELINE_GUIDE_MD      optional path to the private baseline guide markdown
                             (must live in a gitignored/temp dir)
      INCLUDE_VISIBLE_ASSETS "1" (default) to embed 176K visible assets if present
      GENERATION_PROVIDER    optional preferred existing provider id (local|deepseek|qwen)
      GENERATION_PRESET      generator preset id (default "claude_review")
    """
    private_dir = os.environ.get("PRIVATE_OCR_DIR")
    source_label = os.environ.get("SOURCE_LABEL", SOURCE_LABEL_DEFAULT)
    baseline_md_path = os.environ.get("BASELINE_GUIDE_MD")
    include_visible = os.environ.get("INCLUDE_VISIBLE_ASSETS", "1") == "1"
    preferred_provider = os.environ.get("GENERATION_PROVIDER")

    def blocked(reason: str, *, mode: str = "not_run") -> int:
        summary = build_closed_generation_summary(
            status="blocked",
            source_label=source_label,
            private_ocr_artifact_available=False,
            private_ocr_artifact_gitignored=False,
            generation_mode=mode,
            blocked_by=reason,
            recommended_next_step="blocked",
        )
        print(json.dumps(summary, indent=2))
        return 2

    if not private_dir:
        return blocked("private_artifact_missing")
    if not is_private_artifact_dir(private_dir):
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

    source_text, stats = build_ocr_context_source_text(
        entries, source_label=source_label, visible_payload=visible_payload
    )

    # Persist the private SOURCE material (input) for operator inspection — private only.
    if is_private_artifact_dir(private_dir):
        try:
            with open(os.path.join(private_dir, _GENERATED_SOURCE_FILENAME), "w", encoding="utf-8") as fh:
                fh.write(source_text)
        except Exception:
            pass

    visible_cats = stats.get("visible_asset_categories", [])
    visible_used = (
        visible_assets_token(visible_cats)
        if visible_available
        else ("not_available" if include_visible else "no")
    )

    # Resolve an EXISTING provider/client; honest-block if none is available.
    config, provider_id, provider_error = _resolve_generation_config(preferred_provider)
    if config is None:
        summary = build_closed_generation_summary(
            status="blocked",
            source_label=source_label,
            private_ocr_artifact_available=True,
            private_ocr_artifact_gitignored=True,
            private_visible_artifact_available=visible_available,
            private_visible_artifact_gitignored=visible_available,
            private_generated_guide_written=False,
            private_generated_guide_gitignored=False,
            generation_mode="generation_unavailable",
            visible_assets_used=visible_used,
            selected_visible_asset_categories=visible_cats,
            guide_artifact_status="blocked",
            score_status="not_run",
            baseline_comparison_status="not_run",
            coverage_signal="not_run",
            figure_table_signal="not_run",
            blocked_by=provider_error or "provider_unavailable",
        )
        print(json.dumps(summary, indent=2))
        return 2

    # Run the existing generation path once. A failure is an honest block, never a stub.
    guide_markdown, gen_error = _run_real_generation(
        source_text, title=f"{_safe_label(source_label)} study guide", config=config
    )
    generation_mode = (
        generation_mode_for_provider(provider_id)
        if guide_markdown is not None
        else "generation_unavailable"
    )

    if guide_markdown is None:
        summary = build_closed_generation_summary(
            status="blocked",
            source_label=source_label,
            private_ocr_artifact_available=True,
            private_ocr_artifact_gitignored=True,
            private_visible_artifact_available=visible_available,
            private_visible_artifact_gitignored=visible_available,
            private_generated_guide_written=False,
            private_generated_guide_gitignored=False,
            generation_mode="generation_unavailable",
            visible_assets_used=visible_used,
            selected_visible_asset_categories=visible_cats,
            guide_artifact_status="blocked",
            score_status="not_run",
            baseline_comparison_status="not_run",
            coverage_signal="not_run",
            figure_table_signal="not_run",
            blocked_by=gen_error or "generation_unavailable",
        )
        print(json.dumps(summary, indent=2))
        return 2

    # Write the real generated guide ONLY into the private dir.
    guide_written = False
    if is_private_artifact_dir(private_dir):
        try:
            with open(os.path.join(private_dir, _GENERATED_GUIDE_FILENAME), "w", encoding="utf-8") as fh:
                fh.write(guide_markdown)
            guide_written = bool(guide_markdown.strip())
        except Exception:
            guide_written = False

    # Score the REAL candidate vs the private baseline with the existing contract lint.
    candidate_report = score_guide_markdown(guide_markdown)
    baseline_markdown = _read_private_markdown(baseline_md_path)
    baseline_report = score_guide_markdown(baseline_markdown) if baseline_markdown else None
    signals = derive_baseline_comparison(candidate_report, baseline_report)

    summary = build_closed_generation_summary(
        status="completed" if guide_written else "degraded",
        source_label=source_label,
        private_ocr_artifact_available=True,
        private_ocr_artifact_gitignored=True,
        private_visible_artifact_available=visible_available,
        private_visible_artifact_gitignored=visible_available,
        private_generated_guide_written=guide_written,
        private_generated_guide_gitignored=is_private_artifact_dir(private_dir),
        generation_mode=generation_mode,
        visible_assets_used=visible_used,
        selected_visible_asset_categories=visible_cats,
        guide_artifact_status="generated" if guide_written else "blocked",
        render_status="not_run",
        score_status=signals["score_status"],
        baseline_comparison_status=signals["baseline_comparison_status"],
        coverage_signal=signals["coverage_signal"],
        figure_table_signal=signals["figure_table_signal"],
        # Real generation path → never a stub-vs-full confound.
        stub_vs_full_confounded=False,
        blocked_by="none",
    )
    # Print ONLY the closed summary. The generated guide / source markdown is never printed.
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
