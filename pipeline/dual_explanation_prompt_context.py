"""Dual-explanation **generation prompt-context** builder (Slice 99).

Explain like I'm 10 / Exam answer mode v1. Slices 82–98 taught generation and
Ask Guide about *material coverage*; Slice 99 adds an optional **study-quality**
layer on top: when the operator turns it on, the guide generator is asked to give,
for difficult or exam-important concepts, two short companion explanations — a
beginner-friendly "Explain it simply" version and a formal "Exam answer" version.

Product goal (understand it, then learn what to write in the exam)
----------------------------------------------------------------
``For difficult concepts, generated guides should provide both a simple
beginner-friendly explanation and a formal exam-ready answer version.``

This builder turns a single safe boolean (``enabled``) into a short, deterministic,
leak-free ``prompt_block`` that is appended to the existing generation prompt only
when the mode is on. Default off ⇒ the prompt stays byte-identical to prior
behaviour.

Scope (Slice 99 = prompt-context only)
--------------------------------------
Pure derivation only. It does NOT call an LLM / provider / model / VLM / Chandra /
Mistral / Gemini / cloud, change provider or model selection, inspect PDFs/images,
read image bytes, reconstruct a table, extract table text, render, export, change
figure insertion semantics, change material page selection, change visual-manifest
filtering, change Ask Guide behaviour, or add UI. It reads ONLY the safe ``enabled``
flag and returns a sanitized context dict whose ``prompt_block`` is safe to append.

Purity & safety
---------------
stdlib-only (imports nothing from ``pipeline`` and no provider/model/OCR/renderer/
FastAPI/frontend module). The context emits **only** a closed status token, ints,
bools, and fixed instruction strings. It never reads or echoes user source text, a
filename, path, source title, caption, document / OCR / table text, image ref,
asset ref, image byte, base64 / data URI, provider payload, token, URL, argv,
socket path, model path, or raw exception string. Never raises; any malformed input
degrades to a safe ``skipped`` / empty context.
"""
from __future__ import annotations

from typing import Any

CONTEXT_VERSION = 1
CONTEXT_KIND = "dual_explanation_prompt_context"

# --- Closed warning vocabulary (this module owns what it emits) --------------
ENABLED_NOT_BOOL = "enabled_not_bool"
MAX_ITEMS_APPLIED = "max_items_applied"

# Deterministic emitted warning ordering (closed tokens only, never raw text).
WARNING_ORDER = [
    ENABLED_NOT_BOOL,
    MAX_ITEMS_APPLIED,
]

# This feature contributes exactly one conceptual guidance item (the dual-mode
# instruction). ``max_items`` is a defensive ceiling, not a product cap.
_PROMPT_ITEM_COUNT = 1

# Static, deterministic, leak-free instruction block. Contains no source content.
_PROMPT_BLOCK = "\n".join(
    (
        "Dual explanation mode:",
        "- For difficult, abstract, or exam-important concepts, include two short "
        "companion blocks.",
        "- Explain it simply: use beginner-friendly language and a concrete analogy "
        "when helpful.",
        "- Exam answer: give a formal, accurate version suitable for memorization or "
        "exam writing.",
        "- Keep both blocks concise and source-grounded.",
        "- Do not invent facts, examples, labels, table values, diagram details, or "
        "citations.",
        "- If the source does not support a formal answer, say what is missing "
        "instead of guessing.",
    )
)


# =============================================================================
# Public API
# =============================================================================


def build_dual_explanation_prompt_context(
    enabled: bool | None,
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Pure builder: a safe ``enabled`` flag -> dual-explanation prompt context.

    Returns a context dict with ``version``, ``kind``, ``status``
    (``completed``/``skipped``), ``summary`` (``enabled`` + ``prompt_item_count``),
    ``prompt_block`` (the deterministic instruction text when enabled, else ``""``),
    and ``warnings`` (closed tokens only). ``max_items`` is an optional defensive
    ceiling, NOT a product cap. Pure and total: never raises, calls no provider,
    inspects no PDF/image, OCRs nothing, reconstructs no table. On any unexpected
    input it degrades to a safe ``skipped`` context with an empty ``prompt_block``.
    """
    try:
        return _build(enabled, max_items)
    except Exception:
        return _skipped(set(), enabled_flag=False)


# =============================================================================
# Builder
# =============================================================================


def _build(enabled: Any, max_items: Any) -> dict[str, Any]:
    warnings: set[str] = set()

    # Only a real ``True`` enables. ``None``/``False`` are the normal off cases;
    # any other type is malformed input that degrades to off with a closed warning.
    if enabled is None or enabled is False:
        return _skipped(warnings, enabled_flag=False)
    if enabled is not True:
        warnings.add(ENABLED_NOT_BOOL)
        return _skipped(warnings, enabled_flag=False)

    # Defensive ceiling: a non-negative int below the (single) item count zeroes the
    # block out. A bool is never a valid count here.
    if (
        isinstance(max_items, int)
        and not isinstance(max_items, bool)
        and max_items >= 0
        and max_items < _PROMPT_ITEM_COUNT
    ):
        warnings.add(MAX_ITEMS_APPLIED)
        return _skipped(warnings, enabled_flag=True)

    return {
        "version": CONTEXT_VERSION,
        "kind": CONTEXT_KIND,
        "status": "completed",
        "summary": {"enabled": True, "prompt_item_count": _PROMPT_ITEM_COUNT},
        "prompt_block": _PROMPT_BLOCK,
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


# =============================================================================
# Assembly
# =============================================================================


def _skipped(warnings: set[str], *, enabled_flag: bool) -> dict[str, Any]:
    return {
        "version": CONTEXT_VERSION,
        "kind": CONTEXT_KIND,
        "status": "skipped",
        "summary": {"enabled": bool(enabled_flag), "prompt_item_count": 0},
        "prompt_block": "",
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }
