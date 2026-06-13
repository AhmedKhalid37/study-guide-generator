"""Minimal **V4/V5 visual markdown image pilot** (Slice 54), off by default.

The visual stack so far is *advisory only*: a manifest (V1,
``pipeline.visual_assets_manifest``) → scoring (V3, ``visual_asset_scoring``) →
a replacement plan (V3, ``visual_replacement_planner``) → an insertion-position
plan (V3+, ``visual_insertion_planner``). None of those ever touch the guide. This
module is the *first* — and deliberately the *smallest* — step that can actually
put a real figure into a generated guide, and it does so only behind an explicit,
off-by-default flag.

What this slice does and does NOT do
------------------------------------
- Gating is a two-key AND (Slice 55): the global env master switch
  (:func:`is_visual_markdown_pilot_enabled`) **and** an explicit per-job opt-in
  (:func:`is_job_visual_pilot_opt_in`, persisted as ``visual_markdown_image_pilot``)
  must *both* be true. The browser/request can only raise the per-job half; it can
  never bypass the master switch. Either gate off ⇒ byte-identical default output.
- When both gates are on, it inserts **at most one**
  existing ``fitz_local`` ``extracted_figure`` (already cropped to the job's
  ``assets/<slug>.png`` by Slice 40) into the clean Markdown as a *standard
  Markdown image reference* — ``![safe caption](assets/<slug>.png)`` — then hands
  the result to the existing ``JobManager.save_clean_md`` chokepoint and the
  existing PDF/HTML/DOCX renderers. It writes no new image, opens no PDF, calls no
  model/provider/network, and never rewrites a renderer.
- With the flag unset/false it is a **no-op**: it returns the clean Markdown
  unchanged (byte-identical) without reading any artifact, so default guide output
  is exactly as before this slice.
- It is **degrade-never-fail**: any problem (no candidate, unsafe ref, missing
  file, malformed artifact, insertion error) yields the *original* Markdown and a
  closed-vocabulary skip reason — a job never fails because of the pilot.

Candidate rules (narrow on purpose)
-----------------------------------
- Provider ``fitz_local`` only; asset type ``extracted_figure`` only; one maximum.
- Preferred source: a ``visual_replacement_plan.json`` item with
  ``candidate_action == "candidate_include_as_figure"`` whose ``asset_id`` resolves
  to a safe ``extracted_figure`` asset in ``visual_assets_manifest.json``.
- Fallback (flag-on, all safety checks still applied): the first safe ``fitz_local``
  ``extracted_figure`` in the manifest.
- Never Chandra (``chandra_local`` / ``chandra_blocked``), never ``mistral_ocr``,
  never ``page_visual_signal``.

Safety
------
The image reference must be exactly a job-local relative ``assets/<slug>.png``
(``^assets/[A-Za-z0-9_]+\\.png$``) and the file must really exist *inside the job
directory* (symlink escapes are rejected via a realpath containment check).
Absolute paths, ``..``, backslashes, URLs, ``data:``/base64, and non-PNG refs are
all rejected. The caption is a generic, length-limited, Markdown-escaped string
derived from the source page only — no raw caption, OCR text, provider payload,
path, URL, token, image byte, or data URI is ever emitted into the guide.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

ENABLE_ENV = "GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT"

# Slice 62: cautious capped multi-figure pilot. When BOTH gates are on (master env
# switch AND per-job opt-in) the pilot may now insert a *small* number of high-quality
# figures instead of strictly one. The cap is a server-side env integer with a hard
# upper bound of 2 for this slice; the default stays 1 so every existing/un-tuned
# deployment is byte-identical to the single-figure pilot.
MAX_IMAGES_ENV = "GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES"
_DEFAULT_MAX_IMAGES = 1
# Hard upper bound for Slice 62 — no env value can ever push the pilot above this.
_HARD_MAX_IMAGES = 2

# Slice 55: per-job opt-in. The global ``ENABLE_ENV`` master switch is necessary
# but no longer sufficient — a job ALSO has to opt in via this persisted manifest
# flag for any figure to be inserted. Absent / non-true ⇒ False ⇒ byte-identical
# default output even when the master switch is on. The browser/request can only
# *raise* this per job; it can never bypass the env master switch (both AND-gated).
JOB_OPT_IN_KEY = "visual_markdown_image_pilot"

# Provider / asset-type whitelist for this pilot (mirrors the manifest's own closed
# vocab; owned locally so an upstream change cannot widen what the pilot accepts).
SOURCE_PROVIDER_FITZ_LOCAL = "fitz_local"
ASSET_TYPE_EXTRACTED_FIGURE = "extracted_figure"
ACTION_INCLUDE_AS_FIGURE = "candidate_include_as_figure"

# An accepted image reference is ALWAYS a fixed-shape job-local relative path. This
# is the same shape the manifest persists for an extracted figure; anything that
# does not match exactly is rejected, so no absolute / host / traversal / URL /
# data-URI path can ever reach a renderer through this pilot.
_IMAGE_REF_RE = re.compile(r"^assets/[A-Za-z0-9_]+\.png$")

# Slice 56: coarse pre-filter for the pilot's own rendered Markdown image —
# ``![any caption](assets/<slug>.png)``. Only the captured ref is kept, and it is
# then re-validated by :func:`validate_visual_asset_ref` (the real gate), so this
# regex never decides safety on its own; it just locates candidate refs in text.
_MARKDOWN_IMAGE_PILOT_REF_RE = re.compile(r"!\[[^\]]*\]\((assets/[A-Za-z0-9_]+\.png)\)")

# Caption is plain text only: a tiny safe charset, collapsed whitespace, bounded
# length. Everything else is stripped, so a caption can never carry markup, a path,
# a URL, or private text into the guide.
_CAPTION_SAFE_RE = re.compile(r"[^A-Za-z0-9 .,:%()\-]")
_MAX_CAPTION_LEN = 80

# Heading used for the dumb fallback placement when no deterministic source-page
# anchor marker is present in the guide. The singular heading is preserved for the
# one-figure case (byte-identical to the pre-Slice-62 pilot); the plural heading is
# used only when the appended section carries more than one figure (Slice 62).
_VISUAL_REFERENCE_HEADING = "## Visual Reference"
_VISUAL_REFERENCES_HEADING = "## Visual References"

# Deterministic, safe source-page anchor marker convention. When the guide already
# carries ``<!-- visual-anchor: source_page_0003 -->`` for the figure's page, the
# image is placed right at that anchor; otherwise the fallback section is appended.
_ANCHOR_MARKER_TEMPLATE = "<!-- visual-anchor: source_page_{page:04d} -->"

# Closed skip/outcome vocabulary (diagnostic only; never embedded in the guide).
SKIP_DISABLED = "visual_pilot_disabled"
SKIP_JOB_OPT_OUT = "visual_pilot_job_opt_out"
SKIP_CANDIDATE_UNAVAILABLE = "visual_candidate_unavailable"
SKIP_CANDIDATE_UNSAFE = "visual_candidate_unsafe"
# Slice 60: every safe candidate failed the conservative decorative/low-information
# quality gate, so the pilot omits a figure rather than inserting obvious junk.
SKIP_CANDIDATE_LOW_QUALITY = "visual_candidate_low_quality"
SKIP_ASSET_MISSING = "visual_asset_missing"
SKIP_ASSET_PATH_INVALID = "visual_asset_path_invalid"
SKIP_INSERT_FAILED = "visual_markdown_insert_failed"
SKIP_FORMAT_UNSUPPORTED = "visual_format_unsupported"
SKIP_RENDER_DEGRADED = "visual_render_degraded"
STATUS_INSERTED = "visual_inserted"
SKIP_REASONS = {
    SKIP_DISABLED,
    SKIP_JOB_OPT_OUT,
    SKIP_CANDIDATE_UNAVAILABLE,
    SKIP_CANDIDATE_UNSAFE,
    SKIP_CANDIDATE_LOW_QUALITY,
    SKIP_ASSET_MISSING,
    SKIP_ASSET_PATH_INVALID,
    SKIP_INSERT_FAILED,
    SKIP_FORMAT_UNSUPPORTED,
    SKIP_RENDER_DEGRADED,
}

# --- Slice 60: conservative deterministic quality gate -----------------------
#
# Manual operator review found the pilot could select a low-value title-page /
# chapter-title crop when better content figures existed. This gate ranks the
# already-safe ``extracted_figure`` candidates using ONLY already-available
# manifest metadata (source page, bbox, page/crop dimensions) — it never inspects
# private text, OCR text, source contents, or image bytes, and never calls a model.
# It prefers content-bearing figures and avoids decorative title/header/footer/logo/
# banner crops, while degrading safely (no over-rejection) when metadata is sparse.

# Closed quality-reason vocabulary (diagnostic only; never embedded in the guide).
QUALITY_TITLE_PAGE = "quality_title_page"
QUALITY_FULL_PAGE_CROP = "quality_full_page_crop"
QUALITY_BANNER_SHAPE = "quality_banner_shape"
QUALITY_NARROW_SHAPE = "quality_narrow_shape"
QUALITY_SMALL_AREA = "quality_small_area"
QUALITY_TINY_CROP = "quality_tiny_crop"
QUALITY_HEADER_REGION = "quality_header_region"
QUALITY_FOOTER_REGION = "quality_footer_region"
QUALITY_CONTENT_SIZED = "quality_content_sized"
QUALITY_METADATA_SPARSE = "quality_metadata_sparse"
QUALITY_REASONS = {
    QUALITY_TITLE_PAGE,
    QUALITY_FULL_PAGE_CROP,
    QUALITY_BANNER_SHAPE,
    QUALITY_NARROW_SHAPE,
    QUALITY_SMALL_AREA,
    QUALITY_TINY_CROP,
    QUALITY_HEADER_REGION,
    QUALITY_FOOTER_REGION,
    QUALITY_CONTENT_SIZED,
    QUALITY_METADATA_SPARSE,
}
# Deterministic emit order for quality reasons.
_QUALITY_REASON_ORDER = [
    QUALITY_TITLE_PAGE,
    QUALITY_FULL_PAGE_CROP,
    QUALITY_CONTENT_SIZED,
    QUALITY_SMALL_AREA,
    QUALITY_BANNER_SHAPE,
    QUALITY_NARROW_SHAPE,
    QUALITY_HEADER_REGION,
    QUALITY_FOOTER_REGION,
    QUALITY_TINY_CROP,
    QUALITY_METADATA_SPARSE,
]

# Geometry thresholds (conservative; tuned to flag only confident decoration).
_QG_TITLE_PAGE = 1            # page 1 is treated as a likely title/cover page
_QG_FULL_PAGE_RATIO = 0.9     # bbox area / page area at/above this ⇒ full-page crop
_QG_GOOD_AREA_MIN = 0.04      # substantial content figure lower bound
_QG_GOOD_AREA_MAX = 0.85      # below the full-page band
_QG_SMALL_AREA_RATIO = 0.02   # below this ⇒ tiny region
_QG_BANNER_ASPECT = 8.0       # width/height at/above this ⇒ banner-like strip
_QG_NARROW_ASPECT = 0.18      # width/height at/below this ⇒ tall sliver
_QG_EDGE_FRAC = 0.12          # within this fraction of the top/bottom page edge
_QG_EDGE_BAND_FRAC = 0.14     # crop height fraction at/below this ⇒ thin strip
_QG_TINY_PX = 64              # both crop dims at/below this ⇒ logo/icon
_QG_SELECTION_MARGIN = 0.15   # a rival only displaces priority order if clearly better
# Slice 62: a SECOND (or later) figure is only added when it is *confidently*
# content-bearing — its quality score must clear this floor. The base score is 1.0
# and a content-sized figure earns +_QG_CONTENT_BONUS (=1.2); this floor sits just
# below that so a genuine content figure qualifies while a merely-neutral
# (sparse-metadata, 1.0) or penalized (<1.0) candidate never fills the cap and drags
# output quality down. The FIRST/strongest figure is never subject to this floor.
_QG_SECONDARY_MIN_SCORE = 1.15

# Score adjustments (higher score = better). Base score is 1.0.
_QG_TITLE_PENALTY = 0.4
_QG_FULL_PAGE_PENALTY = 0.3
_QG_CONTENT_BONUS = 0.2
_QG_SMALL_AREA_PENALTY = 0.3
_QG_EDGE_PENALTY = 0.2
_QG_BANNER_PENALTY = 0.3
_QG_NARROW_PENALTY = 0.2
_QG_TINY_PENALTY = 0.3
_QG_MAX_SCORE = 1.5

# Placement tokens (diagnostic only).
PLACEMENT_SOURCE_PAGE_ANCHOR = "source_page_anchor"
PLACEMENT_VISUAL_REFERENCE_SECTION = "visual_reference_section"


# --- Flag --------------------------------------------------------------------


def is_visual_markdown_pilot_enabled() -> bool:
    """Whether the off-by-default visual markdown image pilot is turned on.

    Reads ``GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT``. Off unless explicitly
    set to a truthy token, so the default job is byte-identical to before Slice 54.
    """
    return os.getenv(ENABLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def visual_markdown_pilot_max_images() -> int:
    """Effective cap on inserted visual references (Slice 62), in ``[1, 2]``.

    Reads ``GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES``. Only the explicitly supported
    in-range integers ``1`` and ``2`` are honoured; everything else — absent, empty,
    non-integer, ``0``, negative, or larger than the hard upper bound — degrades to the
    safe default ``1`` rather than clamping upward, so a malformed or over-large env
    value can never widen the pilot. The hard upper bound is ``2`` for this slice. Total;
    never raises.
    """
    raw = os.getenv(MAX_IMAGES_ENV, "")
    if not isinstance(raw, str):
        return _DEFAULT_MAX_IMAGES
    raw = raw.strip()
    if not raw:
        return _DEFAULT_MAX_IMAGES
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return _DEFAULT_MAX_IMAGES
    if value < _DEFAULT_MAX_IMAGES or value > _HARD_MAX_IMAGES:
        return _DEFAULT_MAX_IMAGES
    return value


def is_job_visual_pilot_opt_in(job: Any) -> bool:
    """Whether *this job* opted into the visual markdown image pilot (Slice 55).

    Reads the persisted ``visual_markdown_image_pilot`` job option. This is the
    per-job half of the gate; it is only consulted when the global master switch
    (:func:`is_visual_markdown_pilot_enabled`) is already on. Anything other than a
    truthy boolean / token coerces to ``False`` (so a missing key on an
    pre-Slice-55 job, a malformed value, or no manifest all mean "off"). Never
    raises — a read problem degrades to ``False`` (no insertion).
    """
    return _coerce_opt_in(_job_option(job, JOB_OPT_IN_KEY))


# --- Public entry point (degrade-never-fail) ---------------------------------


def apply_visual_markdown_pilot(job: Any, clean_md: Any) -> tuple[str, dict[str, Any]]:
    """Flag-gated, total entry point wired just before ``save_clean_md``.

    Returns ``(markdown, info)``. When the flag is off, or no safe candidate
    exists, or anything goes wrong, the *original* ``clean_md`` is returned
    unchanged together with a closed-vocabulary skip ``info``. Never raises.
    """
    text = clean_md if isinstance(clean_md, str) else ""
    # Both gates are required (AND). The env master switch is checked first so a
    # job opt-in can never enable the pilot on its own; with the switch off the
    # job option is never even read.
    if not is_visual_markdown_pilot_enabled():
        return text, {"status": "skipped", "reason": SKIP_DISABLED}
    if not is_job_visual_pilot_opt_in(job):
        return text, {"status": "skipped", "reason": SKIP_JOB_OPT_OUT}

    try:
        # Slice 62: select up to the server-configured cap (hard-bounded at 2). With the
        # default cap of 1 this returns at most one candidate and the output is identical
        # to the single-figure pilot.
        max_images = visual_markdown_pilot_max_images()
        candidates, reason = _pick_candidates(job, max_images=max_images)
        if not candidates:
            _log(f"Visual markdown pilot: no figure inserted ({reason}).")
            return text, {"status": "skipped", "reason": reason}
        new_text, info = insert_visual_markdown_references(text, candidates)
        if info.get("status") != STATUS_INSERTED:
            _log(f"Visual markdown pilot: no figure inserted ({info.get('reason')}).")
            return text, info
        # Carry the closed-vocabulary quality diagnostics (Slice 60) of the FIRST
        # (strongest) figure on the success info for backward compatibility. These are
        # advisory only and contain no path / text / image bytes.
        first = candidates[0]
        if isinstance(first, dict):
            info["quality_score"] = first.get("quality_score")
            info["quality_reasons"] = first.get("quality_reasons")
        # The single-figure path returns no count; normalize it so every successful
        # insertion advertises a safe integer count (1 or 2).
        info.setdefault("inserted_visual_count", 1)
        count = info.get("inserted_visual_count", 1)
        _log(
            f"Visual markdown pilot: inserted {count} figure(s) "
            f"({info.get('placement')})."
        )
        return new_text, info
    except Exception as exc:  # never let the pilot break a job
        _log(f"Visual markdown pilot skipped ({type(exc).__name__}); job continues.")
        return text, {"status": "skipped", "reason": SKIP_RENDER_DEGRADED}


# --- Candidate selection -----------------------------------------------------


def select_visual_markdown_candidate(
    job: Any,
    *,
    manifest: Any = None,
    replacement_plan: Any = None,
) -> dict[str, Any] | None:
    """Pick at most one safe ``fitz_local`` ``extracted_figure`` candidate, or None.

    ``manifest`` / ``replacement_plan`` may be passed in (already-loaded dicts);
    otherwise they are read from the job's persisted advisory artifacts. The
    preferred source is a replacement-plan ``candidate_include_as_figure`` item
    whose asset resolves safely in the manifest; the fallback is the first safe
    extracted figure in the manifest. Returns a small safe candidate dict (only a
    sanitized asset id, source page, validated relative ref, and generic caption)
    or ``None`` when no safe candidate exists. Pure w.r.t. the inputs; never raises.
    """
    candidate, _reason = _pick_candidate(
        job, manifest=manifest, replacement_plan=replacement_plan
    )
    return candidate


def _collect_ordered_candidates(
    job: Any,
    manifest: Any = None,
    replacement_plan: Any = None,
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], bool, str | None]:
    """Build the priority-ordered, de-duplicated list of *safe* figure candidates.

    Returns ``(ordered, saw_unsafe, err)``. ``ordered`` is a list of
    ``(manifest_asset, built_candidate)`` with replacement-plan preferred items first
    (in plan order), then manifest order, de-duplicated by sanitized asset id. ``err``
    is a closed skip reason set only when the manifest itself is unavailable; otherwise
    ``None`` (an empty ``ordered`` with ``saw_unsafe`` lets the caller distinguish
    unsafe from unavailable). All hard safety gates (``fitz_local`` ``extracted_figure``
    only, safe ``assets/<slug>.png`` ref, real file inside the job dir, never Chandra/
    Mistral/page-signal) are applied here. Pure w.r.t. inputs; never raises.
    """
    manifest_obj = manifest if isinstance(manifest, dict) else _read_json(_path(job, "visual_assets_manifest_json"))
    if not isinstance(manifest_obj, dict):
        return [], False, SKIP_CANDIDATE_UNAVAILABLE

    assets_by_id = _safe_figure_assets(manifest_obj)
    if not assets_by_id:
        return [], False, SKIP_CANDIDATE_UNAVAILABLE

    saw_unsafe = False
    seen_ids: set[str] = set()
    ordered: list[tuple[dict[str, Any], dict[str, Any]]] = []

    plan_obj = replacement_plan if isinstance(replacement_plan, dict) else _read_json(
        _path(job, "visual_replacement_plan_json")
    )
    for asset_id in _plan_figure_asset_ids(plan_obj):
        if asset_id in seen_ids:
            continue
        asset = assets_by_id.get(asset_id)
        if asset is None:
            continue
        built, ok = _build_candidate_from_asset(job, asset, origin="replacement_plan")
        if built is not None:
            seen_ids.add(asset_id)
            ordered.append((asset, built))
        elif not ok:
            saw_unsafe = True

    for asset in _ordered_figure_assets(manifest_obj):
        slug = _safe_slug(asset.get("asset_id"))
        if slug and slug in seen_ids:
            continue
        built, ok = _build_candidate_from_asset(job, asset, origin="manifest")
        if built is not None:
            if slug:
                seen_ids.add(slug)
            ordered.append((asset, built))
        elif not ok:
            saw_unsafe = True

    return ordered, saw_unsafe, None


def _enrich_candidate(candidate: dict[str, Any], quality: dict[str, Any]) -> dict[str, Any]:
    """Copy ``candidate`` with its closed-vocabulary quality diagnostics attached."""
    enriched = dict(candidate)
    enriched["quality_score"] = quality["score"]
    enriched["quality_reasons"] = list(quality["reasons"])
    return enriched


def _best_within_margin(indices: list[int], scored: list[dict[str, Any]]) -> int:
    """Earliest-priority index among those within ``_QG_SELECTION_MARGIN`` of the top score.

    This is the established single-figure selection rule: the highest score wins, but
    priority order (lower index) is preserved on ties and near-ties so a rival only
    displaces it when *clearly* better. ``indices`` must be non-empty.
    """
    top = max(scored[i]["score"] for i in indices)
    contenders = [i for i in indices if top - scored[i]["score"] <= _QG_SELECTION_MARGIN]
    return min(contenders)


def _pick_candidate(
    job: Any,
    *,
    manifest: Any = None,
    replacement_plan: Any = None,
) -> tuple[dict[str, Any] | None, str]:
    """Selection core returning ``(candidate_or_None, closed_reason)``.

    Slice 60: all hard safety gates are unchanged (``fitz_local`` ``extracted_figure``
    only, safe ``assets/<slug>.png`` ref, real file inside the job dir, never Chandra/
    Mistral/page-signal). On top of those, the *safe* candidates are now ranked by a
    conservative deterministic quality gate so a content figure beats a decorative
    title/header/footer/logo/banner crop, and a set of only-decorative candidates
    omits rather than inserts junk. Priority order (replacement-plan first, then
    manifest order) is preserved on ties / near-ties. (Slice 62 keeps this single-best
    selector for ``select_visual_markdown_candidate``; the pilot now uses the plural
    :func:`_pick_candidates`, whose first pick is identical to this one.)
    """
    ordered, saw_unsafe, err = _collect_ordered_candidates(job, manifest, replacement_plan)
    if err is not None:
        return None, err
    if not ordered:
        return None, (SKIP_CANDIDATE_UNSAFE if saw_unsafe else SKIP_CANDIDATE_UNAVAILABLE)

    # Quality gate: score each safe candidate, drop hard-decorative ones, and pick
    # the best of the rest (priority order wins unless a rival is clearly better).
    scored = [score_visual_markdown_candidate_for_pilot(asset) for asset, _ in ordered]
    accepted = [i for i, q in enumerate(scored) if not q["decorative"]]
    if not accepted:
        return None, SKIP_CANDIDATE_LOW_QUALITY

    chosen = _best_within_margin(accepted, scored)
    _asset, candidate = ordered[chosen]
    return _enrich_candidate(candidate, scored[chosen]), STATUS_INSERTED


def _coerce_max_images(max_images: Any) -> int:
    """Clamp an arbitrary ``max_images`` into ``[1, _HARD_MAX_IMAGES]`` (default 1)."""
    if isinstance(max_images, bool) or not isinstance(max_images, int):
        return _DEFAULT_MAX_IMAGES
    if max_images < _DEFAULT_MAX_IMAGES:
        return _DEFAULT_MAX_IMAGES
    if max_images > _HARD_MAX_IMAGES:
        return _HARD_MAX_IMAGES
    return max_images


def select_visual_markdown_candidates(
    job: Any,
    *,
    max_images: int = _DEFAULT_MAX_IMAGES,
    manifest: Any = None,
    replacement_plan: Any = None,
) -> list[dict[str, Any]]:
    """Pick up to ``max_images`` safe figure candidates (Slice 62), strongest first.

    A capped, cautious generalization of :func:`select_visual_markdown_candidate`. The
    cap is clamped into ``[1, 2]``. Returns a list (possibly empty) of safe candidate
    dicts; the first is the single-best pick (identical to the singular selector). Pure
    w.r.t. inputs; never raises.
    """
    candidates, _reason = _pick_candidates(
        job, max_images=max_images, manifest=manifest, replacement_plan=replacement_plan
    )
    return candidates


def _pick_candidates(
    job: Any,
    *,
    max_images: int = _DEFAULT_MAX_IMAGES,
    manifest: Any = None,
    replacement_plan: Any = None,
) -> tuple[list[dict[str, Any]], str]:
    """Capped multi-figure selection core returning ``(candidates, closed_reason)``.

    The first pick is byte-for-byte the same decision as :func:`_pick_candidate`. When
    the clamped cap is ``> 1``, additional figures are appended subject to the Slice 62
    caution rules: each must be non-decorative AND clear the secondary quality floor,
    must not duplicate an already-selected asset id or ref, and a *different* source
    page is preferred (two figures from the same page only when no better alternative
    exists). The strongest figure stays first. Never raises.
    """
    cap = _coerce_max_images(max_images)
    ordered, saw_unsafe, err = _collect_ordered_candidates(job, manifest, replacement_plan)
    if err is not None:
        return [], err
    if not ordered:
        return [], (SKIP_CANDIDATE_UNSAFE if saw_unsafe else SKIP_CANDIDATE_UNAVAILABLE)

    scored = [score_visual_markdown_candidate_for_pilot(asset) for asset, _ in ordered]
    accepted = [i for i, q in enumerate(scored) if not q["decorative"]]
    if not accepted:
        return [], SKIP_CANDIDATE_LOW_QUALITY

    chosen_indices = _select_multi(ordered, scored, accepted, cap)
    return [_enrich_candidate(ordered[i][1], scored[i]) for i in chosen_indices], STATUS_INSERTED


def _select_multi(
    ordered: list[tuple[dict[str, Any], dict[str, Any]]],
    scored: list[dict[str, Any]],
    accepted: list[int],
    cap: int,
) -> list[int]:
    """Choose up to ``cap`` candidate indices, strongest first, with Slice 62 rules.

    The first index is the established single-best pick (priority preserved on near
    ties). Each subsequent index must clear the secondary quality floor and avoid
    duplicate asset ids / refs; a distinct source page is preferred, falling back to a
    same-page figure only when no distinct-page candidate qualifies. ``accepted`` is
    non-empty; the returned list preserves selection order (strongest first).
    """
    selected: list[int] = []
    selected_pages: set[int] = set()
    selected_refs: set[str] = set()
    selected_ids: set[str] = set()

    def _take(index: int) -> None:
        candidate = ordered[index][1]
        selected.append(index)
        ref = candidate.get("asset_ref")
        asset_id = candidate.get("asset_id")
        if isinstance(ref, str):
            selected_refs.add(ref)
        if isinstance(asset_id, str):
            selected_ids.add(asset_id)
        page = candidate.get("source_page")
        if isinstance(page, int) and page > 0:
            selected_pages.add(page)

    def _eligible(index: int, *, prefer_distinct: bool) -> bool:
        if index in selected:
            return False
        if scored[index]["score"] < _QG_SECONDARY_MIN_SCORE:
            return False
        candidate = ordered[index][1]
        ref = candidate.get("asset_ref")
        asset_id = candidate.get("asset_id")
        if isinstance(ref, str) and ref in selected_refs:
            return False
        if isinstance(asset_id, str) and asset_id in selected_ids:
            return False
        page = candidate.get("source_page")
        if prefer_distinct and isinstance(page, int) and page > 0 and page in selected_pages:
            return False
        return True

    # First figure: the single-best pick (no secondary floor — the strongest stands
    # on its own even if it is only neutral quality).
    _take(_best_within_margin(accepted, scored))

    # Subsequent figures, up to the cap: prefer a distinct page; only fall back to a
    # same-page figure when no distinct-page candidate qualifies.
    while len(selected) < cap:
        pool = [i for i in accepted if _eligible(i, prefer_distinct=True)]
        if not pool:
            pool = [i for i in accepted if _eligible(i, prefer_distinct=False)]
        if not pool:
            break
        _take(_best_within_margin(pool, scored))

    return selected


# --- Slice 60: deterministic quality scoring (metadata-only, never raises) ----


def score_visual_markdown_candidate_for_pilot(asset: Any) -> dict[str, Any]:
    """Assess one ``extracted_figure`` asset's quality from manifest metadata only.

    Returns ``{"score": float, "decorative": bool, "reasons": [closed tokens]}``.
    ``score`` is higher-is-better (base ``1.0``); ``decorative`` is True only when the
    metadata makes it *confident* the crop is a logo/header/footer/title-page chrome
    (those are dropped before selection). Uses solely already-sanitized fields —
    ``source_page``, ``bbox``, and the ``signals`` page/crop dimensions — and never
    reads private text, OCR text, captions, or image bytes, and never raises. When the
    geometry/size metadata is absent it degrades to a neutral, non-decorative score so
    a perfectly good figure with sparse metadata is never over-rejected.
    """
    reasons: list[str] = []
    score = 1.0
    decorative = False
    if not isinstance(asset, dict):
        return {"score": 0.0, "decorative": True, "reasons": [QUALITY_METADATA_SPARSE]}

    page = _safe_page(asset.get("source_page"))
    bbox = _quality_bbox(asset.get("bbox"))
    raw_signals = asset.get("signals")
    signals = raw_signals if isinstance(raw_signals, dict) else {}
    page_w = _quality_dim(signals.get("page_width"))
    page_h = _quality_dim(signals.get("page_height"))
    crop_w = _quality_dim(signals.get("crop_width_px"))
    crop_h = _quality_dim(signals.get("crop_height_px"))

    have_geometry = bbox is not None and page_w is not None and page_h is not None
    have_crop_px = crop_w is not None and crop_h is not None

    if page == _QG_TITLE_PAGE:
        reasons.append(QUALITY_TITLE_PAGE)
        score -= _QG_TITLE_PENALTY

    aspect: float | None = None
    if have_geometry:
        x0, y0, x1, y1 = bbox  # type: ignore[misc]
        box_w = x1 - x0
        box_h = y1 - y0
        page_area = page_w * page_h  # type: ignore[operator]
        area_ratio = (box_w * box_h) / page_area if page_area > 0 else 0.0
        aspect = (box_w / box_h) if box_h > 0 else None
        top_frac = y0 / page_h  # type: ignore[operator]
        bottom_frac = y1 / page_h  # type: ignore[operator]
        height_frac = box_h / page_h  # type: ignore[operator]
        thin_edge_strip = height_frac <= _QG_EDGE_BAND_FRAC and (
            top_frac <= _QG_EDGE_FRAC or bottom_frac >= 1.0 - _QG_EDGE_FRAC
        )

        if area_ratio >= _QG_FULL_PAGE_RATIO:
            reasons.append(QUALITY_FULL_PAGE_CROP)
            score -= _QG_FULL_PAGE_PENALTY
            if page == _QG_TITLE_PAGE:
                decorative = True  # a full-page crop on the title page is chrome
        elif _QG_GOOD_AREA_MIN <= area_ratio <= _QG_GOOD_AREA_MAX and not thin_edge_strip:
            reasons.append(QUALITY_CONTENT_SIZED)
            score += _QG_CONTENT_BONUS
        elif area_ratio < _QG_SMALL_AREA_RATIO:
            reasons.append(QUALITY_SMALL_AREA)
            score -= _QG_SMALL_AREA_PENALTY

        # A thin strip hugging the top/bottom edge is header/footer decoration.
        if thin_edge_strip:
            at_top = top_frac <= _QG_EDGE_FRAC
            reasons.append(QUALITY_HEADER_REGION if at_top else QUALITY_FOOTER_REGION)
            score -= _QG_EDGE_PENALTY
            if aspect is not None and aspect >= _QG_BANNER_ASPECT:
                decorative = True  # a wide thin strip at the page edge is a banner

    # Fall back to pixel aspect when there is no usable bbox geometry.
    if aspect is None and have_crop_px and crop_h > 0:  # type: ignore[operator]
        aspect = crop_w / crop_h  # type: ignore[operator]
    if aspect is not None:
        if aspect >= _QG_BANNER_ASPECT and QUALITY_BANNER_SHAPE not in reasons:
            reasons.append(QUALITY_BANNER_SHAPE)
            score -= _QG_BANNER_PENALTY
        elif aspect <= _QG_NARROW_ASPECT:
            reasons.append(QUALITY_NARROW_SHAPE)
            score -= _QG_NARROW_PENALTY

    # A crop that is small in BOTH pixel dimensions is a logo/icon — confident junk.
    if have_crop_px and crop_w <= _QG_TINY_PX and crop_h <= _QG_TINY_PX:  # type: ignore[operator]
        reasons.append(QUALITY_TINY_CROP)
        score -= _QG_TINY_PENALTY
        decorative = True

    if not have_geometry and not have_crop_px:
        reasons.append(QUALITY_METADATA_SPARSE)

    return {
        "score": round(_clamp_quality(score), 3),
        "decorative": decorative,
        "reasons": _ordered_quality_reasons(reasons),
    }


def is_decorative_visual_candidate(asset: Any) -> bool:
    """True iff the quality gate is confident this figure asset is decorative chrome."""
    return bool(score_visual_markdown_candidate_for_pilot(asset)["decorative"])


def rank_visual_markdown_candidates(assets: Any) -> int | None:
    """Index of the best figure asset to insert from a priority-ordered list, or None.

    ``assets`` is an ordered list (highest a-priori priority first) of manifest
    ``extracted_figure`` asset dicts. Hard-decorative candidates are dropped; among
    the rest the highest quality score wins, but priority order is preserved on ties
    and near-ties (a rival only displaces it when clearly better). Returns ``None``
    when the input is empty/invalid or every candidate is hard-decorative. Pure and
    total: never mutates the input and never raises.
    """
    if not isinstance(assets, list) or not assets:
        return None
    scored = [score_visual_markdown_candidate_for_pilot(a) for a in assets]
    accepted = [i for i, q in enumerate(scored) if not q["decorative"]]
    if not accepted:
        return None
    top = max(scored[i]["score"] for i in accepted)
    contenders = [i for i in accepted if top - scored[i]["score"] <= _QG_SELECTION_MARGIN]
    return min(contenders)


def _quality_bbox(value: Any) -> list[float] | None:
    """Coerce a bbox to a well-ordered ``[x0, y0, x1, y1]`` of finite floats, or None."""
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    coords: list[float] = []
    for item in value:
        if isinstance(item, bool):
            return None
        try:
            number = float(item)
        except (TypeError, ValueError):
            return None
        if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
            return None
        coords.append(number)
    x0, y0, x1, y1 = coords
    if x1 <= x0 or y1 <= y0:
        return None
    return [x0, y0, x1, y1]


def _quality_dim(value: Any) -> float | None:
    """Coerce a positive finite dimension (page/crop size), else None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return number if number > 0 else None


