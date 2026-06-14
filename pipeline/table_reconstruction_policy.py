"""Table **reconstruction / simplification policy** core (Slice 85).

Full Material Coverage foundation. Slice 83 added the pure non-table *visual
inclusion planner* and Slice 84 persisted its plan (``visual_inclusion_plan.json``).
Both deliberately **skip table-like material** — tables must not be treated as
ordinary screenshot visuals. This module adds the next, still-pure step: a
deterministic **decision layer** for what should later happen to a table-like
candidate.

Product goal (tables are not screenshots)
-----------------------------------------
A table should generally **not** be inserted as a screenshot. Future behavior
should prefer reconstructed, study-friendly content:

* ``reconstruct_with_original`` — keep the original table text *and* add a simpler,
  clearer version (only when a usable text layer + structure exist);
* ``simplify_only`` — produce a simpler/clearer version (when structure exists but
  the original text layer is absent / unknown);
* ``defer`` — postpone the decision (low confidence, or the page cannot yet be
  anchored) rather than guess;
* ``skip_unreadable`` — drop a table with insufficient structure to reconstruct;
* ``skip_unsafe`` — drop a record flagged unsafe.

Whichever mode is chosen later, the necessary keywords / exam terms / headers /
units / labels / numeric values must be preserved (see the ``preserve`` list).
**Screenshot insertion is never the default table behavior** — the policy never
emits a screenshot action and ``screenshot_insert_count`` is always ``0``.

Scope (Slice 85 = policy-core only)
-----------------------------------
This module is **pure and unwired**. It does NOT reconstruct any table, read PDFs,
inspect images, OCR, render, export, persist an artifact, build/consume a table
manifest, change any prompt, call a provider / model / VLM / Chandra / Mistral /
Gemini, touch the job manager, or change Markdown insertion, the visual-inclusion
planner, the visual-pilot ranking/classification/cap, or any API/UI. There is no
table manifest today and this slice invents none — it evaluates synthetic /
sanitized *table-candidate-shaped* dicts only and returns a sanitized policy dict.

Purity & safety
---------------
stdlib-only. The policy emits **only** closed tokens, ints, ``None``, and fixed
strings. No filename, path, source title, caption, document / OCR / table text,
image ref, asset ref / asset id, image byte, base64 / data URI, provider payload,
token, URL, argv, socket path, model path, or raw exception string can survive
into the output: input fields are read for *decisions only* and never echoed.
Never raises and is total: any malformed input degrades to a safe skipped policy.
"""
from __future__ import annotations

from typing import Any

POLICY_VERSION = 1
POLICY_KIND = "table_reconstruction_policy"

# --- Closed action vocabulary (this module owns what it emits) ----------------
ACTION_RECONSTRUCT_WITH_ORIGINAL = "reconstruct_with_original"
ACTION_SIMPLIFY_ONLY = "simplify_only"
ACTION_DEFER = "defer"
ACTION_SKIP_UNREADABLE = "skip_unreadable"
ACTION_SKIP_UNSAFE = "skip_unsafe"

# --- Closed warning / reason vocabulary --------------------------------------
CANDIDATE_MISSING = "candidate_missing"
CANDIDATE_MALFORMED = "candidate_malformed"
SOURCE_PAGE_MISSING = "source_page_missing"
SOURCE_PAGE_INVALID = "source_page_invalid"
NOT_TABLE_LIKE = "not_table_like"
TEXT_LAYER_AVAILABLE = "text_layer_available"
TEXT_LAYER_MISSING = "text_layer_missing"
TEXT_LAYER_UNKNOWN = "text_layer_unknown"
INSUFFICIENT_STRUCTURE = "insufficient_structure"
LOW_CONFIDENCE = "low_confidence"
UNSAFE_RECORD = "unsafe_record"
MAX_ITEMS_APPLIED = "max_items_applied"

