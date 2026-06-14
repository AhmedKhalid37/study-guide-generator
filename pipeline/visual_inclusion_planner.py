"""Full **non-table visual inclusion planner** core (Slice 83).

Full Material Coverage foundation. Slice 82 applied material page selections to
the *visual assets manifest* (excluded pages contribute no visual records). This
module adds the next, still-pure step: given a sanitized
``visual_assets_manifest.json``-shaped dict, decide which **non-table** figures /
diagrams / graphs / charts / images from the (already page-filtered) manifest
should be *planned* for future guide inclusion.

Product goal (not "insert every crop")
---------------------------------------
Include **all useful non-table visuals from included pages, after deterministic
safety filtering** — explicitly NOT every crop, logo, decorative header,
background, tiny/blank/low-information crop, or table-as-screenshot. This planner
therefore:

* plans **all eligible non-table** visual candidates by default (it is **not** the
  old top-1 / top-2 visual-pilot cap, and it does not hard-cap at 1 or 2);
* **skips table-like** candidates — table reconstruction / simplification is a
  separate, later policy slice (Slice 85), never screenshot insertion here;
* **skips decorative / logo / header / footer / background / watermark** crops,
  **low-information** pages, and **tiny** crops where deterministic manifest
  signals make that possible;
* drops records whose ``source_page`` cannot be verified (conservative);
* preserves the manifest's deterministic source-then-page ordering.

``max_items`` exists only as a defensive / test ceiling for pathological
documents. It is **not** a product cap and defaults to ``None`` (plan everything
eligible).

Scope (Slice 83 = planner-core only)
------------------------------------
This module is **pure and unwired**. It does NOT: read PDFs, inspect images, OCR,
crop, score, render, export, persist an artifact, call a provider / model / VLM /
Chandra / Mistral / Gemini, touch the job manager, or change Markdown insertion,
the visual-pilot ranking/classification/cap, or any API/UI. Plan persistence is
Slice 84; table policy is Slice 85; coverage E2E is Slice 86.

Purity & safety
---------------
stdlib-only. The plan emits **only** closed tokens, ints, ``None``, and fixed
strings. No filename, path, source title, caption, document/OCR/table text, image
ref, asset ref / asset id, image byte, base64 / data URI, provider payload, token,
URL, argv, socket path, model path, or raw exception string can survive into the
plan: input fields are read for *decisions only* and never echoed. The manifest's
internal ``asset_id`` is used solely for in-memory dedupe and is never emitted.
"""
from __future__ import annotations

from typing import Any

PLAN_VERSION = 1
PLAN_KIND = "visual_inclusion_plan"

# --- Closed status / warning vocabulary (this module owns what it emits) ------
MANIFEST_MISSING = "manifest_missing"
MANIFEST_MALFORMED = "manifest_malformed"
MANIFEST_SKIPPED = "manifest_skipped"
RECORD_MALFORMED = "record_malformed"
SOURCE_PAGE_MISSING = "source_page_missing"
SOURCE_PAGE_INVALID = "source_page_invalid"
VISUAL_TYPE_TABLE_SKIPPED = "visual_type_table_skipped"
VISUAL_TYPE_UNKNOWN = "visual_type_unknown"
VISUAL_RECORD_UNSAFE = "visual_record_unsafe"
VISUAL_RECORD_DECORATIVE = "visual_record_decorative"
VISUAL_RECORD_LOW_INFORMATION = "visual_record_low_information"
VISUAL_RECORD_TINY = "visual_record_tiny"
MAX_ITEMS_APPLIED = "max_items_applied"

# Deterministic warning ordering — the emitted ``warnings`` list is always this
# order filtered to the tokens that actually fired (no raw exception strings).
WARNING_ORDER = [
    MANIFEST_MISSING,
    MANIFEST_MALFORMED,
    MANIFEST_SKIPPED,
    RECORD_MALFORMED,
    SOURCE_PAGE_MISSING,
    SOURCE_PAGE_INVALID,
    VISUAL_TYPE_TABLE_SKIPPED,
    VISUAL_TYPE_UNKNOWN,
    VISUAL_RECORD_UNSAFE,
    VISUAL_RECORD_DECORATIVE,
    VISUAL_RECORD_LOW_INFORMATION,
    VISUAL_RECORD_TINY,
    MAX_ITEMS_APPLIED,
]

