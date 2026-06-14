"""Table **reconstruction prompt-context** builder (Slice 93).

Full Material Coverage foundation. Slice 92 landed the safe table bridge::

    visual_assets_manifest.json
    -> table_candidates_manifest.json   (sanitized candidates)
    -> table_reconstruction_policy.json  (Slice 85 policy decisions)

This module is the next, still-safe step: turn those two **already-sanitized**
artifacts into a short, deterministic, leak-free *prompt context* the normal guide
generator can be told, so a table-like region is handled honestly instead of being
hallucinated or treated as a screenshot.

Product goal (honest, no-hallucination table handling)
------------------------------------------------------
When the source material has table-like candidates, tell the generator how to
handle them safely:

* reconstruct / simplify a table **only** when its contents are present in the
  normal source text already in the prompt;
* preserve headers, units, exam terms, row/column labels, and numeric values when
  available;
* never invent rows / columns / labels / values for image-only or unreadable
  tables;
* emit an honest "table-like material was detected on page N but its contents were
  not readable" note when content is unavailable.

Scope (Slice 93 = prompt-context only)
--------------------------------------
Pure derivation only. It does NOT reconstruct a table, read PDFs, inspect images,
OCR, read image bytes, extract table text, render, export, call a provider / model
/ VLM / Chandra / Mistral / Gemini, change material page selection, change visual
insertion / filtering, or treat a table as a screenshot. It reads ONLY the two
sanitized artifact dicts and returns a sanitized context dict whose ``prompt_block``
is safe to append to the existing generation prompt.

Purity & safety
---------------
stdlib-only (imports nothing from ``pipeline`` and no provider/model/OCR/renderer/
FastAPI/frontend module). The context emits **only** closed tokens, ints, ``None``,
bools, fixed instruction strings built from those, and a safe generated
``candidate_id`` of the fixed shape ``table_candidate_NNNN``. No filename, path,
source title, caption, document / OCR / table text, image ref, asset ref / asset
id, image byte, base64 / data URI, provider payload, token, URL, argv, socket path,
model path, or raw exception string can survive into it: input fields are read for
*decisions only* and never echoed. Never raises; any malformed input degrades to a
safe ``skipped`` / empty context.
"""
from __future__ import annotations

import re
from typing import Any

CONTEXT_VERSION = 1
CONTEXT_KIND = "table_reconstruction_prompt_context"

# --- Closed action vocabulary (mirrors the Slice 85 policy actions) -----------
ACTION_RECONSTRUCT_WITH_ORIGINAL = "reconstruct_with_original"
ACTION_SIMPLIFY_ONLY = "simplify_only"
ACTION_DEFER = "defer"
ACTION_SKIP_UNREADABLE = "skip_unreadable"
ACTION_SKIP_UNSAFE = "skip_unsafe"

# Actions that produce a prompt item. ``skip_unsafe`` is deliberately absent — an
# unsafe record is never surfaced as a reconstruction instruction or note.
_RECONSTRUCT_ACTIONS = {ACTION_RECONSTRUCT_WITH_ORIGINAL, ACTION_SIMPLIFY_ONLY}
_NOTE_ACTIONS = {ACTION_DEFER, ACTION_SKIP_UNREADABLE}
_EMITTED_ACTIONS = _RECONSTRUCT_ACTIONS | _NOTE_ACTIONS

# --- Closed preserve vocabulary (what a future reconstruction must keep) ------
# Maps the policy's closed preserve token to a safe human phrase. Only tokens in
# this map survive; anything else (incl. a hostile canary) is dropped.
_PRESERVE_PHRASES = {
    "headers": "headers",
    "column_labels": "column labels",
    "row_labels": "row labels",
    "exam_terms": "exam terms",
    "numeric_values": "numeric values",
    "units": "units",
}
# Deterministic emitted order for the per-item ``preserve`` list / phrases.
_PRESERVE_ORDER = [
    "headers",
    "column_labels",
    "row_labels",
    "exam_terms",
    "numeric_values",
    "units",
]

# --- Closed warning vocabulary (this module owns what it emits) ---------------
ARTIFACTS_MISSING = "artifacts_missing"
POLICY_MISSING = "policy_missing"
POLICY_MALFORMED = "policy_malformed"
POLICY_SKIPPED = "policy_skipped"
CANDIDATES_MISSING = "candidates_missing"
CANDIDATES_MALFORMED = "candidates_malformed"
ITEM_MALFORMED = "item_malformed"
CANDIDATE_ID_SYNTHESIZED = "candidate_id_synthesized"
SKIP_UNSAFE_EXCLUDED = "skip_unsafe_excluded"
MAX_ITEMS_APPLIED = "max_items_applied"