def _clamp_quality(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > _QG_MAX_SCORE:
        return _QG_MAX_SCORE
    return value


def _ordered_quality_reasons(tokens: list[str]) -> list[str]:
    present = {t for t in tokens if t in QUALITY_REASONS}
    return [t for t in _QUALITY_REASON_ORDER if t in present]


def _build_candidate_from_asset(
    job: Any, asset: Any, *, origin: str
) -> tuple[dict[str, Any] | None, bool]:
    """Validate one manifest asset → safe candidate dict. Returns ``(candidate, ok)``.

    ``ok`` is False only when the asset *looked* like a figure but failed a safety
    gate (used to distinguish "unsafe" from "unavailable" for diagnostics).
    """
    if not _is_pilot_eligible_asset(asset):
        return None, True
    asset_ref = validate_visual_asset_ref(asset.get("image_ref"))
    if asset_ref is None:
        return None, False
    if not _asset_file_ok(job, asset_ref):
        return None, False
    source_page = _safe_page(asset.get("source_page"))
    return (
        {
            "asset_id": _safe_slug(asset.get("asset_id")) or "figure",
            "source_page": source_page,
            "asset_ref": asset_ref,
            "caption": _safe_caption(asset.get("caption"), source_page),
            "origin": origin if origin in {"replacement_plan", "manifest"} else "manifest",
        },
        True,
    )


def _is_pilot_eligible_asset(asset: Any) -> bool:
    """True only for a non-Chandra ``fitz_local`` ``extracted_figure`` asset."""
    if not isinstance(asset, dict):
        return False
    if asset.get("source_provider") != SOURCE_PROVIDER_FITZ_LOCAL:
        return False
    if asset.get("asset_type") != ASSET_TYPE_EXTRACTED_FIGURE:
        return False
    reasons = asset.get("reasons")
    if isinstance(reasons, list) and "chandra_blocked" in reasons:
        return False
    return True


def _safe_figure_assets(manifest_obj: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map ``{sanitized_asset_id: asset}`` for pilot-eligible figure assets."""
    out: dict[str, dict[str, Any]] = {}
    for asset in _ordered_figure_assets(manifest_obj):
        slug = _safe_slug(asset.get("asset_id"))
        if slug:
            out.setdefault(slug, asset)
    return out


def _ordered_figure_assets(manifest_obj: dict[str, Any]) -> list[dict[str, Any]]:
    assets = manifest_obj.get("assets")
    if not isinstance(assets, list):
        return []
    return [a for a in assets if _is_pilot_eligible_asset(a)]


def _plan_figure_asset_ids(plan_obj: Any) -> list[str]:
    """Sanitized asset ids of plan items recommending include-as-figure (fitz_local)."""
    if not isinstance(plan_obj, dict) or plan_obj.get("status") != "completed":
        return []
    items = plan_obj.get("items")
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("candidate_action") != ACTION_INCLUDE_AS_FIGURE:
            continue
        if item.get("source_provider") != SOURCE_PROVIDER_FITZ_LOCAL:
            continue
        if item.get("asset_type") != ASSET_TYPE_EXTRACTED_FIGURE:
            continue
        reasons = item.get("reasons")
        if isinstance(reasons, list) and "chandra_blocked" in reasons:
            continue
        slug = _safe_slug(item.get("asset_id"))
        if slug:
            out.append(slug)
    return out


# --- Path / asset validation -------------------------------------------------


def validate_visual_asset_ref(asset_ref: Any) -> str | None:
    """Return ``asset_ref`` iff it is exactly a job-local ``assets/<slug>.png``.

    Rejects (returns ``None`` for) absolute paths, ``..`` traversal, backslashes,
    URL-like refs, ``data:``/base64 refs, and any non-PNG path. String-only — the
    on-disk existence / containment check lives in :func:`_asset_file_ok`.
    """
    if not isinstance(asset_ref, str):
        return None
    ref = asset_ref.strip()
    if not ref or "\\" in ref or ".." in ref or "://" in ref:
        return None
    if ref.startswith("/") or ref.lower().startswith("data:"):
        return None
    return ref if _IMAGE_REF_RE.match(ref) else None


def _asset_file_ok(job: Any, asset_ref: str) -> bool:
    """True iff ``asset_ref`` resolves to a real file *inside* the job directory.

    Uses realpath containment so a symlink that escapes the job directory is
    rejected even though the relative ref itself looked safe.
    """
    try:
        job_dir = os.path.realpath(str(_job_dir(job)))
        target = os.path.realpath(os.path.join(job_dir, asset_ref))
    except Exception:
        return False
    if target != job_dir and not target.startswith(job_dir + os.sep):
        return False
    return os.path.isfile(target)


# --- Slice 56: export ride-along detection -----------------------------------


def extract_visual_pilot_asset_refs(markdown_text: Any) -> list[str]:
    """All distinct safe pilot asset refs referenced as Markdown images in *text*.

    Pure / string-only. Scans for ``![...](assets/<slug>.png)`` and keeps only refs
    that pass :func:`validate_visual_asset_ref` — i.e. exactly the fixed-shape
    job-local ``assets/<slug>.png`` (no absolute path, ``..``, backslash, URL,
    ``data:`` / base64, or non-PNG). Order-preserving and de-duplicated. Never
    raises; a non-string or unparsable input yields ``[]``. This only *locates*
    refs in text — it never opens, reads, or logs the referenced files.
    """
    if not isinstance(markdown_text, str) or not markdown_text:
        return []
    seen: set[str] = set()
    refs: list[str] = []
    for match in _MARKDOWN_IMAGE_PILOT_REF_RE.finditer(markdown_text):
        ref = validate_visual_asset_ref(match.group(1))
        if ref and ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


def find_exportable_visual_pilot_assets(job: Any) -> list[str]:
    """The safe job-local pilot PNG refs to ride along in an export bundle (Slice 62).

    Reads this job's ``clean.md`` (read-only), collects every Markdown image whose
    target is a safe ``assets/<slug>.png`` ref that really exists *inside* the job
    directory (realpath containment, a regular file — symlink escapes are rejected),
    de-duplicated and order-preserving, and capped at ``_HARD_MAX_IMAGES`` (2) as an
    absolute safety bound. Returns ``[]`` when there is no clean.md, no safe reference,
    or every referenced file is missing / unsafe. Never raises and never opens / reads
    / logs image bytes — it only confirms each file's existence and containment.
    """
    text = _read_text(getattr(job, "clean_md", None))
    if text is None:
        return []
    out: list[str] = []
    for ref in extract_visual_pilot_asset_refs(text):
        if _asset_file_ok(job, ref):
            out.append(ref)
            if len(out) >= _HARD_MAX_IMAGES:
                break
    return out


def find_exportable_visual_pilot_asset(job: Any) -> str | None:
    """The single safe job-local pilot PNG ref to ride along in an export bundle.

    Backward-compatible singular wrapper over :func:`find_exportable_visual_pilot_assets`
    — returns the FIRST safe, present, contained ref or ``None``. Never raises.
    """
    refs = find_exportable_visual_pilot_assets(job)
    return refs[0] if refs else None


# --- Markdown building / insertion -------------------------------------------


def build_visual_markdown_image(candidate: Any) -> str:
    """Build a single standard Markdown image reference from a safe candidate.

    The reference is ``![caption](assets/<slug>.png)``. The ref is re-validated
    here (defence in depth) and the caption is re-sanitized + Markdown-escaped, so
    even a hand-built candidate cannot smuggle an unsafe path or markup into the
    guide. Raises ``ValueError`` if the candidate has no valid relative ref.
    """
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be a dict")
    ref = validate_visual_asset_ref(candidate.get("asset_ref"))
    if ref is None:
        raise ValueError("candidate has no valid asset_ref")
    caption = _safe_caption(candidate.get("caption"), _safe_page(candidate.get("source_page")))
    return f"![{caption}]({ref})"


def insert_visual_markdown_reference(
    clean_md: Any, candidate: Any
) -> tuple[str, dict[str, Any]]:
    """Insert exactly one Markdown image into ``clean_md`` for ``candidate``.

    Placement is intentionally dumb: if the guide carries a deterministic
    ``<!-- visual-anchor: source_page_NNNN -->`` marker for the figure's page, the
    image is placed at that anchor; otherwise a single trailing
    ``## Visual Reference`` section is appended. Returns ``(markdown, info)``; on any
    failure it returns the original text with a closed-vocabulary skip reason.
    """
    text = clean_md if isinstance(clean_md, str) else ""
    try:
        image_md = build_visual_markdown_image(candidate)
    except Exception:
        return text, {"status": "skipped", "reason": SKIP_INSERT_FAILED}

    try:
        source_page = _safe_page(candidate.get("source_page")) if isinstance(candidate, dict) else 0
        anchor = _ANCHOR_MARKER_TEMPLATE.format(page=source_page) if source_page > 0 else None
        if anchor and anchor in text:
            new_text = _insert_after_marker(text, anchor, image_md)
            placement = PLACEMENT_SOURCE_PAGE_ANCHOR
        else:
            new_text = _append_visual_reference_section(text, image_md)
            placement = PLACEMENT_VISUAL_REFERENCE_SECTION
    except Exception:
        return text, {"status": "skipped", "reason": SKIP_INSERT_FAILED}

    return new_text, {
        "status": STATUS_INSERTED,
        "asset_id": candidate.get("asset_id") if isinstance(candidate, dict) else None,
        "asset_ref": candidate.get("asset_ref") if isinstance(candidate, dict) else None,
        "placement": placement,
    }


def insert_visual_markdown_references(
    clean_md: Any, candidates: Any
) -> tuple[str, dict[str, Any]]:
    """Insert up to a handful of Markdown images into ``clean_md`` (Slice 62).

    With exactly one candidate this delegates to :func:`insert_visual_markdown_reference`
    so the single-figure output is byte-identical to the pre-Slice-62 pilot. With more
    than one, each figure with a deterministic ``<!-- visual-anchor: source_page_NNNN -->``
    marker present in the guide is placed at that anchor (in selection order); the rest
    are appended together under a single trailing ``## Visual References`` section. The
    strongest figure stays first. Returns ``(markdown, info)``; on total failure it
    returns the original text with a closed-vocabulary skip reason. Never raises.
    """
    text = clean_md if isinstance(clean_md, str) else ""
    if not isinstance(candidates, list) or not candidates:
        return text, {"status": "skipped", "reason": SKIP_CANDIDATE_UNAVAILABLE}
    if len(candidates) == 1:
        return insert_visual_markdown_reference(text, candidates[0])

    # Build a validated image-markdown for each candidate up front (defence in depth:
    # a candidate whose ref/caption cannot be rebuilt safely is dropped here).
    prepared: list[tuple[dict[str, Any], str, int]] = []
    for candidate in candidates:
        try:
            image_md = build_visual_markdown_image(candidate)
        except Exception:
            continue
        page = _safe_page(candidate.get("source_page")) if isinstance(candidate, dict) else 0
        prepared.append((candidate, image_md, page))

    if not prepared:
        return text, {"status": "skipped", "reason": SKIP_INSERT_FAILED}
    if len(prepared) == 1:
        return insert_visual_markdown_reference(text, prepared[0][0])

    try:
        new_text = text
        inserted_assets: list[dict[str, Any]] = []
        deferred: list[tuple[dict[str, Any], str]] = []
        for candidate, image_md, page in prepared:
            anchor = _ANCHOR_MARKER_TEMPLATE.format(page=page) if page > 0 else None
            if anchor and _has_anchor_line(new_text, anchor):
                new_text = _insert_after_marker(new_text, anchor, image_md)
                inserted_assets.append(_asset_info(candidate, PLACEMENT_SOURCE_PAGE_ANCHOR))
            else:
                deferred.append((candidate, image_md))
        if deferred:
            new_text = _append_visual_references_section(
                new_text, [image_md for _c, image_md in deferred]
            )
            for candidate, _image_md in deferred:
                inserted_assets.append(_asset_info(candidate, PLACEMENT_VISUAL_REFERENCE_SECTION))
    except Exception:
        return text, {"status": "skipped", "reason": SKIP_INSERT_FAILED}

    if not inserted_assets:
        return text, {"status": "skipped", "reason": SKIP_INSERT_FAILED}

    first = inserted_assets[0]
    return new_text, {
        "status": STATUS_INSERTED,
        "asset_id": first.get("asset_id"),
        "asset_ref": first.get("asset_ref"),
        "placement": first.get("placement"),
        "inserted_visual_count": len(inserted_assets),
        "inserted_assets": inserted_assets,
    }


def _asset_info(candidate: Any, placement: str) -> dict[str, Any]:
    """A small, safe per-figure diagnostic record (no path / text / image bytes)."""
    if not isinstance(candidate, dict):
        return {"asset_id": None, "asset_ref": None, "source_page": 0, "placement": placement,
                "quality_score": None, "quality_reasons": None}
    reasons = candidate.get("quality_reasons")
    return {
        "asset_id": candidate.get("asset_id"),
        "asset_ref": candidate.get("asset_ref"),
        "source_page": _safe_page(candidate.get("source_page")),
        "placement": placement,
        "quality_score": candidate.get("quality_score"),
        "quality_reasons": list(reasons) if isinstance(reasons, list) else None,
    }


def _has_anchor_line(text: str, marker: str) -> bool:
    """True iff some line of ``text`` is exactly ``marker`` (a full-line anchor comment)."""
    return any(line.strip() == marker for line in text.splitlines())


def _insert_after_marker(text: str, marker: str, image_md: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and line.strip() == marker:
            out.append("")
            out.append(image_md)
            inserted = True
    if not inserted:  # marker only matched as a substring; fall back safely
        return _append_visual_reference_section(text, image_md)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _append_visual_reference_section(text: str, image_md: str) -> str:
    body = text.rstrip("\n")
    section = f"{_VISUAL_REFERENCE_HEADING}\n\n{image_md}\n"
    if not body:
        return section
    return f"{body}\n\n{section}"


def _append_visual_references_section(text: str, images: list[str]) -> str:
    """Append one or more images under a single trailing visual-references section.

    Uses the singular ``## Visual Reference`` heading for one image (byte-identical to
    the legacy single-figure section) and the plural ``## Visual References`` heading
    for more than one. Images are separated by a blank line, in the given order.
    """
    if len(images) == 1:
        return _append_visual_reference_section(text, images[0])
    body = text.rstrip("\n")
    block = "\n\n".join(images)
    section = f"{_VISUAL_REFERENCES_HEADING}\n\n{block}\n"
    if not body:
        return section
    return f"{body}\n\n{section}"


# --- Small safe coercers -----------------------------------------------------


def _safe_caption(raw: Any, source_page: int) -> str:
    """A short, safe, Markdown-escapable caption.

    Prefers a sanitized version of ``raw`` only when it survives a strict safe-char
    filter and stays non-empty; otherwise (the normal case — manifest captions are
    ``None``) a generic page-derived caption is used. The result contains only the
    safe charset, so it carries no markup, path, URL, or private text.
    """
    generic = (
        f"Extracted figure from source page {source_page}"
        if source_page and source_page > 0
        else "Extracted figure"
    )
    if not isinstance(raw, str):
        return generic
    cleaned = _CAPTION_SAFE_RE.sub(" ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return generic
    return cleaned[:_MAX_CAPTION_LEN].strip()


def _safe_slug(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    slug = re.sub(r"[^A-Za-z0-9_]", "", value)[:64]
    return slug or None


def _safe_page(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        page = int(value)
    except (TypeError, ValueError):
        return 0
    return page if page > 0 else 0


# --- Job-shape access (duck-typed, total) ------------------------------------


def _job_option(job: Any, key: str) -> Any:
    """Read a persisted job option (Slice 55), total and side-effect-free.

    Prefers the persisted manifest (a real ``JobManager.Job`` exposes
    ``read_manifest()``); falls back to a direct attribute for synthetic/test job
    objects. Never raises and never mutates the job — a missing key or any read
    problem yields ``None`` (which :func:`_coerce_opt_in` treats as off).
    """
    reader = getattr(job, "read_manifest", None)
    if callable(reader):
        try:
            manifest = reader()
            if isinstance(manifest, dict) and key in manifest:
                return manifest.get(key)
        except Exception:
            pass
    return getattr(job, key, None)


def _coerce_opt_in(value: Any) -> bool:
    """Coerce a stored opt-in value to a strict bool (default False).

    Accepts a real ``True`` or a truthy string token only; everything else —
    ``None``, ``False``, numbers, other strings, arbitrary objects — is False. This
    is deliberately conservative so a malformed/unexpected value can never turn the
    pilot on.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _path(job: Any, attr: str):
    return getattr(job, attr, None)


def _job_dir(job: Any):
    return getattr(job, "dir", None)


def _read_json(path: Any) -> Any:
    if path is None:
        return None
    try:
        p = os.fspath(path)
    except TypeError:
        return None
    try:
        if not os.path.isfile(p):
            return None
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _read_text(path: Any) -> str | None:
    """Read a UTF-8 text file (e.g. clean.md) read-only; never raises (Slice 56).

    Returns the file contents, or ``None`` if the path is empty, not a real file,
    or unreadable. Used only to scan Markdown for safe asset refs — it never reads
    or returns image bytes.
    """
    if path is None:
        return None
    try:
        p = os.fspath(path)
    except TypeError:
        return None
    try:
        if not os.path.isfile(p):
            return None
        with open(p, "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return None


def _log(message: str) -> None:
    # Closed-vocabulary, path-free diagnostics only; never echoes asset content.
    print(message, file=sys.stderr)