# --- Type-token vocabularies (defensive: cover today's manifest + future) -----
#
# Fields a record may carry a type/kind/category token in. Read for decisions
# only; never echoed. Today's manifest only populates ``asset_type``; the others
# are accepted defensively so a future provider tagging a record as e.g.
# ``"table"`` is skipped, and so a hostile record cannot smuggle a token through
# an unexpected field name.
_TYPE_FIELDS = ("asset_type", "visual_kind", "kind", "type", "category", "visual_type")

# A record carrying any of these is table-like → skipped (tables belong to the
# later reconstruction/simplification policy, never screenshot insertion here).
_TABLE_TYPE_TOKENS = {
    "table",
    "table_like",
    "grid_table",
    "dense_table",
    "table_region",
    "table_image",
    "tabular",
}

# Decorative / chrome / branding → skipped as not instructional content.
_DECORATIVE_TYPE_TOKENS = {
    "decorative",
    "logo",
    "header",
    "footer",
    "background",
    "watermark",
    "ornament",
}

# Explicit fine-grained non-table visual kinds (future providers may tag these).
_NONTABLE_KIND_TOKENS = {
    "diagram",
    "figure",
    "graph",
    "chart",
    "image",
    "plot",
    "illustration",
}

# Recognized non-table ``asset_type`` tokens from TODAY's manifest convention
# (``pipeline.visual_assets_manifest``). A ``page_visual_signal`` is a page-level
# signal (supporting); an ``extracted_figure`` is a real cropped region (primary).
_NONTABLE_ASSET_TYPES = {"page_visual_signal", "extracted_figure"}

# Emitted ``visual_kind`` vocabulary (closed). ``plot`` maps to ``graph`` and
# ``illustration`` to ``figure`` so the output stays in this small set.
_OUTPUT_KINDS = {"diagram", "figure", "graph", "chart", "image", "unknown"}
_KIND_ALIASES = {"plot": "graph", "illustration": "figure"}

INCLUSION_REASON = "non_table_visual_from_included_page"
ROLE_PRIMARY = "primary_visual"
ROLE_SUPPORTING = "supporting_visual"

# Crops smaller than this in either pixel dimension are treated as tiny/low-value
# (only ``extracted_figure`` crops carry ``crop_*_px``; page-level signals never
# trip this).
_MIN_CROP_PX = 24

_MISSING = object()