# Deterministic emitted warning ordering (closed tokens only, never raw text).
WARNING_ORDER = [
    ARTIFACTS_MISSING,
    POLICY_MISSING,
    POLICY_MALFORMED,
    POLICY_SKIPPED,
    CANDIDATES_MISSING,
    CANDIDATES_MALFORMED,
    ITEM_MALFORMED,
    CANDIDATE_ID_SYNTHESIZED,
    SKIP_UNSAFE_EXCLUDED,
    MAX_ITEMS_APPLIED,
]

# Safe generated candidate-id shape. The manifest emits ``table_candidate_0001``…;
# a malformed/absent id is replaced by a synthesized id of this exact shape.
CANDIDATE_ID_PREFIX = "table_candidate_"
_CANDIDATE_ID_RE = re.compile(r"^table_candidate_\d{4,}$")

# Defensive full ceiling — guards a pathological policy, NOT a product cap.
_PROMPT_ITEM_HARD_CEILING = 500

# Static, leak-free guidance lines prepended to every non-empty prompt block.
_GUIDANCE_LINES = (
    "Table reconstruction guidance:",
    "- Some included pages have table-like material.",
    "- Reconstruct or simplify a table only when its contents are present in the "
    "provided source text.",
    "- Preserve headers, units, exam terms, row and column labels, and numeric "
    "values when available.",
    "- Do not invent rows, columns, labels, or values for image-only or unreadable "
    "tables.",
    "- If a detected table is not readable from the source text, add a short note "
    "that table-like material was detected on that page but its contents were not "
    "readable.",
)


# =============================================================================
# Public API
# =============================================================================


