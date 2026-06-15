"""Missing diagram/table **explainer context** core (Slice 94).

Full Material Coverage foundation. Slices 90–91 made full non-table figure
insertion safe; Slices 92–93 added the sanitized table candidate/policy artifacts
and a safe table reconstruction *prompt context*. Slice 94 adds the last honest
piece: when useful visual or table-like material is **detected but cannot be
included or reconstructed**, produce safe guidance so the generated guide can tell
the student *what kind of item was missing and on which page* — without inventing
its contents.

Product goal (honest "what was missing", never hallucinated)
------------------------------------------------------------
* A table the policy chose to ``defer`` or ``skip_unreadable`` → tell the model to
  emit an honest "table-like material was detected on page N but its contents were
  not readable" note, and never invent rows/columns/labels/values.
* A table flagged ``skip_unsafe`` → never surfaced as something to explain (counted
  only).
* Non-table visuals that were *planned* for inclusion but full visual insertion is
  **disabled** → tell the model a figure/diagram was detected on page N but was not
  available for automatic insertion, and to point the student at the source page.
* When full visual insertion is **enabled**, planned visuals are NOT marked missing
  unless a closed insertion-failure signal exists. There is no insertion-status
  artifact today, so this core never invents a failure.

Scope (Slice 94 = pure core + safe prompt context)
--------------------------------------------------
Pure derivation only. It does NOT inspect PDFs/images, OCR, read image bytes,
extract table text, reconstruct a table, generate image-derived diagram
explanations, call a provider/model/cloud, change render/export, change figure
insertion semantics, change visual-manifest filtering, change material page
selection, or add UI. It reads ONLY the already-sanitized Slice 84/85/92 artifact
dicts (visual inclusion plan + table candidate manifest + table reconstruction
policy) and returns a sanitized context dict whose ``prompt_block`` is safe to
append to the existing generation prompt.

Purity & safety
---------------
stdlib-only (imports nothing from ``pipeline`` and no provider/model/OCR/renderer/
FastAPI/frontend module). The context emits **only** closed tokens, ints, ``None``,
fixed instruction strings built from those, and a safe generated ``item_id`` of the
fixed shape ``missing_material_NNNN``. No filename, path, source title, caption,
document / OCR / table text, image ref, asset ref / asset id, image byte, base64 /
data URI, provider payload, token, URL, argv, socket path, model path, or raw
exception string can survive into it: input fields are read for *decisions only*
and never echoed. Never raises; any malformed input degrades to a safe ``skipped`` /
empty context.
"""
from __future__ import annotations

from typing import Any

CONTEXT_VERSION = 1
CONTEXT_KIND = "missing_material_explainer_context"

# --- Closed material-kind vocabulary -----------------------------------------
MATERIAL_DIAGRAM = "diagram"
MATERIAL_FIGURE = "figure"
MATERIAL_GRAPH = "graph"
MATERIAL_CHART = "chart"
MATERIAL_TABLE = "table"
MATERIAL_TABLE_LIKE = "table_like"
MATERIAL_UNKNOWN = "unknown"

# Closed map: a planner ``visual_kind`` token → our material kind (defaults to
# unknown). The planner already emits a closed set {diagram, figure, graph, chart,
# image, unknown}; ``image`` collapses to the generic ``figure``.
_VISUAL_KIND_MAP = {
    "diagram": MATERIAL_DIAGRAM,
    "figure": MATERIAL_FIGURE,
    "graph": MATERIAL_GRAPH,
    "chart": MATERIAL_CHART,
    "image": MATERIAL_FIGURE,
    "unknown": MATERIAL_UNKNOWN,
}
# Closed map: a policy ``table_kind`` token → our table material kind.
_TABLE_KIND_MAP = {
    "grid_table": MATERIAL_TABLE,
    "dense_table": MATERIAL_TABLE,
    "table_like": MATERIAL_TABLE_LIKE,
    "unknown": MATERIAL_TABLE_LIKE,
}

# Safe human phrase per material kind (closed; never source content).
_MATERIAL_PHRASE = {
    MATERIAL_DIAGRAM: "diagram",
    MATERIAL_FIGURE: "figure",
    MATERIAL_GRAPH: "graph",
    MATERIAL_CHART: "chart",
    MATERIAL_TABLE: "table",
    MATERIAL_TABLE_LIKE: "table-like material",
    MATERIAL_UNKNOWN: "visual",
}