# Deterministic top-level warning ordering. ``text_layer_available`` is the happy
# path (a *reason*, not a warning) and is intentionally NOT a warning token.
WARNING_ORDER = [
    CANDIDATE_MISSING,
    CANDIDATE_MALFORMED,
    NOT_TABLE_LIKE,
    SOURCE_PAGE_MISSING,
    SOURCE_PAGE_INVALID,
    TEXT_LAYER_MISSING,
    TEXT_LAYER_UNKNOWN,
    INSUFFICIENT_STRUCTURE,
    LOW_CONFIDENCE,
    UNSAFE_RECORD,
    MAX_ITEMS_APPLIED,
]

# --- Closed table-kind vocabulary --------------------------------------------
KIND_GRID_TABLE = "grid_table"
KIND_DENSE_TABLE = "dense_table"
KIND_TABLE_LIKE = "table_like"
KIND_UNKNOWN = "unknown"

# Fields a candidate may carry a kind/type/signal token in. Read for decisions
# only; never echoed. ``asset_type`` is accepted defensively so a hostile record
# cannot smuggle a token through an unexpected field name.
_KIND_FIELDS = (
    "candidate_kind",
    "visual_kind",
    "visual_type",
    "table_signal",
    "kind",
    "type",
    "asset_type",
)

# Any of these tokens marks a record as table-like. Ordered so the most specific
# kind wins when several are present (grid > dense > generic table-like).
_TABLE_TOKENS_ORDERED = [
    "grid_table",
    "dense_table",
    "table_region",
    "table_image",
    "table_like",
    "tabular",
    "table",
]
_TABLE_KIND_MAP = {
    "grid_table": KIND_GRID_TABLE,
    "dense_table": KIND_DENSE_TABLE,
    "table_region": KIND_TABLE_LIKE,
    "table_image": KIND_TABLE_LIKE,
    "table_like": KIND_TABLE_LIKE,
    "tabular": KIND_TABLE_LIKE,
    "table": KIND_TABLE_LIKE,
}

# --- Closed preserve vocabulary (what a future reconstruction must keep) ------
PRESERVE_HEADERS = "headers"
PRESERVE_COLUMN_LABELS = "column_labels"
PRESERVE_ROW_LABELS = "row_labels"
PRESERVE_EXAM_TERMS = "exam_terms"
PRESERVE_NUMERIC_VALUES = "numeric_values"
PRESERVE_UNITS = "units"

# Deterministic emitted order for the per-item ``preserve`` list.
_PRESERVE_ORDER = [
    PRESERVE_HEADERS,
    PRESERVE_COLUMN_LABELS,
    PRESERVE_ROW_LABELS,
    PRESERVE_EXAM_TERMS,
    PRESERVE_NUMERIC_VALUES,
    PRESERVE_UNITS,
]

# Structure thresholds — conservative. A table is "structured enough" to act on if
# it has at least a small grid OR a few text cells.
_MIN_DIM = 2
_MIN_CELLS = 3

# Confidence tokens treated as "too low to commit to reconstruction".
_LOW_CONFIDENCE_TOKENS = {"low", "very_low", "none", "weak"}

_MISSING = object()


# =============================================================================
# Public API
# =============================================================================


def classify_table_candidate(candidate: Any) -> dict[str, Any]:
    """Pure, total classifier for a single table-candidate-shaped dict.

    Returns a sanitized item dict::

        {
          "source_index": int | None,
          "source_page": int | None,
          "table_kind": "grid_table | dense_table | table_like | unknown",
          "action": "reconstruct_with_original | simplify_only | defer |
                     skip_unreadable | skip_unsafe",
          "reason": <closed token>,
          "preserve": [<closed tokens>],
          "warnings": [<closed tokens>],
        }

    Only decision fields are read; no input string is ever echoed. Never raises;
    any malformed input degrades to a safe ``defer`` item with a closed warning.
    Non-table records resolve to ``defer`` / ``not_table_like`` so a table is
    never mistaken for a screenshot visual.
    """
    try:
        return _classify(candidate)
    except Exception:
        # Defensive: total even if a future field type surprises us. No raw
        # exception text is ever serialized.
        return _item(None, None, KIND_UNKNOWN, ACTION_DEFER, CANDIDATE_MALFORMED, [], [CANDIDATE_MALFORMED])