def build_visual_inclusion_plan(
    visual_manifest: Any,
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Pure planner: sanitized visual manifest dict → sanitized inclusion plan.

    ``visual_manifest`` is a ``visual_assets_manifest.json``-shaped dict (as built
    by :mod:`pipeline.visual_assets_manifest`, already material-page-filtered by
    Slice 82). Only its ``status`` and ``assets`` list are consulted.

    ``max_items`` is an optional **defensive ceiling**, NOT a product cap. Default
    ``None`` plans every eligible non-table visual. When passed as a non-negative
    int and fewer items survive than the plan would otherwise contain, the plan is
    truncated in deterministic order, ``status`` becomes ``"partial"``, and
    ``max_items_applied`` is recorded. Any other value is ignored.

    Returns a plan dict with ``version``, ``kind``, ``status``
    (``completed``/``partial``/``skipped``), ``summary``, ``items``, ``warnings``.
    Pure and total: never raises, never inspects a PDF/image, never calls a
    provider. On any unexpected input it degrades to a safe ``skipped`` plan.
    """
    try:
        return _build(visual_manifest, max_items)
    except Exception:
        return _skipped_plan(MANIFEST_MALFORMED)


def _build(visual_manifest: Any, max_items: Any) -> dict[str, Any]:
    if visual_manifest is None:
        return _skipped_plan(MANIFEST_MISSING)
    if not isinstance(visual_manifest, dict):
        return _skipped_plan(MANIFEST_MALFORMED)

    status = visual_manifest.get("status")
    if isinstance(status, str) and status.strip().lower() == "skipped":
        return _skipped_plan(MANIFEST_SKIPPED)

    assets = visual_manifest.get("assets")
    if assets is None:
        # No assets key but an otherwise-valid manifest ⇒ nothing to plan.
        assets = []
    if not isinstance(assets, list):
        return _skipped_plan(MANIFEST_MALFORMED)

    warnings: set[str] = set()
    source_indexes: set[int] = set()
    seen_ids: set[str] = set()
    planned: list[dict[str, Any]] = []
    candidate_count = 0
    table_skipped = 0
    unsafe_or_incomplete = 0

    for position, record in enumerate(assets):
        if not isinstance(record, dict):
            warnings.add(RECORD_MALFORMED)
            unsafe_or_incomplete += 1
            continue
        candidate_count += 1

        source_index = _coerce_source_index(record.get("source_index"))
        if source_index is not None:
            source_indexes.add(source_index)

        cls, visual_kind, role = _classify(record)
        if cls == "table":
            table_skipped += 1
            warnings.add(VISUAL_TYPE_TABLE_SKIPPED)
            continue
        if cls == "decorative":
            unsafe_or_incomplete += 1
            warnings.add(VISUAL_RECORD_DECORATIVE)
            continue
        if cls == "unknown":
            unsafe_or_incomplete += 1
            warnings.add(VISUAL_TYPE_UNKNOWN)
            continue

        # cls == "nontable" from here on — apply deterministic safety filters.
        if _is_unsafe(record):
            unsafe_or_incomplete += 1
            warnings.add(VISUAL_RECORD_UNSAFE)
            continue
        if _is_low_information(record):
            unsafe_or_incomplete += 1
            warnings.add(VISUAL_RECORD_LOW_INFORMATION)
            continue
        if _is_tiny(record):
            unsafe_or_incomplete += 1
            warnings.add(VISUAL_RECORD_TINY)
            continue

        page, page_status = _resolve_source_page(record)
        if page is None:
            unsafe_or_incomplete += 1
            warnings.add(page_status)
            continue

        identity = _stable_identity(record)
        if identity is not None:
            if identity in seen_ids:
                continue  # exact-duplicate record, silently collapsed
            seen_ids.add(identity)

        planned.append(
            {
                "source_index": source_index,
                "source_page": page,
                "visual_kind": visual_kind,
                "role": role,
                "position": position,
            }
        )

    # Deterministic ordering: source order, then page, then original manifest
    # position. Manifest order already encodes this; the stable sort makes the
    # guarantee explicit and robust to mildly out-of-order inputs.
    planned.sort(key=lambda p: (p["source_index"] if p["source_index"] is not None else 0,
                                p["source_page"], p["position"]))

    plan_status = "completed"
    if isinstance(max_items, int) and not isinstance(max_items, bool) and max_items >= 0:
        if len(planned) > max_items:
            planned = planned[:max_items]
            warnings.add(MAX_ITEMS_APPLIED)
            plan_status = "partial"

    items: list[dict[str, Any]] = []
    for index, p in enumerate(planned, start=1):
        items.append(
            {
                "plan_index": index,
                "source_index": p["source_index"],
                "source_page": p["source_page"],
                "visual_kind": p["visual_kind"],
                "inclusion_role": p["role"],
                "reason": INCLUSION_REASON,
                "warnings": [],
            }
        )

    pages_with_plan = len({item["source_page"] for item in items})
    summary = {
        "source_count": len(source_indexes),
        "candidate_count": candidate_count,
        "planned_count": len(items),
        "non_table_planned_count": len(items),
        "table_like_skipped_count": table_skipped,
        "unsafe_or_incomplete_skipped_count": unsafe_or_incomplete,
        "page_count_with_planned_visuals": pages_with_plan,
    }
    return _finalize(plan_status, summary, items, warnings)


# --- Classification ----------------------------------------------------------


def _classify(record: dict[str, Any]) -> tuple[str, str | None, str | None]:
    """Return ``(class, visual_kind, role)`` for a record.

    ``class`` is one of ``"table"``, ``"decorative"``, ``"nontable"``,
    ``"unknown"``. ``visual_kind`` / ``role`` are only set for ``"nontable"``.
    Table wins over everything (skip), then decorative, then an explicit non-table
    kind, then a recognized non-table ``asset_type``, else unknown.
    """
    tokens: set[str] = set()
    for field in _TYPE_FIELDS:
        value = record.get(field)
        if isinstance(value, str):
            token = value.strip().lower()
            if token:
                tokens.add(token)

    if tokens & _TABLE_TYPE_TOKENS:
        return "table", None, None
    if tokens & _DECORATIVE_TYPE_TOKENS:
        return "decorative", None, None

    explicit = tokens & _NONTABLE_KIND_TOKENS
    if explicit:
        # Deterministic: first by the fixed kind ordering, not set iteration.
        for token in ("diagram", "figure", "graph", "chart", "image", "plot", "illustration"):
            if token in explicit:
                return "nontable", _map_kind(token), ROLE_PRIMARY

    asset_type = record.get("asset_type")
    if isinstance(asset_type, str):
        at = asset_type.strip().lower()
        if at == "extracted_figure":
            return "nontable", "figure", ROLE_PRIMARY
        if at == "page_visual_signal":
            return "nontable", _kind_from_signals(record), ROLE_SUPPORTING

    return "unknown", None, None


def _map_kind(token: str) -> str:
    mapped = _KIND_ALIASES.get(token, token)
    return mapped if mapped in _OUTPUT_KINDS else "image"


def _kind_from_signals(record: dict[str, Any]) -> str:
    """Best-effort non-table kind for a page-level signal from safe numeric/bool.

    Drawings-only ⇒ ``diagram``; otherwise ⇒ ``image``. Never echoes input text.
    """
    signals = record.get("signals")
    if not isinstance(signals, dict):
        return "image"
    images = _truthy_signal(signals.get("has_images"), signals.get("image_object_count"))
    drawings = _truthy_signal(signals.get("has_drawings"), signals.get("drawing_object_count"))
    if drawings and not images:
        return "diagram"
    return "image"


def _truthy_signal(flag: Any, count: Any) -> bool:
    if flag is True:
        return True
    try:
        return int(count) > 0
    except (TypeError, ValueError):
        return False


# --- Deterministic safety filters --------------------------------------------


def _is_unsafe(record: dict[str, Any]) -> bool:
    if record.get("unsafe") is True:
        return True
    if record.get("safe") is False:
        return True
    record_warnings = record.get("warnings")
    if isinstance(record_warnings, (list, tuple)):
        for token in record_warnings:
            if isinstance(token, str) and "unsafe" in token.lower():
                return True
    return False


def _is_low_information(record: dict[str, Any]) -> bool:
    signals = record.get("signals")
    if isinstance(signals, dict):
        classification = signals.get("classification")
        if isinstance(classification, str) and classification.strip().lower() == "blank_or_low_text":
            return True
    return False


def _is_tiny(record: dict[str, Any]) -> bool:
    signals = record.get("signals")
    if not isinstance(signals, dict):
        return False
    for key in ("crop_width_px", "crop_height_px"):
        value = signals.get(key)
        try:
            pixels = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= pixels < _MIN_CROP_PX:
            return True
    return False


# --- Field coercion (read for decisions; never echo raw input) ---------------


def _coerce_source_index(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _resolve_source_page(record: dict[str, Any]) -> tuple[int | None, str | None]:
    raw = record.get("source_page", _MISSING)
    if raw is _MISSING or raw is None:
        return None, SOURCE_PAGE_MISSING
    # Strict: the manifest persists ``source_page`` as a positive int. A float,
    # string, or bool is not a verifiable 1-based page and is dropped conservatively
    # (never silently truncated, e.g. 1.5 → 1).
    if not isinstance(raw, int) or isinstance(raw, bool):
        return None, SOURCE_PAGE_INVALID
    if raw <= 0:
        return None, SOURCE_PAGE_INVALID
    return raw, None


def _stable_identity(record: dict[str, Any]) -> str | None:
    """Manifest-internal identity for dedupe ONLY — never emitted into the plan."""
    asset_id = record.get("asset_id")
    if isinstance(asset_id, str) and asset_id.strip():
        return asset_id.strip()
    return None


# --- Plan assembly -----------------------------------------------------------


def _finalize(
    status: str,
    summary: dict[str, Any],
    items: list[dict[str, Any]],
    warnings: set[str],
) -> dict[str, Any]:
    return {
        "version": PLAN_VERSION,
        "kind": PLAN_KIND,
        "status": status,
        "summary": summary,
        "items": items,
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


def _skipped_plan(warning: str) -> dict[str, Any]:
    summary = {
        "source_count": 0,
        "candidate_count": 0,
        "planned_count": 0,
        "non_table_planned_count": 0,
        "table_like_skipped_count": 0,
        "unsafe_or_incomplete_skipped_count": 0,
        "page_count_with_planned_visuals": 0,
    }
    return _finalize("skipped", summary, [], {warning})