# --- Closed reason vocabulary ------------------------------------------------
REASON_VISUAL_NOT_INSERTED = "visual_not_inserted"
REASON_TABLE_DEFERRED = "table_deferred"
REASON_TABLE_UNREADABLE = "table_unreadable"
REASON_TABLE_UNSAFE = "table_unsafe"
REASON_CONTENT_UNAVAILABLE = "content_unavailable"

# --- Closed policy action tokens we react to ---------------------------------
_ACTION_DEFER = "defer"
_ACTION_SKIP_UNREADABLE = "skip_unreadable"
_ACTION_SKIP_UNSAFE = "skip_unsafe"
# reconstruct_with_original / simplify_only are handled by the Slice 93 table
# reconstruction prompt context, never by this missing-material explainer.

# --- Closed warning vocabulary (this module owns what it emits) --------------
ALL_INPUTS_MISSING = "all_inputs_missing"
PLAN_MALFORMED = "plan_malformed"
TABLE_POLICY_MALFORMED = "table_policy_malformed"
TABLE_MANIFEST_MALFORMED = "table_manifest_malformed"
ITEM_MALFORMED = "item_malformed"
SOURCE_PAGE_INVALID = "source_page_invalid"
UNSAFE_SKIPPED = "unsafe_skipped"
VISUAL_INSERTION_ENABLED_NO_FAILURE_SIGNAL = "visual_insertion_enabled_no_failure_signal"
MAX_ITEMS_APPLIED = "max_items_applied"

# Deterministic emitted warning ordering (closed tokens only, never raw text).
WARNING_ORDER = [
    ALL_INPUTS_MISSING,
    PLAN_MALFORMED,
    TABLE_POLICY_MALFORMED,
    TABLE_MANIFEST_MALFORMED,
    ITEM_MALFORMED,
    SOURCE_PAGE_INVALID,
    UNSAFE_SKIPPED,
    VISUAL_INSERTION_ENABLED_NO_FAILURE_SIGNAL,
    MAX_ITEMS_APPLIED,
]

# Safe generated item-id shape.
ITEM_ID_PREFIX = "missing_material_"

# Defensive full ceiling — guards a pathological input, NOT a product cap.
_PROMPT_ITEM_HARD_CEILING = 500

# Category rank for deterministic per-page ordering (table before visual).
_CATEGORY_TABLE = 0
_CATEGORY_VISUAL = 1

# Static, leak-free guidance lines prepended to every non-empty prompt block.
_GUIDANCE_LINES = (
    "Missing visual/table guidance:",
    "- Some included pages may contain visual or table-like material that could "
    "not be inserted or reconstructed.",
    "- Do not invent labels, rows, values, or diagram details that are not present "
    "in the provided source text.",
    "- When material is unavailable, add a short note telling the student what kind "
    "of item was detected and on which page.",
    "- For unreadable tables, say that table-like material was detected but its "
    "contents were not readable from the provided text.",
    "- For missing diagrams or figures, say that a figure or diagram was detected "
    "but was not available for explanation.",
)


# =============================================================================
# Public API
# =============================================================================