def build_table_reconstruction_prompt_context(
    table_candidates_manifest: dict | None,
    table_reconstruction_policy: dict | None,
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Pure builder: sanitized candidate manifest + policy -> prompt context dict.

    ``table_candidates_manifest`` is a ``table_candidates_manifest.json``-shaped
    dict (Slice 92) used only to recover each item's safe ``candidate_id``;
    ``table_reconstruction_policy`` is a ``table_reconstruction_policy.json``-shaped
    dict (Slice 85 policy) whose ``items`` carry the per-table action decisions.

    Each actionable policy item becomes a sanitized prompt item with a closed
    ``action``, a positive-int ``source_page`` (or ``None``), closed ``preserve``
    tokens, and a fixed-shape ``instruction`` string. ``reconstruct_with_original``
    / ``simplify_only`` yield reconstruction instructions; ``defer`` /
    ``skip_unreadable`` yield honest no-hallucination notes; ``skip_unsafe`` is
    excluded entirely (never surfaced as an instruction or note).

    ``max_items`` is an optional **defensive ceiling**, NOT a product cap. Default
    ``None`` keeps every eligible item (still bounded by an internal hard ceiling).
    When passed as a non-negative int and more items exist, the list is truncated in
    input order, ``status`` becomes ``"partial"``, and ``max_items_applied`` is
    recorded.

    Returns a context dict with ``version``, ``kind``, ``status``
    (``completed``/``partial``/``skipped``), ``summary``, ``prompt_block``,
    ``items``, ``warnings``. Pure and total: never raises, reconstructs no table,
    inspects no PDF/image, calls no provider. On any unexpected input it degrades to
    a safe ``skipped`` context with an empty ``prompt_block``.
    """
    try:
        return _build(table_candidates_manifest, table_reconstruction_policy, max_items)
    except Exception:
        return _skipped_context(POLICY_MALFORMED)


# =============================================================================
# Builder
# =============================================================================


def _build(
    manifest: Any,
    policy: Any,
    max_items: Any,
) -> dict[str, Any]:
    warnings: set[str] = set()

    if policy is None and manifest is None:
        return _skipped_context(ARTIFACTS_MISSING)
    if policy is None:
        return _skipped_context(POLICY_MISSING)
    if not isinstance(policy, dict):
        return _skipped_context(POLICY_MALFORMED)

    status = policy.get("status")
    if isinstance(status, str) and status.strip().lower() == "skipped":
        return _skipped_context(POLICY_SKIPPED)

    policy_items = policy.get("items")
    if policy_items is None:
        policy_items = []
    if not isinstance(policy_items, list):
        return _skipped_context(POLICY_MALFORMED)

    candidate_ids = _candidate_ids(manifest, warnings)

    items: list[dict[str, Any]] = []
    policy_item_count = 0
    for index, raw in enumerate(policy_items):
        if not isinstance(raw, dict):
            warnings.add(ITEM_MALFORMED)
            continue
        policy_item_count += 1

        action = raw.get("action")
        if not isinstance(action, str):
            warnings.add(ITEM_MALFORMED)
            continue
        action = action.strip().lower()

        if action == ACTION_SKIP_UNSAFE:
            # An unsafe record is never surfaced as an instruction or a note.
            warnings.add(SKIP_UNSAFE_EXCLUDED)
            continue
        if action not in _EMITTED_ACTIONS:
            # Unknown / non-actionable token (e.g. a hostile value) is dropped.
            warnings.add(ITEM_MALFORMED)
            continue

        page = _coerce_page(raw.get("source_page"))
        preserve = _preserve_tokens(raw.get("preserve"))
        candidate_id = _candidate_id_for(index, candidate_ids, warnings)

        items.append(
            {
                "candidate_id": candidate_id,
                "source_page": page,
                "action": action,
                "preserve": preserve,
                "instruction": _instruction(action, page, preserve),
                "warnings": [],
            }
        )

    # Defensive ceiling: the smaller of the caller cap (if any) and the internal
    # hard ceiling. Truncation is in input order and marks the context partial.
    status_token = "completed"
    if isinstance(status, str) and status.strip().lower() == "partial":
        status_token = "partial"
    ceiling = _PROMPT_ITEM_HARD_CEILING
    if isinstance(max_items, int) and not isinstance(max_items, bool) and max_items >= 0:
        ceiling = min(ceiling, max_items)
    if len(items) > ceiling:
        items = items[:ceiling]
        warnings.add(MAX_ITEMS_APPLIED)
        status_token = "partial"

    summary = _summarize(len(candidate_ids), policy_item_count, items)
    prompt_block = _prompt_block(items)
    return _finalize(status_token, summary, prompt_block, items, warnings)


def _candidate_ids(manifest: Any, warnings: set[str]) -> list[str | None]:
    """Recover per-candidate safe ids from the candidate manifest, in order.

    Returns a list aligned to manifest emission order; each entry is a validated
    ``table_candidate_NNNN`` id or ``None`` (caller synthesizes one). A missing /
    malformed manifest records a closed warning and yields an empty list (all ids
    are then synthesized from position).
    """
    if manifest is None:
        warnings.add(CANDIDATES_MISSING)
        return []
    if not isinstance(manifest, dict):
        warnings.add(CANDIDATES_MALFORMED)
        return []
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list):
        warnings.add(CANDIDATES_MALFORMED)
        return []
    ids: list[str | None] = []
    for candidate in candidates:
        cid = candidate.get("candidate_id") if isinstance(candidate, dict) else None
        ids.append(cid if isinstance(cid, str) and _CANDIDATE_ID_RE.match(cid) else None)
    return ids


def _candidate_id_for(
    index: int,
    candidate_ids: list[str | None],
    warnings: set[str],
) -> str:
    """Return the aligned safe candidate id, or a synthesized fixed-shape id."""
    if 0 <= index < len(candidate_ids):
        cid = candidate_ids[index]
        if isinstance(cid, str) and _CANDIDATE_ID_RE.match(cid):
            return cid
    warnings.add(CANDIDATE_ID_SYNTHESIZED)
    return f"{CANDIDATE_ID_PREFIX}{index + 1:04d}"


# =============================================================================
# Instruction / prompt-block text (closed; never echoes raw input)
# =============================================================================


def _page_phrase(page: int | None) -> str:
    return f"page {page}" if isinstance(page, int) else "the detected page"


def _preserve_clause(preserve: list[str]) -> str:
    phrases = [_PRESERVE_PHRASES[token] for token in preserve if token in _PRESERVE_PHRASES]
    if not phrases:
        return ""
    return f" Preserve {_join(phrases)} when present in the source text."


def _instruction(action: str, page: int | None, preserve: list[str]) -> str:
    where = _page_phrase(page)
    preserve_clause = _preserve_clause(preserve)
    no_invent = (
        " Do not invent rows, columns, labels, or values that are not present in "
        "the source text."
    )
    if action == ACTION_RECONSTRUCT_WITH_ORIGINAL:
        return (
            f"Reconstruct the table on {where} only from content present in the "
            f"provided source text, keeping original values where available."
            f"{preserve_clause}{no_invent}"
        )
    if action == ACTION_SIMPLIFY_ONLY:
        return (
            f"Produce a simplified version of the table on {where} only from content "
            f"present in the provided source text.{preserve_clause}{no_invent}"
        )
    # defer / skip_unreadable: honest no-hallucination note.
    return (
        f"Table-like material was detected on {where}, but its contents may not be "
        f"readable from the provided source text. If they are not present, add a "
        f"short note that table-like material was detected on {where} but its "
        f"contents were not readable.{no_invent}"
    )


def _prompt_block(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    lines = list(_GUIDANCE_LINES)
    lines.append("Detected table actions:")
    for item in items:
        lines.append(f"- {_action_summary(item)}")
    return "\n".join(lines)


def _action_summary(item: dict[str, Any]) -> str:
    where = _page_phrase(item.get("source_page"))
    action = item.get("action")
    # Capitalize only the leading "page"/"the" word safely (closed strings).
    head = where[0].upper() + where[1:]
    if action == ACTION_RECONSTRUCT_WITH_ORIGINAL:
        body = "reconstruct with original when supported by source text"
    elif action == ACTION_SIMPLIFY_ONLY:
        body = "simplify only when supported by source text"
    else:
        return (
            f"{head}: table-like material detected but contents may not be readable; "
            "do not invent rows or values"
        )
    preserve = item.get("preserve") or []
    phrases = [_PRESERVE_PHRASES[t] for t in preserve if t in _PRESERVE_PHRASES]
    if phrases:
        return f"{head}: {body}; preserve {_join(phrases)}"
    return f"{head}: {body}"


def _join(phrases: list[str]) -> str:
    if len(phrases) == 1:
        return phrases[0]
    if len(phrases) == 2:
        return f"{phrases[0]} and {phrases[1]}"
    return ", ".join(phrases[:-1]) + f", and {phrases[-1]}"


# =============================================================================
# Field coercion
# =============================================================================


def _coerce_page(value: Any) -> int | None:
    # Strict: a verifiable 1-based page is a positive int (never a float/str/bool).
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return value if value > 0 else None


def _preserve_tokens(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    present: set[str] = set()
    for token in value:
        if isinstance(token, str) and token in _PRESERVE_PHRASES:
            present.add(token)
    return [token for token in _PRESERVE_ORDER if token in present]


# =============================================================================
# Assembly
# =============================================================================


def _summarize(
    candidate_count: int,
    policy_item_count: int,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = {
        ACTION_RECONSTRUCT_WITH_ORIGINAL: 0,
        ACTION_SIMPLIFY_ONLY: 0,
        ACTION_DEFER: 0,
        ACTION_SKIP_UNREADABLE: 0,
    }
    for item in items:
        action = item["action"]
        if action in counts:
            counts[action] += 1
    return {
        "candidate_count": candidate_count,
        "policy_item_count": policy_item_count,
        "prompt_item_count": len(items),
        "reconstruct_with_original_count": counts[ACTION_RECONSTRUCT_WITH_ORIGINAL],
        "simplify_only_count": counts[ACTION_SIMPLIFY_ONLY],
        "defer_count": counts[ACTION_DEFER],
        "skip_count": counts[ACTION_SKIP_UNREADABLE],
    }


def _finalize(
    status: str,
    summary: dict[str, Any],
    prompt_block: str,
    items: list[dict[str, Any]],
    warnings: set[str],
) -> dict[str, Any]:
    return {
        "version": CONTEXT_VERSION,
        "kind": CONTEXT_KIND,
        "status": status,
        "summary": summary,
        "prompt_block": prompt_block,
        "items": items,
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


def _skipped_context(warning: str) -> dict[str, Any]:
    summary = {
        "candidate_count": 0,
        "policy_item_count": 0,
        "prompt_item_count": 0,
        "reconstruct_with_original_count": 0,
        "simplify_only_count": 0,
        "defer_count": 0,
        "skip_count": 0,
    }
    return _finalize("skipped", summary, "", [], {warning})