def build_table_reconstruction_policy(
    candidates: Any,
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Pure policy builder: candidate dict(s) → sanitized policy dict.

    ``candidates`` may be a list of candidate dicts, a single candidate dict, a
    light container dict (``{"candidates": [...]}`` / ``items`` / ``tables``), or
    ``None``. Each candidate is a synthetic / sanitized *table-candidate-shaped*
    dict — there is no real table manifest in this slice.

    ``max_items`` is an optional **defensive ceiling**, NOT a product cap. Default
    ``None`` evaluates every candidate. When passed as a non-negative int and more
    actionable items exist, the list is truncated in input order, ``status``
    becomes ``"partial"``, and ``max_items_applied`` is recorded.

    Returns a policy dict with ``version``, ``kind``, ``status``
    (``completed``/``partial``/``skipped``), ``summary``, ``items``, ``warnings``.
    Pure and total: never raises, never reconstructs a table, never calls a
    provider. On any unexpected input it degrades to a safe ``skipped`` policy.
    """
    try:
        return _build(candidates, max_items)
    except Exception:
        return _skipped_policy(CANDIDATE_MALFORMED)


# =============================================================================
# Builder
# =============================================================================


def _build(candidates: Any, max_items: Any) -> dict[str, Any]:
    if candidates is None:
        return _skipped_policy(CANDIDATE_MISSING)

    records = _coerce_candidate_list(candidates)
    if records is None:
        return _skipped_policy(CANDIDATE_MALFORMED)

    warnings: set[str] = set()
    items: list[dict[str, Any]] = []
    candidate_count = 0

    for candidate in records:
        if not isinstance(candidate, dict):
            warnings.add(CANDIDATE_MALFORMED)
            continue
        candidate_count += 1

        item = _classify(candidate)
        if item["reason"] == NOT_TABLE_LIKE:
            # A non-table record is never treated as a table screenshot here; it
            # is left to the (separate) non-table visual inclusion planner.
            warnings.add(NOT_TABLE_LIKE)
            continue

        items.append(item)
        warnings.update(item["warnings"])

    status = "completed"
    if isinstance(max_items, int) and not isinstance(max_items, bool) and max_items >= 0:
        if len(items) > max_items:
            items = items[:max_items]
            warnings.add(MAX_ITEMS_APPLIED)
            status = "partial"

    # Assign deterministic policy indices in input order (only after any ceiling).
    for index, item in enumerate(items, start=1):
        item["policy_index"] = index

    summary = _summarize(candidate_count, items)
    return _finalize(status, summary, items, warnings)


def _coerce_candidate_list(candidates: Any) -> list[Any] | None:
    """Normalize the flexible ``candidates`` argument to a list, or ``None``."""
    if isinstance(candidates, list):
        return candidates
    if isinstance(candidates, dict):
        # A light container dict may hold the list under a known key; otherwise the
        # dict is itself a single candidate.
        for key in ("candidates", "items", "tables"):
            value = candidates.get(key)
            if isinstance(value, list):
                return value
        return [candidates]
    return None


def _summarize(candidate_count: int, items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        ACTION_RECONSTRUCT_WITH_ORIGINAL: 0,
        ACTION_SIMPLIFY_ONLY: 0,
        ACTION_DEFER: 0,
        ACTION_SKIP_UNREADABLE: 0,
        ACTION_SKIP_UNSAFE: 0,
    }
    for item in items:
        action = item["action"]
        if action in counts:
            counts[action] += 1
    return {
        "candidate_count": candidate_count,
        "policy_item_count": len(items),
        "reconstruct_with_original_count": counts[ACTION_RECONSTRUCT_WITH_ORIGINAL],
        "simplify_only_count": counts[ACTION_SIMPLIFY_ONLY],
        "defer_count": counts[ACTION_DEFER],
        "skip_unreadable_count": counts[ACTION_SKIP_UNREADABLE],
        "skip_unsafe_count": counts[ACTION_SKIP_UNSAFE],
        # Tables are never inserted as screenshots by this policy — always 0.
        "screenshot_insert_count": 0,
    }


# =============================================================================
# Per-candidate classification
# =============================================================================


def _classify(candidate: Any) -> dict[str, Any]:
    if candidate is None:
        return _item(None, None, KIND_UNKNOWN, ACTION_DEFER, CANDIDATE_MISSING, [], [CANDIDATE_MISSING])
    if not isinstance(candidate, dict):
        return _item(None, None, KIND_UNKNOWN, ACTION_DEFER, CANDIDATE_MALFORMED, [], [CANDIDATE_MALFORMED])

    source_index = _coerce_source_index(candidate.get("source_index"))
    table_kind = _detect_table_kind(candidate)
    if table_kind is None:
        return _item(source_index, None, KIND_UNKNOWN, ACTION_DEFER, NOT_TABLE_LIKE, [], [NOT_TABLE_LIKE])

    # Unsafe wins over everything — never reconstruct a record flagged unsafe.
    if _is_unsafe(candidate):
        return _item(source_index, None, table_kind, ACTION_SKIP_UNSAFE, UNSAFE_RECORD, [], [UNSAFE_RECORD])

    page, page_warning = _resolve_source_page(candidate)
    if page is None:
        # Cannot yet anchor the table to a page → defer (recoverable later) rather
        # than guess or insert.
        return _item(source_index, None, table_kind, ACTION_DEFER, page_warning, [], [page_warning])

    if not _has_structure(candidate):
        # Not enough structure to reconstruct or even meaningfully simplify.
        return _item(source_index, page, table_kind, ACTION_SKIP_UNREADABLE, INSUFFICIENT_STRUCTURE, [], [INSUFFICIENT_STRUCTURE])

    if _is_low_confidence(candidate):
        # Structured but the signal is too weak to commit — defer the decision.
        return _item(source_index, page, table_kind, ACTION_DEFER, LOW_CONFIDENCE, [], [LOW_CONFIDENCE])

    preserve = _preserve_tokens(candidate)
    text_state = _text_layer_state(candidate)
    if text_state == TEXT_LAYER_AVAILABLE:
        # Keep the original table text AND add a simpler version.
        return _item(source_index, page, table_kind, ACTION_RECONSTRUCT_WITH_ORIGINAL, TEXT_LAYER_AVAILABLE, preserve, [])
    if text_state == TEXT_LAYER_MISSING:
        return _item(source_index, page, table_kind, ACTION_SIMPLIFY_ONLY, TEXT_LAYER_MISSING, preserve, [TEXT_LAYER_MISSING])
    # text_state == TEXT_LAYER_UNKNOWN
    return _item(source_index, page, table_kind, ACTION_SIMPLIFY_ONLY, TEXT_LAYER_UNKNOWN, preserve, [TEXT_LAYER_UNKNOWN])


# --- Detection / signal helpers (read for decisions; never echo raw input) ----


def _detect_table_kind(candidate: dict[str, Any]) -> str | None:
    """Return a closed table-kind token, or ``None`` if not table-like."""
    tokens: set[str] = set()
    for field in _KIND_FIELDS:
        value = candidate.get(field)
        if isinstance(value, str):
            token = value.strip().lower()
            if token:
                tokens.add(token)
    for token in _TABLE_TOKENS_ORDERED:
        if token in tokens:
            return _TABLE_KIND_MAP[token]
    return None


def _is_unsafe(candidate: dict[str, Any]) -> bool:
    if candidate.get("unsafe") is True:
        return True
    if candidate.get("safe") is False:
        return True
    record_warnings = candidate.get("warnings")
    if isinstance(record_warnings, (list, tuple)):
        for token in record_warnings:
            if isinstance(token, str) and "unsafe" in token.lower():
                return True
    return False


def _text_layer_state(candidate: dict[str, Any]) -> str:
    """Closed token for whether the original table text is readable."""
    flag = candidate.get("has_text_layer", _MISSING)
    if flag is True:
        return TEXT_LAYER_AVAILABLE
    if flag is False:
        return TEXT_LAYER_MISSING
    # Absent / None / non-bool ⇒ unknown (conservative).
    return TEXT_LAYER_UNKNOWN


def _has_structure(candidate: dict[str, Any]) -> bool:
    rows = _coerce_count(candidate.get("rows"))
    columns = _coerce_count(candidate.get("columns"))
    cell_text_count = _coerce_count(candidate.get("cell_text_count"))
    if rows >= _MIN_DIM and columns >= _MIN_DIM:
        return True
    if cell_text_count >= _MIN_CELLS:
        return True
    return False


def _is_low_confidence(candidate: dict[str, Any]) -> bool:
    value = candidate.get("confidence")
    if isinstance(value, str):
        return value.strip().lower() in _LOW_CONFIDENCE_TOKENS
    return False


def _preserve_tokens(candidate: dict[str, Any]) -> list[str]:
    """Deterministic closed preserve list for a future reconstruction."""
    selected: set[str] = {PRESERVE_EXAM_TERMS}  # keywords / exam terms always kept
    if _coerce_count(candidate.get("header_cell_count")) >= 1:
        selected.update({PRESERVE_HEADERS, PRESERVE_COLUMN_LABELS, PRESERVE_ROW_LABELS})
    if _coerce_count(candidate.get("numeric_cell_count")) >= 1:
        selected.update({PRESERVE_NUMERIC_VALUES, PRESERVE_UNITS})
    return [token for token in _PRESERVE_ORDER if token in selected]


# --- Field coercion ----------------------------------------------------------


def _coerce_count(value: Any) -> int:
    if value is None or isinstance(value, bool):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _coerce_source_index(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _resolve_source_page(candidate: dict[str, Any]) -> tuple[int | None, str | None]:
    raw = candidate.get("source_page", _MISSING)
    if raw is _MISSING or raw is None:
        return None, SOURCE_PAGE_MISSING
    # Strict: a verifiable 1-based page is a positive int (never a float/str/bool).
    if not isinstance(raw, int) or isinstance(raw, bool):
        return None, SOURCE_PAGE_INVALID
    if raw <= 0:
        return None, SOURCE_PAGE_INVALID
    return raw, None


# --- Assembly ----------------------------------------------------------------


def _item(
    source_index: int | None,
    source_page: int | None,
    table_kind: str,
    action: str,
    reason: str,
    preserve: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "source_index": source_index,
        "source_page": source_page,
        "table_kind": table_kind,
        "action": action,
        "reason": reason,
        "preserve": list(preserve),
        "warnings": list(warnings),
    }


def _finalize(
    status: str,
    summary: dict[str, Any],
    items: list[dict[str, Any]],
    warnings: set[str],
) -> dict[str, Any]:
    return {
        "version": POLICY_VERSION,
        "kind": POLICY_KIND,
        "status": status,
        "summary": summary,
        "items": items,
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


def _skipped_policy(warning: str) -> dict[str, Any]:
    summary = {
        "candidate_count": 0,
        "policy_item_count": 0,
        "reconstruct_with_original_count": 0,
        "simplify_only_count": 0,
        "defer_count": 0,
        "skip_unreadable_count": 0,
        "skip_unsafe_count": 0,
        "screenshot_insert_count": 0,
    }
    return _finalize("skipped", summary, [], {warning})