def build_missing_material_explainer_context(
    visual_inclusion_plan: dict | None,
    table_candidates_manifest: dict | None,
    table_reconstruction_policy: dict | None,
    *,
    full_visual_insertion_enabled: bool = False,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Pure builder: sanitized plan/manifest/policy -> missing-material context.

    Reads only the already-sanitized Slice 84 visual inclusion plan, Slice 92 table
    candidate manifest, and Slice 85/92 table reconstruction policy. Produces honest
    "what was missing" guidance:

    * table policy ``defer`` / ``skip_unreadable`` → a missing-table item;
    * table policy ``skip_unsafe`` → counted only (never surfaced for explanation);
    * planned non-table visuals + ``full_visual_insertion_enabled=False`` → a
      missing-visual item (insertion was not enabled);
    * ``full_visual_insertion_enabled=True`` → planned visuals are NOT marked
      missing (no insertion-failure signal exists; failure is never invented).

    ``max_items`` is an optional **defensive ceiling**, NOT a product cap. Items with
    an unverifiable page are dropped. Returns a context dict with ``version``,
    ``kind``, ``status`` (``completed``/``partial``/``skipped``), ``summary``,
    ``items``, ``prompt_block``, ``warnings``. Pure and total: never raises,
    reconstructs no table, inspects no PDF/image, calls no provider. On any
    unexpected input it degrades to a safe ``skipped`` context with an empty
    ``prompt_block``.
    """
    try:
        return _build(
            visual_inclusion_plan,
            table_candidates_manifest,
            table_reconstruction_policy,
            bool(full_visual_insertion_enabled),
            max_items,
        )
    except Exception:
        return _skipped_context(ALL_INPUTS_MISSING)


# =============================================================================
# Builder
# =============================================================================


def _build(
    plan: Any,
    manifest: Any,
    policy: Any,
    full_insertion_enabled: bool,
    max_items: Any,
) -> dict[str, Any]:
    warnings: set[str] = set()

    if plan is None and manifest is None and policy is None:
        return _skipped_context(ALL_INPUTS_MISSING)

    unsafe_skipped = 0
    # (category_rank, page, original_index, item) tuples for deterministic ordering.
    staged: list[tuple[int, int, int, dict[str, Any]]] = []

    # --- Missing tables (from the table reconstruction policy) ----------------
    if manifest is not None and not isinstance(manifest, dict):
        warnings.add(TABLE_MANIFEST_MALFORMED)
    table_items = _table_policy_items(policy, warnings)
    for order, raw in enumerate(table_items):
        if not isinstance(raw, dict):
            warnings.add(ITEM_MALFORMED)
            continue
        action = raw.get("action")
        action = action.strip().lower() if isinstance(action, str) else ""
        if action == _ACTION_SKIP_UNSAFE:
            unsafe_skipped += 1
            warnings.add(UNSAFE_SKIPPED)
            continue
        if action not in (_ACTION_DEFER, _ACTION_SKIP_UNREADABLE):
            # reconstruct/simplify (handled by Slice 93) or unknown → not "missing".
            continue
        page = _coerce_page(raw.get("source_page"))
        if page is None:
            warnings.add(SOURCE_PAGE_INVALID)
            continue
        material_kind = _TABLE_KIND_MAP.get(
            _token(raw.get("table_kind")), MATERIAL_TABLE_LIKE
        )
        reason = (
            REASON_TABLE_DEFERRED if action == _ACTION_DEFER else REASON_TABLE_UNREADABLE
        )
        staged.append(
            (
                _CATEGORY_TABLE,
                page,
                order,
                {
                    "source_page": page,
                    "material_kind": material_kind,
                    "reason": reason,
                    "instruction": _table_instruction(page),
                    "warnings": [],
                },
            )
        )

    # --- Missing non-table visuals (from the visual inclusion plan) -----------
    plan_items = _plan_items(plan, warnings)
    if full_insertion_enabled:
        # Full insertion is on; without a closed insertion-failure signal we never
        # invent a failure, so planned visuals are not treated as missing.
        if plan_items:
            warnings.add(VISUAL_INSERTION_ENABLED_NO_FAILURE_SIGNAL)
    else:
        for order, raw in enumerate(plan_items):
            if not isinstance(raw, dict):
                warnings.add(ITEM_MALFORMED)
                continue
            page = _coerce_page(raw.get("source_page"))
            if page is None:
                warnings.add(SOURCE_PAGE_INVALID)
                continue
            material_kind = _VISUAL_KIND_MAP.get(
                _token(raw.get("visual_kind")), MATERIAL_UNKNOWN
            )
            staged.append(
                (
                    _CATEGORY_VISUAL,
                    page,
                    order,
                    {
                        "source_page": page,
                        "material_kind": material_kind,
                        "reason": REASON_VISUAL_NOT_INSERTED,
                        "instruction": _visual_instruction(page, material_kind),
                        "warnings": [],
                    },
                )
            )

    # Deterministic order: by page, then table-before-visual, then input order.
    staged.sort(key=lambda entry: (entry[1], entry[0], entry[2]))

    status_token = "completed"
    ceiling = _PROMPT_ITEM_HARD_CEILING
    if isinstance(max_items, int) and not isinstance(max_items, bool) and max_items >= 0:
        ceiling = min(ceiling, max_items)
    if len(staged) > ceiling:
        staged = staged[:ceiling]
        warnings.add(MAX_ITEMS_APPLIED)
        status_token = "partial"

    items: list[dict[str, Any]] = []
    for index, (category, _page, _order, item) in enumerate(staged, start=1):
        item["item_id"] = f"{ITEM_ID_PREFIX}{index:04d}"
        # Reorder keys deterministically with item_id first.
        items.append(
            {
                "item_id": item["item_id"],
                "source_page": item["source_page"],
                "material_kind": item["material_kind"],
                "reason": item["reason"],
                "instruction": item["instruction"],
                "warnings": item["warnings"],
            }
        )

    if not items:
        # Nothing honest to say (all inputs empty/skipped/handled elsewhere).
        return _skipped_context_with(warnings, unsafe_skipped)

    summary = _summarize(items, unsafe_skipped)
    prompt_block = _prompt_block(items)
    return _finalize(status_token, summary, items, prompt_block, warnings)


# --- Input extraction (read for decisions; never echo raw input) -------------


def _table_policy_items(policy: Any, warnings: set[str]) -> list[Any]:
    if policy is None:
        return []
    if not isinstance(policy, dict):
        warnings.add(TABLE_POLICY_MALFORMED)
        return []
    status = policy.get("status")
    if isinstance(status, str) and status.strip().lower() == "skipped":
        return []
    items = policy.get("items")
    if items is None:
        return []
    if not isinstance(items, list):
        warnings.add(TABLE_POLICY_MALFORMED)
        return []
    return items


def _plan_items(plan: Any, warnings: set[str]) -> list[Any]:
    if plan is None:
        return []
    if not isinstance(plan, dict):
        warnings.add(PLAN_MALFORMED)
        return []
    status = plan.get("status")
    if isinstance(status, str) and status.strip().lower() == "skipped":
        return []
    items = plan.get("items")
    if items is None:
        return []
    if not isinstance(items, list):
        warnings.add(PLAN_MALFORMED)
        return []
    return items


# =============================================================================
# Instruction / prompt-block text (closed; never echoes raw input)
# =============================================================================


def _table_instruction(page: int) -> str:
    return (
        f"Table-like material was detected on page {page}, but its contents were not "
        f"readable from the provided source text. Add a short note that table-like "
        f"material was detected on page {page} but its contents were not available, "
        f"and do not invent rows, columns, labels, or values."
    )


def _visual_instruction(page: int, material_kind: str) -> str:
    phrase = _MATERIAL_PHRASE.get(material_kind, "visual")
    return (
        f"A {phrase} was detected on page {page} but was not available for automatic "
        f"insertion. Add a short note telling the student to consult the original "
        f"source page for its labels and details, and do not invent its contents, "
        f"labels, or values."
    )


def _prompt_block(items: list[dict[str, Any]]) -> str:
    lines = list(_GUIDANCE_LINES)
    lines.append("Detected missing material:")
    for item in items:
        lines.append(f"- {_bullet(item)}")
    return "\n".join(lines)


def _bullet(item: dict[str, Any]) -> str:
    page = item["source_page"]
    if item["reason"] in (REASON_TABLE_DEFERRED, REASON_TABLE_UNREADABLE):
        return (
            f"Page {page}: table-like material detected; contents not readable from "
            "provided text."
        )
    phrase = _MATERIAL_PHRASE.get(item["material_kind"], "visual")
    return f"Page {page}: {phrase} detected; use the source page for labels and details."


# =============================================================================
# Field coercion
# =============================================================================


def _coerce_page(value: Any) -> int | None:
    # Strict: a verifiable 1-based page is a positive int (never a float/str/bool).
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return value if value > 0 else None


def _token(value: Any) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


# =============================================================================
# Assembly
# =============================================================================


def _summarize(items: list[dict[str, Any]], unsafe_skipped: int) -> dict[str, Any]:
    missing_table = sum(
        1
        for item in items
        if item["reason"] in (REASON_TABLE_DEFERRED, REASON_TABLE_UNREADABLE)
    )
    missing_visual = sum(
        1 for item in items if item["reason"] == REASON_VISUAL_NOT_INSERTED
    )
    deferred = sum(1 for item in items if item["reason"] == REASON_TABLE_DEFERRED)
    unreadable = sum(1 for item in items if item["reason"] == REASON_TABLE_UNREADABLE)
    return {
        "missing_visual_count": missing_visual,
        "missing_table_count": missing_table,
        "prompt_item_count": len(items),
        "deferred_count": deferred,
        "unreadable_count": unreadable,
        "unsafe_skipped_count": unsafe_skipped,
    }


def _finalize(
    status: str,
    summary: dict[str, Any],
    items: list[dict[str, Any]],
    prompt_block: str,
    warnings: set[str],
) -> dict[str, Any]:
    return {
        "version": CONTEXT_VERSION,
        "kind": CONTEXT_KIND,
        "status": status,
        "summary": summary,
        "items": items,
        "prompt_block": prompt_block,
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


def _skipped_context(warning: str) -> dict[str, Any]:
    return _skipped_context_with({warning}, 0)


def _skipped_context_with(warnings: set[str], unsafe_skipped: int) -> dict[str, Any]:
    summary = {
        "missing_visual_count": 0,
        "missing_table_count": 0,
        "prompt_item_count": 0,
        "deferred_count": 0,
        "unreadable_count": 0,
        "unsafe_skipped_count": unsafe_skipped,
    }
    return _finalize("skipped", summary, [], "", warnings)
