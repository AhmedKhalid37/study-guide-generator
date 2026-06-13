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

# Slice 74: a small, safe italic caption line placed *below* an inserted visual.
# It carries ONLY a fixed generic phrase plus the (already-bounded, integer)
# source page number when available — never a source filename, path, title, raw
# manifest caption, OCR/document/extracted-table text, or any private content.
# The image alt text (built by :func:`build_visual_markdown_image`) is unchanged;
# this is an additional readable line for the reader, not a new image ref.
_VISUAL_CAPTION_WITH_PAGE = "*Source visual, page {page}.*"
_VISUAL_CAPTION_GENERIC = "*Source visual.*"

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


# --- Slice 64: deterministic visual-TYPE prioritization (pixel-only, never raises) ---
#
# Slice 63's cap-2 operator validation passed the plumbing but selected *tables only*.
# Tables are useful yet frequently reconstructable from extracted text into clean
# generated Markdown/HTML tables; the higher-value reason to embed a source visual is to
# preserve diagrams/flowcharts/screenshots/labeled figures/network maps and other graphics
# an LLM cannot reliably recreate. Slice 64 adds a conservative, deterministic visual-TYPE
# classifier so, when quality is otherwise acceptable, a hard-to-reconstruct diagram/figure
# is preferred over a reconstructable table — while a good table is still selected when it
# is the best/only useful visual.
#
# The classifier reads ONLY the already-safe, already-job-dir-contained ``assets/<slug>.png``
# crop (the same file the Slice 60 gate already validated), computes a handful of bounded,
# non-sensitive summary features (size, aspect, blank ratio, horizontal/vertical rule counts,
# rough edge density), and returns a closed-vocabulary token. It never OCRs the crop, never
# calls a model/provider/network, never base64/serializes/logs image bytes, never records a
# path or source text, and adds no artifact. If Pillow is unavailable, the crop is unreadable,
# or it is too small to analyze, it degrades to ``unknown`` and the prior (Slice 60/62)
# quality-only selection behavior is preserved.

# Closed visual-type vocabulary (diagnostic only; never embedded in the guide).
VISUAL_TYPE_DIAGRAM = "diagram_or_figure"
VISUAL_TYPE_TABLE = "reconstructable_table"
VISUAL_TYPE_DECORATIVE = "decorative_or_low_information"
VISUAL_TYPE_UNKNOWN = "unknown"
VISUAL_TYPES = {
    VISUAL_TYPE_DIAGRAM,
    VISUAL_TYPE_TABLE,
    VISUAL_TYPE_DECORATIVE,
    VISUAL_TYPE_UNKNOWN,
}
# Preferred order when quality is otherwise acceptable:
#   diagram_or_figure > reconstructable_table > unknown > decorative_or_low_information
_VISUAL_TYPE_PRIORITY = {
    VISUAL_TYPE_DIAGRAM: 3,
    VISUAL_TYPE_TABLE: 2,
    VISUAL_TYPE_UNKNOWN: 1,
    VISUAL_TYPE_DECORATIVE: 0,
}

# Visual-type analysis thresholds (conservative; tuned to act only when the distinction
# is clear, never to "solve" computer vision). All bounded; no value is sensitive.
_VT_MIN_ANALYZE_DIM = 24     # below this (either original dim) ⇒ too small ⇒ unknown
_VT_MAX_DIM = 160            # bounded downscale cap for cheap pure-Python analysis
_VT_DARK = 110               # grayscale value below this counts as "ink" (line/shape)
_VT_LIGHT = 235              # grayscale value above this counts as near-white background
_VT_LINE_FRAC = 0.5          # row/col with ≥ this fraction of ink counts as a full rule
_VT_GRID_MIN_LINES = 3       # ≥ this many horizontal AND vertical rules ⇒ table-like grid
_VT_EDGE_DELTA = 40          # adjacent-pixel |Δ| at/above this counts as an edge
_VT_EDGE_MIN = 0.03          # edge fraction at/above this ⇒ meaningful graphic content
_VT_BLANK_MAX = 0.92         # near-white fraction at/above this (and low edges) ⇒ low-info
_VT_BANNER_ASPECT = 8.0      # width/height at/above this with low edges ⇒ decorative strip
_VT_NARROW_ASPECT = 0.18     # width/height at/below this with low edges ⇒ decorative sliver


# --- Slice 66: lightly-ruled / text-heavy reconstructable-table detection -----
#
# Slice 65's real operator validation showed the Slice 64 classifier only caught a *strong*
# full horizontal+vertical rule grid as a table; the real sample's lightly ruled / text-heavy
# tables stayed ``unknown`` (their faint rules and antialiased text never reached the strict
# ``_VT_DARK`` ink threshold), so every candidate stayed in one type tier and diagram-first
# ranking never engaged — two useful but reconstructable tables were selected. Slice 66 adds a
# few extra *bounded* projection features — a softer-ink horizontal text-band rhythm and a
# vertical column-gutter structure — so a table with weak/no drawn rules is still recognized as
# ``reconstructable_table``, while a genuine diagram (no regular row/column rhythm) stays
# ``diagram_or_figure``. Same hard limits as Slice 64: pixel-only over the already-safe,
# already-job-dir-contained crop; never OCRs, never calls a model/provider/network, never
# base64/serializes/logs image bytes, never records a path or source text, adds no artifact,
# and degrades to ``unknown`` (prior behavior) whenever the crop cannot be analyzed.

# A separate, softer ink threshold used ONLY for the new text-band / column-gutter projections.
# ``_VT_DARK`` (110) counts only near-black rule/shape pixels; downscaled, antialiased printed
# text is mid-gray and would be missed — which is exactly why the real light tables fell to
# ``unknown``. Anything clearly darker than light-gray counts as "text ink" for the projection.
_LT_INK = 180
_LT_ROW_TEXT_MIN = 0.05   # row text-ink fraction at/above this ⇒ a text (ink) row
_LT_ROW_BLANK_MAX = 0.01  # row text-ink fraction at/below this ⇒ a blank separator row
_LT_COL_GUTTER_MAX = 0.06 # column text-ink fraction at/below this ⇒ a whitespace gutter column
_LT_MIN_TEXT_BANDS = 3    # ≥ this many separated text bands ⇒ a repeated-row rhythm
_LT_MIN_COL_BLOCKS = 2    # ≥ this many gutter-separated column blocks ⇒ column structure
_LT_GAP_CV_MAX = 0.5      # band-gap coefficient-of-variation at/below this ⇒ regular spacing


