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

# Caption is plain text only: a tiny safe charset, collapsed whitespace, bounded
# length. Everything else is stripped, so a caption can never carry markup, a path,
# a URL, or private text into the guide.
_CAPTION_SAFE_RE = re.compile(r"[^A-Za-z0-9 .,:%()\-]")
_MAX_CAPTION_LEN = 80

# Heading used for the dumb fallback placement when no deterministic source-page
# anchor marker is present in the guide.
_VISUAL_REFERENCE_HEADING = "## Visual Reference"

# Deterministic, safe source-page anchor marker convention. When the guide already
# carries ``<!-- visual-anchor: source_page_0003 -->`` for the figure's page, the
# image is placed right at that anchor; otherwise the fallback section is appended.
_ANCHOR_MARKER_TEMPLATE = "<!-- visual-anchor: source_page_{page:04d} -->"

# Closed skip/outcome vocabulary (diagnostic only; never embedded in the guide).
SKIP_DISABLED = "visual_pilot_disabled"
SKIP_JOB_OPT_OUT = "visual_pilot_job_opt_out"
SKIP_CANDIDATE_UNAVAILABLE = "visual_candidate_unavailable"
SKIP_CANDIDATE_UNSAFE = "visual_candidate_unsafe"
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
    SKIP_ASSET_MISSING,
    SKIP_ASSET_PATH_INVALID,
    SKIP_INSERT_FAILED,
    SKIP_FORMAT_UNSUPPORTED,
    SKIP_RENDER_DEGRADED,
}

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
        candidate, reason = _pick_candidate(job)
        if candidate is None:
            _log(f"Visual markdown pilot: no figure inserted ({reason}).")
            return text, {"status": "skipped", "reason": reason}
        new_text, info = insert_visual_markdown_reference(text, candidate)
        if info.get("status") != STATUS_INSERTED:
            _log(f"Visual markdown pilot: no figure inserted ({info.get('reason')}).")
            return text, info
        _log(
            "Visual markdown pilot: inserted one figure "
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


def _pick_candidate(
    job: Any,
    *,
    manifest: Any = None,
    replacement_plan: Any = None,
) -> tuple[dict[str, Any] | None, str]:
    """Selection core returning ``(candidate_or_None, closed_reason)``."""
    manifest_obj = manifest if isinstance(manifest, dict) else _read_json(_path(job, "visual_assets_manifest_json"))
    if not isinstance(manifest_obj, dict):
        return None, SKIP_CANDIDATE_UNAVAILABLE

    assets_by_id = _safe_figure_assets(manifest_obj)
    if not assets_by_id:
        return None, SKIP_CANDIDATE_UNAVAILABLE

    saw_unsafe = False

    # Preferred: a replacement-plan include-as-figure item, resolved in the manifest.
    plan_obj = replacement_plan if isinstance(replacement_plan, dict) else _read_json(
        _path(job, "visual_replacement_plan_json")
    )
    for asset_id in _plan_figure_asset_ids(plan_obj):
        asset = assets_by_id.get(asset_id)
        if asset is None:
            continue
        built, ok = _build_candidate_from_asset(job, asset, origin="replacement_plan")
        if built is not None:
            return built, STATUS_INSERTED
        if not ok:
            saw_unsafe = True

    # Fallback: first safe extracted figure in manifest order (flag-on only path).
    for asset in _ordered_figure_assets(manifest_obj):
        built, ok = _build_candidate_from_asset(job, asset, origin="manifest")
        if built is not None:
            return built, STATUS_INSERTED
        if not ok:
            saw_unsafe = True

    return None, (SKIP_CANDIDATE_UNSAFE if saw_unsafe else SKIP_CANDIDATE_UNAVAILABLE)


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


def _log(message: str) -> None:
    # Closed-vocabulary, path-free diagnostics only; never echoes asset content.
    print(message, file=sys.stderr)