# --- Slice 70: two-column / glossary / definition-table precision -------------
#
# Slice 69's real operator selection trace localized the remaining failure precisely:
# all 11 safe candidates were classified ``diagram_or_figure`` while the two *selected*
# visuals were, by manual inspection, clean two-column definition/glossary TABLES — so
# diagram-first ranking had no signal and reconstructable tables won. The mechanism: a
# glossary/definition table has VARIABLE-height rows (multi-line definitions wrap), so its
# horizontal text bands are NOT evenly spaced; Slice 66's text-grid path requires a *regular*
# row rhythm (``row_band_regular``) and therefore misses it, and with no drawn rules the
# lightly-ruled path misses it too — leaving it to fall through to ``diagram_or_figure``.
#
# Slice 70 adds one more bounded, deterministic, pixel-only signal: a ``two_col_split``. It
# fires only when the crop has exactly TWO substantial text columns separated by a real
# gutter (whitespace or a thin drawn divider) AND *each* column independently contains
# several separated horizontal text bands. The per-column row-band requirement is the key
# guard that keeps a labeled DIAGRAM a diagram: a diagram's "columns" are continuous shapes
# (one or two bands) and its connectors/diagonals smear ink across the middle so there are
# rarely two clean text columns — text presence alone is never enough, the layout must be a
# regular two-column row structure. Regularity of row spacing is intentionally NOT required,
# which is exactly what lets variable-height glossary/definition rows qualify. Same hard
# limits as Slice 64/66: pixel-only over the already-safe, already-job-dir-contained crop;
# never OCRs, never calls a model/provider/network, never base64/serializes/logs image bytes,
# never records a path or source text, adds no artifact, and degrades to ``unknown`` whenever
# the crop cannot be analyzed.
_TT_SIDE_MIN_FRAC = 0.10   # each of the two columns must span ≥ this fraction of the width
_TT_GUTTER_MIN_FRAC = 0.04 # the separator between the two columns must span ≥ this fraction
_TT_BLOCK_INK_MIN = 0.02   # each column's mean text-ink fraction must be ≥ this (real content)
_TT_MIN_COL_ROWS = 3       # each column must contain ≥ this many separated horizontal text bands


# --- Slice 72: dense ruled / wrapped-cell two-column definition-table precision ------
#
# Slice 71's real operator validation showed Slice 70 measurably improved classification
# (the trace's type buckets split: 9 diagram + 2 table where Slice 69 read 11 + 0), but the
# two *selected* visuals were STILL reconstructable two-column definition tables. The residual
# mechanism: those specific tables are densely ruled with WRAPPED multi-line description cells,
# so each column's wrapped lines merge into too FEW separated horizontal text bands. Slice 70's
# ``two_col_split`` requires ≥ ``_TT_MIN_COL_ROWS`` (3) separated bands *per column*; a dense
# wrapped definition column collapses to one or two bands and the guard never fires, so the
# table falls through to ``diagram_or_figure`` and leads the diagram tier.
#
# Slice 72 adds one more bounded, deterministic, pixel-only signal: ``dense_wrapped_two_col``.
# It relaxes the per-column band count (wrapped cells legitimately merge bands) but COMPENSATES
# with a much stronger structural guard — a *persistent* vertical gutter that stays clear of ink
# down most of the crop height. A genuine diagram (whose connectors / diagonals / shapes smear
# ink across the middle) cannot fake a clean full-height gutter, so the relaxation does not
# weaken the diagram guard. The signal fires only when ALL hold: exactly two substantial content
# columns, both carrying DENSE ink (real wrapped definition text — not a sparse diagram label),
# separated by a real gutter that is clear of ink for most rows, with at least a couple of
# stacked text bands per column (so two side-by-side solid blobs never qualify). Row-spacing
# regularity is intentionally NOT required, which is exactly what lets variable-height wrapped
# definition rows qualify. Same hard limits as Slice 64/66/70: pixel-only over the already-safe,
# already-job-dir-contained crop; never OCRs, never calls a model/provider/network, never
# base64/serializes/logs image bytes, never records a path or source text, adds no artifact, and
# degrades to ``unknown`` whenever the crop cannot be analyzed.
_DW_DENSE_INK_MIN = 0.06       # each column's mean text-ink fraction must be ≥ this (DENSE text)
_DW_GUTTER_ROW_INK_MAX = 0.10  # a row's gutter ink fraction at/below this ⇒ that row's gutter clear
_DW_GUTTER_CONSISTENCY_MIN = 0.75  # ≥ this fraction of rows must have a clear gutter (persistent)
_DW_MIN_COL_RICHNESS = 2.5     # each column's avg ink-runs per inked row must be ≥ this (TEXT, not a shape)


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
            info = {"status": "skipped", "reason": reason}
            # Slice 68: both gates passed and candidate selection WAS attempted, so a
            # sanitized selection trace is emitted even though nothing was inserted —
            # this is exactly the case future runs need to audit (why no figure).
            _emit_selection_trace(job, max_images=max_images, selected=[], info=info)
            return text, info
        new_text, info = insert_visual_markdown_references(text, candidates)
        if info.get("status") != STATUS_INSERTED:
            _log(f"Visual markdown pilot: no figure inserted ({info.get('reason')}).")
            _emit_selection_trace(job, max_images=max_images, selected=candidates, info=info)
            return text, info
        # Carry the closed-vocabulary quality diagnostics (Slice 60) of the FIRST
        # (strongest) figure on the success info for backward compatibility. These are
        # advisory only and contain no path / text / image bytes.
        first = candidates[0]
        if isinstance(first, dict):
            info["quality_score"] = first.get("quality_score")
            info["quality_reasons"] = first.get("quality_reasons")
            first_type = first.get("visual_type")
            info["visual_type"] = first_type if first_type in VISUAL_TYPES else None
        # The single-figure path returns no count; normalize it so every successful
        # insertion advertises a safe integer count (1 or 2).
        info.setdefault("inserted_visual_count", 1)
        count = info.get("inserted_visual_count", 1)
        _log(
            f"Visual markdown pilot: inserted {count} figure(s) "
            f"({info.get('placement')})."
        )
        # Slice 68: sanitized diagnostic candidate audit (closed-vocab / bounded-numeric
        # only). Wrapped internally so a trace problem can never fail the insertion.
        _emit_selection_trace(job, max_images=max_images, selected=candidates, info=info)
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
    # the best of the rest. Slice 64: among the accepted candidates a hard-to-reconstruct
    # diagram/figure outranks a reconstructable table (visual-type tier first), and within
    # a tier the established quality near-margin rule decides. With no analyzable crop the
    # type priority is uniform and this is identical to the prior quality-only pick.
    scored = [score_visual_markdown_candidate_for_pilot(asset) for asset, _ in ordered]
    accepted = [i for i, q in enumerate(scored) if not q["decorative"]]
    if not accepted:
        return None, SKIP_CANDIDATE_LOW_QUALITY

    types = _visual_type_priorities(job, ordered, accepted)
    chosen = _best_typed(accepted, scored, types)
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

    types = _visual_type_priorities(job, ordered, accepted)
    chosen_indices = _select_multi(ordered, scored, accepted, cap, types)
    return [_enrich_candidate(ordered[i][1], scored[i]) for i in chosen_indices], STATUS_INSERTED


def _select_multi(
    ordered: list[tuple[dict[str, Any], dict[str, Any]]],
    scored: list[dict[str, Any]],
    accepted: list[int],
    cap: int,
    types: list[int],
) -> list[int]:
    """Choose up to ``cap`` candidate indices, strongest first, with Slice 62/64 rules.

    The first index is the single-best pick, now visual-type aware (Slice 64): a
    hard-to-reconstruct diagram/figure outranks a reconstructable table, and within a
    visual-type tier the established quality near-margin rule decides. Each subsequent
    index must clear the secondary quality floor and avoid duplicate asset ids / refs; a
    distinct source page is preferred, falling back to a same-page figure only when no
    distinct-page candidate qualifies, and within the eligible pool the same type-first /
    quality-second ordering applies (so a second diagram is preferred over a table when
    both qualify). ``accepted`` is non-empty; the returned list preserves selection order
    (strongest first). With no analyzable crop the type priority is uniform and this
    reduces to the unchanged Slice 62 behavior.
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

    # First figure: the single-best pick — visual-type tier first, then the quality
    # near-rule (no secondary floor; the strongest stands on its own even if only neutral).
    _take(_best_typed(accepted, scored, types))

    # Subsequent figures, up to the cap: prefer a distinct page; only fall back to a
    # same-page figure when no distinct-page candidate qualifies. Within the eligible pool
    # the same type-first / quality-second ordering applies.
    while len(selected) < cap:
        pool = [i for i in accepted if _eligible(i, prefer_distinct=True)]
        if not pool:
            pool = [i for i in accepted if _eligible(i, prefer_distinct=False)]
        if not pool:
            break
        _take(_best_typed(pool, scored, types))

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


# --- Slice 64: deterministic visual-TYPE classification (pixel-only) ----------


def score_visual_type_priority_for_pilot(visual_type: Any) -> int:
    """Closed-vocabulary visual-type → ranking priority (higher = preferred).

    ``diagram_or_figure`` (3) > ``reconstructable_table`` (2) > ``unknown`` (1) >
    ``decorative_or_low_information`` (0). Any unrecognized value maps to the neutral
    ``unknown`` priority so an unexpected token can never out-rank a real classification.
    Total; never raises.
    """
    return _VISUAL_TYPE_PRIORITY.get(visual_type, _VISUAL_TYPE_PRIORITY[VISUAL_TYPE_UNKNOWN])


def classify_visual_markdown_candidate_type_for_pilot(job: Any, candidate: Any) -> str:
    """Classify a *safe* candidate's visual TYPE from its job-local crop (Slice 64).

    Returns one closed-vocabulary token: ``diagram_or_figure`` · ``reconstructable_table``
    · ``decorative_or_low_information`` · ``unknown``. The candidate's ``asset_ref`` is
    re-validated and re-confirmed inside the job directory (defence in depth) before the
    PNG is opened read-only with Pillow, converted to grayscale, bounded-downscaled, and
    summarized into a few non-sensitive numeric features. It NEVER OCRs the crop, calls a
    model/provider/network, base64/serializes/logs image bytes, records a path or source
    text, or writes any artifact. Degrade-never-fail: a missing/unsafe ref, missing Pillow,
    an unreadable/too-small image, or any error yields ``unknown`` (which preserves the
    prior quality-only selection behavior). Never raises.
    """
    if not isinstance(candidate, dict):
        return VISUAL_TYPE_UNKNOWN
    features = _visual_type_features(job, candidate.get("asset_ref"))
    if features is None:
        return VISUAL_TYPE_UNKNOWN
    return _classify_visual_type_from_features(features)


def _visual_type_features(job: Any, asset_ref: Any) -> dict[str, float] | None:
    """Bounded, non-sensitive summary features of a safe crop, or ``None`` (Slice 64).

    Re-applies the safe-ref + job-dir containment gates, then reads the PNG via Pillow
    (lazy import; optional dependency). Returns only small rounded numeric features —
    no pixels, bytes, path, or text are retained or returned. ``None`` whenever the crop
    cannot be analyzed (no Pillow, unreadable, or below ``_VT_MIN_ANALYZE_DIM``). Never
    raises and never logs image content.
    """
    ref = validate_visual_asset_ref(asset_ref)
    if ref is None or not _asset_file_ok(job, ref):
        return None
    try:
        from PIL import Image  # optional dependency; absent ⇒ degrade to unknown
    except Exception:
        return None
    try:
        job_dir = os.path.realpath(str(_job_dir(job)))
        target = os.path.realpath(os.path.join(job_dir, ref))
        with Image.open(target) as im:
            orig_w, orig_h = im.size
            if (orig_w < _VT_MIN_ANALYZE_DIM or orig_h < _VT_MIN_ANALYZE_DIM):
                return None
            gray = im.convert("L")
            longest = max(orig_w, orig_h)
            if longest > _VT_MAX_DIM:
                scale = _VT_MAX_DIM / float(longest)
                gray = gray.resize(
                    (max(1, int(orig_w * scale)), max(1, int(orig_h * scale)))
                )
            w, h = gray.size
            pixels = list(gray.getdata())
    except Exception:
        return None
    if w <= 0 or h <= 0 or len(pixels) < w * h:
        return None
    return _summarize_gray_pixels(pixels, w, h, orig_w, orig_h)


def _summarize_gray_pixels(
    pixels: list[int], w: int, h: int, orig_w: int, orig_h: int
) -> dict[str, float]:
    """Compute the bounded visual-type features from a grayscale pixel buffer.

    Pure arithmetic over a bounded (≤ ``_VT_MAX_DIM`` per side) buffer. Produces only
    rounded scalar summaries: blank ratio, horizontal/vertical full-rule counts and
    densities, rough edge density, the original aspect ratio, and (Slice 66) the
    softer-ink text-band rhythm + column-gutter structure used to spot lightly ruled /
    text-heavy reconstructable tables. No pixel values leave this function.
    """
    total = w * h
    light_count = 0
    line_rows = 0
    row_text: list[float] = []  # Slice 66: per-row softer-ink text fraction
    for r in range(h):
        base = r * w
        dark_in_row = 0
        text_in_row = 0
        for c in range(w):
            value = pixels[base + c]
            if value <= _VT_DARK:
                dark_in_row += 1
            elif value >= _VT_LIGHT:
                light_count += 1
            if value <= _LT_INK:
                text_in_row += 1
        if w > 0 and dark_in_row / w >= _VT_LINE_FRAC:
            line_rows += 1
        row_text.append(text_in_row / w if w > 0 else 0.0)

    line_cols = 0
    col_text: list[float] = []  # Slice 66: per-column softer-ink text fraction
    for c in range(w):
        dark_in_col = 0
        text_in_col = 0
        for r in range(h):
            value = pixels[r * w + c]
            if value <= _VT_DARK:
                dark_in_col += 1
            if value <= _LT_INK:
                text_in_col += 1
        if h > 0 and dark_in_col / h >= _VT_LINE_FRAC:
            line_cols += 1
        col_text.append(text_in_col / h if h > 0 else 0.0)

    # Rough edge density: horizontal adjacent-pixel transitions above a delta.
    edges = 0
    pairs = 0
    for r in range(h):
        base = r * w
        prev = pixels[base]
        for c in range(1, w):
            value = pixels[base + c]
            if abs(value - prev) >= _VT_EDGE_DELTA:
                edges += 1
            prev = value
            pairs += 1

    blank_ratio = (light_count / total) if total > 0 else 1.0
    edge_density = (edges / pairs) if pairs > 0 else 0.0
    aspect = (orig_w / orig_h) if orig_h > 0 else 0.0

    # Slice 66: softer-ink text-band rhythm (rows) and column-gutter structure (columns).
    text_bands = _profile_runs(row_text, _LT_ROW_TEXT_MIN, _LT_ROW_BLANK_MAX)
    n_text_bands = len(text_bands)
    row_band_regular = _runs_regular(text_bands)
    n_col_blocks = _count_col_blocks(col_text, _LT_COL_GUTTER_MAX)

    # Slice 70: strong two-column split (glossary/definition table), regularity NOT required.
    two_col_split = _two_column_split(pixels, w, h, col_text)

    # Slice 72: dense ruled / wrapped-cell two-column table (bands merge; gutter persists).
    dense_wrapped_two_col = _dense_wrapped_two_column(pixels, w, h, col_text)

    return {
        "blank_ratio": round(blank_ratio, 4),
        "edge_density": round(edge_density, 4),
        "n_line_rows": float(line_rows),
        "n_line_cols": float(line_cols),
        "h_line_density": round(line_rows / h, 4) if h > 0 else 0.0,
        "v_line_density": round(line_cols / w, 4) if w > 0 else 0.0,
        "aspect": round(aspect, 4),
        "n_text_bands": float(n_text_bands),
        "row_band_regular": float(row_band_regular),
        "n_col_blocks": float(n_col_blocks),
        "two_col_split": float(two_col_split),
        "dense_wrapped_two_col": float(dense_wrapped_two_col),
    }


def _profile_runs(profile: list[float], ink_min: float, blank_max: float) -> list[tuple[int, int]]:
    """Contiguous *ink* runs in a 1-D projection, separated by *blank* values (Slice 66).

    A value ``>= ink_min`` is ink (opens / extends a run); a value ``<= blank_max`` is a
    blank separator (closes a run). An ambiguous value in between keeps an open run open but
    never starts one — so faint speckle between bands does not merge them. Returns a list of
    ``(start, end_exclusive)`` index runs. Pure; never raises.
    """
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, value in enumerate(profile):
        if value >= ink_min:
            if start is None:
                start = i
        elif value <= blank_max:
            if start is not None:
                runs.append((start, i))
                start = None
        # else ambiguous: keep an open run open, but do not start a new one.
    if start is not None:
        runs.append((start, len(profile)))
    return runs


def _runs_regular(runs: list[tuple[int, int]]) -> float:
    """1.0 iff ``runs`` are evenly spaced (regular row rhythm), else 0.0 (Slice 66).

    Regularity = the coefficient of variation of consecutive run-center gaps is at/below
    ``_LT_GAP_CV_MAX``. Fewer than three runs cannot establish a rhythm ⇒ 0.0. Pure; never
    raises (a degenerate zero/near-zero mean spacing ⇒ 0.0).
    """
    if len(runs) < _LT_MIN_TEXT_BANDS:
        return 0.0
    centers = [(s + e) / 2.0 for s, e in runs]
    gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
    if not gaps:
        return 0.0
    mean = sum(gaps) / len(gaps)
    if mean <= 0.0:
        return 0.0
    var = sum((g - mean) ** 2 for g in gaps) / len(gaps)
    cv = (var ** 0.5) / mean
    return 1.0 if cv <= _LT_GAP_CV_MAX else 0.0


def _count_col_blocks(col_text: list[float], gutter_max: float) -> int:
    """Number of gutter-separated column blocks in a vertical text projection (Slice 66).

    A column with text fraction ``> gutter_max`` is content; a run of content columns is one
    block; a column ``<= gutter_max`` is a whitespace gutter that ends the current block. So a
    three-column table reads as three blocks; full-width prose reads as one. Pure; never raises.
    """
    blocks = 0
    in_block = False
    for value in col_text:
        if value > gutter_max:
            if not in_block:
                blocks += 1
                in_block = True
        else:
            in_block = False
    return blocks


def _content_column_spans(col_text: list[float], gutter_max: float) -> list[tuple[int, int]]:
    """Contiguous content-column ``(start, end_exclusive)`` spans (Slice 70).

    A column with text fraction ``> gutter_max`` is content; a run of such columns is one
    span; a column ``<= gutter_max`` is a whitespace gutter that closes the current span.
    Mirrors :func:`_count_col_blocks` but returns the spans so the two-column split can
    measure widths, gutters, and per-column row structure. Pure; never raises.
    """
    spans: list[tuple[int, int]] = []
    start: int | None = None
    for i, value in enumerate(col_text):
        if value > gutter_max:
            if start is None:
                start = i
        else:
            if start is not None:
                spans.append((start, i))
                start = None
    if start is not None:
        spans.append((start, len(col_text)))
    return spans


def _column_row_band_count(pixels: list[int], w: int, h: int, x0: int, x1: int) -> int:
    """Number of separated horizontal text bands within one column's x-range (Slice 70).

    Builds a per-row softer-ink (``_LT_INK``) text-fraction profile restricted to columns
    ``[x0, x1)`` and counts its separated bands with the established :func:`_profile_runs`
    rule. A glossary/definition column has several entry rows separated by whitespace
    (≥ several bands); a diagram's continuous shape spans the height as one or two bands.
    Bounded (≤ ``_VT_MAX_DIM`` per side); pure; never raises.
    """
    span = x1 - x0
    if span <= 0 or h <= 0:
        return 0
    profile: list[float] = []
    for r in range(h):
        base = r * w
        ink = 0
        for c in range(x0, x1):
            if pixels[base + c] <= _LT_INK:
                ink += 1
        profile.append(ink / span)
    return len(_profile_runs(profile, _LT_ROW_TEXT_MIN, _LT_ROW_BLANK_MAX))


def _two_column_split(pixels: list[int], w: int, h: int, col_text: list[float]) -> float:
    """1.0 iff the crop is a regular two-column (glossary/definition) table, else 0.0 (Slice 70).

    Fires only when ALL hold (conservative, multi-signal — never "contains text"):

    * exactly **two** substantial content columns (each ≥ ``_TT_SIDE_MIN_FRAC`` of the width),
    * separated by a real gutter (≥ ``_TT_GUTTER_MIN_FRAC`` of the width — whitespace, or a
      thin drawn divider that leaves the surrounding band narrow),
    * both columns carry real ink (mean text fraction ≥ ``_TT_BLOCK_INK_MIN``), and
    * **each** column independently contains ≥ ``_TT_MIN_COL_ROWS`` separated horizontal text
      bands (the guard that keeps a labeled diagram a diagram: its columns are continuous
      shapes, not stacks of text rows).

    Row-spacing regularity is intentionally NOT required, so variable-height definition rows
    qualify. Pure; bounded; never raises.
    """
    if w <= 0 or h <= 0:
        return 0.0
    spans = _content_column_spans(col_text, _LT_COL_GUTTER_MAX)
    substantial = [(s, e) for (s, e) in spans if (e - s) / w >= _TT_SIDE_MIN_FRAC]
    if len(substantial) != 2:
        return 0.0
    (ls, le), (rs, re) = substantial
    if (rs - le) / w < _TT_GUTTER_MIN_FRAC:
        return 0.0
    left_ink = sum(col_text[ls:le]) / (le - ls) if le > ls else 0.0
    right_ink = sum(col_text[rs:re]) / (re - rs) if re > rs else 0.0
    if left_ink < _TT_BLOCK_INK_MIN or right_ink < _TT_BLOCK_INK_MIN:
        return 0.0
    if _column_row_band_count(pixels, w, h, ls, le) < _TT_MIN_COL_ROWS:
        return 0.0
    if _column_row_band_count(pixels, w, h, rs, re) < _TT_MIN_COL_ROWS:
        return 0.0
    return 1.0


def _gutter_consistency(pixels: list[int], w: int, h: int, x0: int, x1: int) -> float:
    """Fraction of rows whose gutter band ``[x0, x1)`` is clear of ink (Slice 72).

    A wrapped two-column table keeps a vertical whitespace channel between its columns down
    almost the whole height (a thin drawn divider is tolerated — only a small fraction of the
    gutter is then inked). A diagram's connectors / diagonals / shapes cross the middle, so its
    "gutter" is repeatedly broken. Returns the fraction of rows whose ink fraction inside the
    band is at/below ``_DW_GUTTER_ROW_INK_MAX``. Bounded; pure; never raises.
    """
    span = x1 - x0
    if span <= 0 or h <= 0:
        return 0.0
    clear_rows = 0
    for r in range(h):
        base = r * w
        ink = 0
        for c in range(x0, x1):
            if pixels[base + c] <= _LT_INK:
                ink += 1
        if (ink / span) <= _DW_GUTTER_ROW_INK_MAX:
            clear_rows += 1
    return clear_rows / h


def _column_text_richness(pixels: list[int], w: int, h: int, x0: int, x1: int) -> float:
    """Average number of separated ink runs per *inked* row within column ``[x0, x1)`` (Slice 72).

    The text-vs-shape discriminator: a column of real text has several short ink runs per row
    (words / glyph clusters), while a diagram's continuous shape outline contributes only one or
    two long runs per row. Counts horizontal ink runs (transitions into softer-ink ``_LT_INK``)
    on each row that carries any ink, and averages over the inked rows. A column that is a single
    solid block scores ~1.0 (one run/row); dense wrapped text scores well above. Bounded
    (≤ ``_VT_MAX_DIM`` per side); pure; never raises.
    """
    if x1 - x0 <= 0 or h <= 0:
        return 0.0
    total_runs = 0
    inked_rows = 0
    for r in range(h):
        base = r * w
        runs = 0
        prev_ink = False
        any_ink = False
        for c in range(x0, x1):
            ink = pixels[base + c] <= _LT_INK
            if ink and not prev_ink:
                runs += 1
            if ink:
                any_ink = True
            prev_ink = ink
        if any_ink:
            total_runs += runs
            inked_rows += 1
    return (total_runs / inked_rows) if inked_rows else 0.0


def _dense_wrapped_two_column(pixels: list[int], w: int, h: int, col_text: list[float]) -> float:
    """1.0 iff the crop is a dense, wrapped-cell two-column table, else 0.0 (Slice 72).

    The Slice 70 companion to :func:`_two_column_split` for the residual failure shape Slice 71
    localized on the real sample: dense ruled / wrapped-cell two-column definition tables whose
    wrapped lines merge into too FEW separated bands per column for the ≥ ``_TT_MIN_COL_ROWS``
    band guard to fire (antialiased wrapped text leaves no clean blank separator rows, so a whole
    column collapses to one band). It therefore does NOT rely on band count at all; instead it
    pairs the two-column structure with two strong guards a diagram cannot fake — a *persistent*
    clean vertical gutter and per-column *text richness*. Fires only when ALL hold:

    * exactly **two** substantial content columns (each ≥ ``_TT_SIDE_MIN_FRAC`` of the width),
    * separated by a real gutter (≥ ``_TT_GUTTER_MIN_FRAC`` of the width),
    * both columns carry **dense** ink (mean text fraction ≥ ``_DW_DENSE_INK_MIN`` — real wrapped
      definition text, not a sparse diagram label),
    * the gutter is a **persistent** vertical separator (clear of ink for ≥
      ``_DW_GUTTER_CONSISTENCY_MIN`` of rows — a diagram's connectors / diagonals break it), and
    * **both** columns are **text-rich** (avg ink-runs per inked row ≥ ``_DW_MIN_COL_RICHNESS`` —
      several words per row, not a continuous shape outline; this is the guard that keeps a
      labeled diagram a diagram even when it happens to have two side-by-side regions).

    Row-spacing regularity is intentionally NOT required, so variable-height wrapped rows qualify.
    Pure; bounded (≤ ``_VT_MAX_DIM`` per side); never raises.
    """
    if w <= 0 or h <= 0:
        return 0.0
    spans = _content_column_spans(col_text, _LT_COL_GUTTER_MAX)
    substantial = [(s, e) for (s, e) in spans if (e - s) / w >= _TT_SIDE_MIN_FRAC]
    if len(substantial) != 2:
        return 0.0
    (ls, le), (rs, re) = substantial
    if (rs - le) / w < _TT_GUTTER_MIN_FRAC:
        return 0.0
    left_ink = sum(col_text[ls:le]) / (le - ls) if le > ls else 0.0
    right_ink = sum(col_text[rs:re]) / (re - rs) if re > rs else 0.0
    if left_ink < _DW_DENSE_INK_MIN or right_ink < _DW_DENSE_INK_MIN:
        return 0.0
    if _gutter_consistency(pixels, w, h, le, rs) < _DW_GUTTER_CONSISTENCY_MIN:
        return 0.0
    if _column_text_richness(pixels, w, h, ls, le) < _DW_MIN_COL_RICHNESS:
        return 0.0
    if _column_text_richness(pixels, w, h, rs, re) < _DW_MIN_COL_RICHNESS:
        return 0.0
    return 1.0


def _looks_like_reconstructable_table(features: dict[str, float]) -> bool:
    """True iff the bounded features describe a lightly ruled / text-heavy table (Slice 66).

    Two conservative, dual-signal paths (both require more than one independent table cue so a
    diagram's incidental banding can never qualify):

    * **Text-grid** — a regular repeated text-band rhythm *and* a multi-column gutter structure
      (rows arranged in columns, no drawn rules needed); or
    * **Lightly ruled** — multiple full horizontal rules *without* a strong vertical-rule grid,
      backed by either the row rhythm or the column structure.

    A genuine diagram (irregular row spacing, no clean full-height column gutters, no repeated
    horizontal rules) satisfies neither. Slice 70 adds a third path — a strong two-column
    split — so glossary/definition tables with *variable-height* (irregular) rows still
    qualify without weakening the diagram guard. Slice 72 adds a fourth — a dense, wrapped-cell
    two-column split with a *persistent* gutter — so densely ruled / wrapped definition tables
    whose merged bands defeat the Slice 70 per-column band guard still qualify, again without
    weakening the diagram guard (the persistent gutter is what a diagram cannot fake). Pure;
    never raises.
    """
    n_text_bands = features.get("n_text_bands", 0.0)
    row_band_regular = features.get("row_band_regular", 0.0)
    n_col_blocks = features.get("n_col_blocks", 0.0)
    n_line_rows = features.get("n_line_rows", 0.0)
    n_line_cols = features.get("n_line_cols", 0.0)
    two_col_split = features.get("two_col_split", 0.0)
    dense_wrapped_two_col = features.get("dense_wrapped_two_col", 0.0)

    has_row_rhythm = n_text_bands >= _LT_MIN_TEXT_BANDS and row_band_regular >= 1.0
    has_columns = n_col_blocks >= _LT_MIN_COL_BLOCKS
    has_h_rules = n_line_rows >= _VT_GRID_MIN_LINES
    weak_v_rules = n_line_cols < _VT_GRID_MIN_LINES

    # Slice 70 two-column split: two text columns of stacked rows (regularity not required).
    if two_col_split >= 1.0:
        return True
    # Slice 72 dense wrapped two-column split: merged bands but a persistent vertical gutter.
    if dense_wrapped_two_col >= 1.0:
        return True
    # Text-grid: regular rows arranged in clear columns.
    if has_row_rhythm and has_columns:
        return True
    # Lightly ruled: horizontal rules + row/column structure, but no strong vertical grid.
    if has_h_rules and weak_v_rules and (has_row_rhythm or has_columns):
        return True
    return False


def _classify_visual_type_from_features(features: dict[str, float]) -> str:
    """Map bounded features to a closed visual-type token (conservative; never raises).

    Order of decision: near-empty / decorative strip first (low information), then a clear
    horizontal+vertical rule grid ⇒ table, then (Slice 66) a lightly ruled / text-heavy table
    by its text-band rhythm + column-gutter structure ⇒ table, then meaningful non-grid graphic
    content ⇒ diagram/figure; anything ambiguous degrades to ``unknown`` so prior behavior holds.
    """
    blank_ratio = features.get("blank_ratio", 0.0)
    edge_density = features.get("edge_density", 0.0)
    n_line_rows = features.get("n_line_rows", 0.0)
    n_line_cols = features.get("n_line_cols", 0.0)
    aspect = features.get("aspect", 0.0)

    low_edges = edge_density < _VT_EDGE_MIN
    # Near-empty crop, or an extreme banner/sliver with little content ⇒ low-information.
    if low_edges and blank_ratio >= _VT_BLANK_MAX:
        return VISUAL_TYPE_DECORATIVE
    if low_edges and aspect > 0 and (aspect >= _VT_BANNER_ASPECT or aspect <= _VT_NARROW_ASPECT):
        return VISUAL_TYPE_DECORATIVE
    # A regular grid of full horizontal AND vertical rules ⇒ reconstructable table.
    if n_line_rows >= _VT_GRID_MIN_LINES and n_line_cols >= _VT_GRID_MIN_LINES:
        return VISUAL_TYPE_TABLE
    # Slice 66: a lightly ruled / text-heavy table (weak/no drawn rules) ⇒ still a table.
    if _looks_like_reconstructable_table(features):
        return VISUAL_TYPE_TABLE
    # Substantial non-grid graphic content ⇒ a hard-to-reconstruct diagram/figure.
    if edge_density >= _VT_EDGE_MIN and blank_ratio < _VT_BLANK_MAX:
        return VISUAL_TYPE_DIAGRAM
    return VISUAL_TYPE_UNKNOWN


def _visual_type_priorities(
    job: Any,
    ordered: list[tuple[dict[str, Any], dict[str, Any]]],
    accepted: list[int],
) -> list[int]:
    """Type-priority per ``ordered`` index; classify & annotate ACCEPTED candidates only.

    Returns a list aligned to ``ordered`` where accepted indices carry their visual-type
    ranking priority and every other index carries the neutral ``unknown`` priority (those
    indices are never in a selection pool, so their value is inert). As a side effect each
    accepted candidate dict gains a safe closed-vocabulary ``visual_type`` token for
    diagnostics. Never raises — classification already degrades to ``unknown`` on any
    problem, so when no crop is analyzable this returns a uniform priority and selection
    falls back to the unchanged quality-only behavior.
    """
    neutral = _VISUAL_TYPE_PRIORITY[VISUAL_TYPE_UNKNOWN]
    priorities = [neutral] * len(ordered)
    accepted_set = set(accepted)
    for i in accepted_set:
        candidate = ordered[i][1]
        visual_type = classify_visual_markdown_candidate_type_for_pilot(job, candidate)
        if isinstance(candidate, dict):
            candidate["visual_type"] = visual_type
        priorities[i] = score_visual_type_priority_for_pilot(visual_type)
    return priorities


def _best_typed(pool: list[int], scored: list[dict[str, Any]], types: list[int]) -> int:
    """Best index in ``pool``: highest visual-type tier first, then the quality near-rule.

    Within the strongest visual-type tier present in ``pool`` the established
    :func:`_best_within_margin` quality rule decides (highest score wins; earliest priority
    on ties / near-ties). When every pooled candidate shares one type tier (e.g. all
    ``unknown`` — the common degrade case) this is identical to ``_best_within_margin`` over
    the whole pool, so prior selection behavior is preserved byte-for-byte. ``pool`` must be
    non-empty.
    """
    top_priority = max(types[i] for i in pool)
    tier = [i for i in pool if types[i] == top_priority]
    return _best_within_margin(tier, scored)


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


def _visual_caption_line(source_page: int) -> str:
    """A safe italic caption line for *below* an inserted visual (Slice 74).

    Carries only a fixed generic phrase plus the bounded integer source page when
    available; otherwise the page-free generic phrase. It never includes a source
    filename, path, title, raw manifest caption, OCR/document/extracted-table text,
    URL, or any other private content — so it cannot leak regardless of input.
    """
    if isinstance(source_page, int) and not isinstance(source_page, bool) and source_page > 0:
        return _VISUAL_CAPTION_WITH_PAGE.format(page=source_page)
    return _VISUAL_CAPTION_GENERIC


def build_visual_markdown_block(candidate: Any) -> str:
    """Build the readable inserted block: the image ref plus a safe caption line.

    The image reference (``![alt](assets/<slug>.png)``) is built by
    :func:`build_visual_markdown_image` and is **byte-identical** to the pre-Slice-74
    output — the ref and its alt text are not altered. A generic, page-derived italic
    caption line (Slice 74) is appended below it, separated by a blank line::

        ![alt](assets/<slug>.png)

        *Source visual, page N.*

    Caption construction degrades-never-fails: if the caption line cannot be built for
    any reason, the image ref alone is returned (the pre-Slice-74 behavior). Raises
    ``ValueError`` only when the image ref itself is invalid (same as
    :func:`build_visual_markdown_image`).
    """
    image_md = build_visual_markdown_image(candidate)
    try:
        source_page = _safe_page(candidate.get("source_page")) if isinstance(candidate, dict) else 0
        caption_line = _visual_caption_line(source_page)
    except Exception:
        return image_md
    if not caption_line:
        return image_md
    return f"{image_md}\n\n{caption_line}"


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
        image_md = build_visual_markdown_block(candidate)
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
            image_md = build_visual_markdown_block(candidate)
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
                "quality_score": None, "quality_reasons": None, "visual_type": None}
    reasons = candidate.get("quality_reasons")
    visual_type = candidate.get("visual_type")
    return {
        "asset_id": candidate.get("asset_id"),
        "asset_ref": candidate.get("asset_ref"),
        "source_page": _safe_page(candidate.get("source_page")),
        "placement": placement,
        "quality_score": candidate.get("quality_score"),
        "quality_reasons": list(reasons) if isinstance(reasons, list) else None,
        "visual_type": visual_type if visual_type in VISUAL_TYPES else None,
    }


# --- Slice 68: sanitized visual-pilot selection trace (diagnostic only) --------
#
# Slice 67 reran the real post-Slice-66 cap-2 operator sample and it STILL selected
# two useful-but-reconstructable tables only; no irreplaceable diagram/figure was
# chosen. Before any further blind heuristic tuning, this slice adds a bounded,
# sanitized candidate-audit artifact so future real runs can explain *why* diagrams
# were not selected (which candidates existed, their classified visual type, and why
# the chosen tables outranked them). It is DIAGNOSTIC ONLY: it never changes ranking,
# the cap, the default, the two-key gate, the UI, render/export behavior, or extraction/
# OCR routing, and it adds no model/provider/cloud call. It is written only when both
# gates are on AND candidate selection was attempted, and degrades-never-fails.
#
# Hard no-leak contract (same discipline as the rest of this module): the trace carries
# ONLY closed-vocabulary tokens and bounded integers/rounded floats plus the already-
# safe ``assets/<slug>.png`` ref. It NEVER carries an absolute path, the source document
# filename, document/OCR/caption/extracted-table text, image bytes, base64, a data URI,
# a raw provider payload, a raw exception, a raw URL, a token, raw argv, or a model/
# mmproj/executable path.

SELECTION_TRACE_FILENAME = "visual_markdown_selection_trace.json"
SELECTION_TRACE_SCHEMA_VERSION = 1

# Closed selection-reason vocabulary (diagnostic only; never embedded in the guide).
TRACE_SELECTED_DIAGRAM_FIRST = "selected_by_diagram_first_ranking"
TRACE_SELECTED_QUALITY = "selected_by_quality_ranking"
TRACE_SELECTED_PRIORITY = "selected_by_priority_order"
# Closed rejection / deprioritization vocabulary.
TRACE_REJECTED_LOW_QUALITY = "rejected_low_quality"
TRACE_REJECTED_UNSAFE_REF = "rejected_unsafe_ref"
TRACE_REJECTED_WRONG_PROVIDER = "rejected_wrong_provider"
TRACE_REJECTED_WRONG_ASSET_TYPE = "rejected_wrong_asset_type"
TRACE_REJECTED_DUP_REF = "rejected_duplicate_asset_ref"
TRACE_REJECTED_DUP_ID = "rejected_duplicate_asset_id"
TRACE_REJECTED_SECONDARY_FLOOR = "rejected_secondary_below_quality_floor"
TRACE_DEPRIORITIZED_TABLE = "deprioritized_reconstructable_table"

# Closed classification vocabulary (one per safe candidate; mirrors the visual-type token).
TRACE_CLASSIFIED_UNKNOWN = "classified_unknown"
TRACE_CLASSIFIED_TABLE = "classified_reconstructable_table"
TRACE_CLASSIFIED_DIAGRAM = "classified_diagram_or_figure"
TRACE_CLASSIFIED_DECORATIVE = "classified_decorative_or_low_information"

_VT_TO_CLASSIFIED = {
    VISUAL_TYPE_DIAGRAM: TRACE_CLASSIFIED_DIAGRAM,
    VISUAL_TYPE_TABLE: TRACE_CLASSIFIED_TABLE,
    VISUAL_TYPE_UNKNOWN: TRACE_CLASSIFIED_UNKNOWN,
    VISUAL_TYPE_DECORATIVE: TRACE_CLASSIFIED_DECORATIVE,
}

SELECTION_TRACE_SELECTION_REASONS = {
    TRACE_SELECTED_DIAGRAM_FIRST,
    TRACE_SELECTED_QUALITY,
    TRACE_SELECTED_PRIORITY,
}
SELECTION_TRACE_REJECTION_REASONS = {
    TRACE_REJECTED_LOW_QUALITY,
    TRACE_REJECTED_UNSAFE_REF,
    TRACE_REJECTED_WRONG_PROVIDER,
    TRACE_REJECTED_WRONG_ASSET_TYPE,
    TRACE_REJECTED_DUP_REF,
    TRACE_REJECTED_DUP_ID,
    TRACE_REJECTED_SECONDARY_FLOOR,
    TRACE_DEPRIORITIZED_TABLE,
}


def _bump(counts: dict[str, int], token: str) -> None:
    counts[token] = counts.get(token, 0) + 1


def _trace_placement(info: dict[str, Any]) -> str | None:
    placement = info.get("placement")
    if placement in (PLACEMENT_SOURCE_PAGE_ANCHOR, PLACEMENT_VISUAL_REFERENCE_SECTION):
        return placement
    return None


def _safe_quality_score(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(_clamp_quality(float(value)), 3)


def _safe_quality_reasons(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [r for r in value if isinstance(r, str) and r in QUALITY_REASONS]


def _safe_inserted_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    if value < 0:
        return 0
    if value > _HARD_MAX_IMAGES:
        return _HARD_MAX_IMAGES
    return value


def _summarize_trace_candidates(
    job: Any, manifest_obj: Any, selected_slugs: set[str]
) -> dict[str, Any]:
    """One sanitized pass over the manifest assets → safe/unsafe counts + per-type tally.

    Re-applies (independently of the selection core, so ranking is untouched) the same
    hard provider/asset-type/Chandra/safe-ref/file gates, records a closed rejection token
    for every asset that fails one, and for each unique *safe* candidate records its bounded
    quality + closed visual-type classification. Returns the assembled fields plus the list
    of safe-candidate records the caller needs to assign soft (post-quality) rejection
    tokens. Pure w.r.t. inputs apart from reading the already-safe crops read-only; never
    raises.
    """
    assets = manifest_obj.get("assets") if isinstance(manifest_obj, dict) else None
    assets = assets if isinstance(assets, list) else []

    safe_records: list[dict[str, Any]] = []
    unsafe = 0
    rejection_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    seen_ids: set[str] = set()
    seen_refs: set[str] = set()

    for asset in assets:
        if not isinstance(asset, dict):
            unsafe += 1
            _bump(rejection_counts, TRACE_REJECTED_WRONG_ASSET_TYPE)
            continue
        if asset.get("source_provider") != SOURCE_PROVIDER_FITZ_LOCAL:
            unsafe += 1
            _bump(rejection_counts, TRACE_REJECTED_WRONG_PROVIDER)
            continue
        if asset.get("asset_type") != ASSET_TYPE_EXTRACTED_FIGURE:
            unsafe += 1
            _bump(rejection_counts, TRACE_REJECTED_WRONG_ASSET_TYPE)
            continue
        reasons = asset.get("reasons")
        if isinstance(reasons, list) and "chandra_blocked" in reasons:
            unsafe += 1
            _bump(rejection_counts, TRACE_REJECTED_WRONG_PROVIDER)
            continue
        ref = validate_visual_asset_ref(asset.get("image_ref"))
        if ref is None or not _asset_file_ok(job, ref):
            unsafe += 1
            _bump(rejection_counts, TRACE_REJECTED_UNSAFE_REF)
            continue
        slug = _safe_slug(asset.get("asset_id"))
        if slug and slug in seen_ids:
            unsafe += 1
            _bump(rejection_counts, TRACE_REJECTED_DUP_ID)
            continue
        if ref in seen_refs:
            unsafe += 1
            _bump(rejection_counts, TRACE_REJECTED_DUP_REF)
            continue
        if slug:
            seen_ids.add(slug)
        seen_refs.add(ref)

        quality = score_visual_markdown_candidate_for_pilot(asset)
        decorative = bool(quality.get("decorative"))
        if decorative:
            visual_type = VISUAL_TYPE_DECORATIVE
        else:
            visual_type = classify_visual_markdown_candidate_type_for_pilot(
                job, {"asset_ref": ref}
            )
            if visual_type not in VISUAL_TYPES:
                visual_type = VISUAL_TYPE_UNKNOWN
        _bump(type_counts, visual_type)
        safe_records.append(
            {
                "slug": slug or "figure",
                "score": _safe_quality_score(quality.get("score")) or 0.0,
                "decorative": decorative,
                "visual_type": visual_type,
                "selected": bool(slug and slug in selected_slugs),
            }
        )

    return {
        "total_manifest_assets": len(assets),
        "safe_records": safe_records,
        "unsafe_candidate_count": unsafe,
        "rejection_counts": rejection_counts,
        "type_counts": type_counts,
    }


def build_visual_markdown_selection_trace(
    job: Any,
    *,
    max_images: Any,
    selected: Any,
    info: Any,
    manifest: Any = None,
) -> dict[str, Any]:
    """Build the sanitized selection-trace dict (Slice 68). Total; never raises.

    ``selected`` is the list of enriched candidate dicts actually chosen (possibly empty);
    ``info`` is the pilot outcome info (status / reason / placement / inserted count). The
    returned dict contains only the whitelisted top-level fields, closed-vocabulary tokens,
    bounded integers / rounded floats, and the already-safe ``assets/<slug>.png`` ref. No
    path, document/OCR/caption text, image bytes, base64, data URI, provider payload, raw
    exception, URL, token, raw argv, or model/executable path is ever included.
    """
    selected = selected if isinstance(selected, list) else []
    info = info if isinstance(info, dict) else {}

    raw_status = info.get("status")
    status = STATUS_INSERTED if raw_status == STATUS_INSERTED else "skipped"
    if status == STATUS_INSERTED:
        reason = STATUS_INSERTED
        inserted_count = _safe_inserted_count(info.get("inserted_visual_count"))
    else:
        candidate_reason = info.get("reason")
        reason = candidate_reason if candidate_reason in SKIP_REASONS else None
        inserted_count = 0

    manifest_obj = manifest if isinstance(manifest, dict) else _read_json(
        _path(job, "visual_assets_manifest_json")
    )

    # Selected slugs / diagram flag from the actually-chosen candidates.
    selected_slugs: set[str] = set()
    diagram_selected = False
    for candidate in selected:
        if not isinstance(candidate, dict):
            continue
        slug = _safe_slug(candidate.get("asset_id"))
        if slug:
            selected_slugs.add(slug)
        vt = candidate.get("visual_type")
        if vt == VISUAL_TYPE_DIAGRAM:
            diagram_selected = True

    summary = _summarize_trace_candidates(job, manifest_obj, selected_slugs)
    safe_records = summary["safe_records"]
    rejection_counts = summary["rejection_counts"]
    any_table_accepted = any(
        r["visual_type"] == VISUAL_TYPE_TABLE and not r["decorative"] for r in safe_records
    )

    # Soft (post-quality) rejection tokens for safe candidates that were not selected.
    for record in safe_records:
        if record["selected"]:
            continue
        if record["decorative"]:
            _bump(rejection_counts, TRACE_REJECTED_LOW_QUALITY)
        elif record["score"] < _QG_SECONDARY_MIN_SCORE:
            _bump(rejection_counts, TRACE_REJECTED_SECONDARY_FLOOR)
        elif record["visual_type"] == VISUAL_TYPE_TABLE and diagram_selected:
            _bump(rejection_counts, TRACE_DEPRIORITIZED_TABLE)

    placement = _trace_placement(info)
    selected_candidates: list[dict[str, Any]] = []
    for rank, candidate in enumerate(selected):
        if not isinstance(candidate, dict):
            continue
        slug = _safe_slug(candidate.get("asset_id")) or "figure"
        vt = candidate.get("visual_type")
        vt = vt if vt in VISUAL_TYPES else VISUAL_TYPE_UNKNOWN
        if vt == VISUAL_TYPE_DIAGRAM and any_table_accepted:
            selection_reason = TRACE_SELECTED_DIAGRAM_FIRST
        elif rank == 0:
            selection_reason = TRACE_SELECTED_QUALITY
        else:
            selection_reason = TRACE_SELECTED_PRIORITY
        selected_candidates.append(
            {
                "asset_id": slug,
                "asset_ref": validate_visual_asset_ref(candidate.get("asset_ref")),
                "source_page": _safe_page(candidate.get("source_page")),
                "source_provider": SOURCE_PROVIDER_FITZ_LOCAL,
                "visual_type": vt,
                "visual_type_score": score_visual_type_priority_for_pilot(vt),
                "classification": _VT_TO_CLASSIFIED[vt],
                "quality_score": _safe_quality_score(candidate.get("quality_score")),
                "quality_reasons": _safe_quality_reasons(candidate.get("quality_reasons")),
                "placement": placement,
                "rank": rank,
                "selected": True,
                "selection_reason": selection_reason,
            }
        )

    candidate_summary = {
        "total_manifest_assets": summary["total_manifest_assets"],
        "safe_candidate_count": len(safe_records),
        "unsafe_candidate_count": summary["unsafe_candidate_count"],
        "selected_count": len(selected_candidates),
        "type_counts": {k: v for k, v in summary["type_counts"].items() if v},
        "rejection_reason_counts": {k: v for k, v in rejection_counts.items() if v},
    }

    return {
        "schema_version": SELECTION_TRACE_SCHEMA_VERSION,
        "status": status,
        "reason": reason,
        "effective_max_images": _coerce_max_images(max_images),
        "inserted_visual_count": inserted_count,
        "selected_candidates": selected_candidates,
        "candidate_summary": candidate_summary,
        "warnings": [],
    }


def _selection_trace_path(job: Any) -> str | None:
    job_dir = _job_dir(job)
    if job_dir is None:
        return None
    try:
        return os.path.join(os.fspath(job_dir), SELECTION_TRACE_FILENAME)
    except TypeError:
        return None


def _write_selection_trace(job: Any, trace: dict[str, Any]) -> None:
    path = _selection_trace_path(job)
    if path is None:
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(trace, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except Exception:
        pass


def _emit_selection_trace(
    job: Any, *, max_images: Any, selected: Any, info: Any
) -> None:
    """Build + persist the sanitized selection trace. Degrade-never-fail (Slice 68).

    Any problem building or writing the trace is swallowed so a diagnostic can never
    break generation; the trace is best-effort and advisory only.
    """
    try:
        trace = build_visual_markdown_selection_trace(
            job, max_images=max_images, selected=selected, info=info
        )
        _write_selection_trace(job, trace)
    except Exception:
        _log("Visual markdown pilot: selection trace skipped; job continues.")


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
