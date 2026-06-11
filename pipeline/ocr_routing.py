"""Pure, deterministic OCR routing-policy core (Slice 33).

Given the **advisory page classification** already produced by
:mod:`pipeline.extraction_metadata` (Slice 31) plus a small, optional policy
``config``, this module decides what *should* happen for a page's OCR — without
touching extraction, calling OCR, or naming a key/URL. It is the "pure core,
then integrate" step in ``docs/HYBRID_OCR_DESIGN.md`` §9 (Slice 33): the policy
is implemented and tested in isolation here and is **deliberately NOT wired into
``pipeline/extract.py``** in this slice. Extraction behaviour, OCR calls,
prompts, metadata artifacts, and generation are all unchanged.

Design guarantees (see ``HYBRID_OCR_DESIGN.md`` §5):

- **Pure & deterministic.** No I/O, no clock, no randomness, no global state.
  The same inputs always yield the same JSON-safe decision. Multi-page budget
  decisions depend only on input order.
- **Dependency-free.** Imports nothing from PyMuPDF (``fitz``), Tesseract,
  ``pipeline.ocr_provider``, cloud providers, or provider settings. The closed
  classification vocabulary is mirrored locally so the core has zero coupling.
- **Local-first, cloud-off by default.** With default config (no cloud, local
  OCR available) the policy only ever recommends embedded text or local OCR;
  ``cloud_ocr_candidate`` is an *advisory* future option returned **only** when
  cloud OCR is explicitly allowed AND local OCR cannot serve the page.
- **Failure is impossible.** Any malformed / hostile / smuggled input degrades
  to a fixed safe decision (``action: "unknown"``) — it never raises and never
  echoes an input value, so no path, secret, image blob, or free text from the
  input can ever appear in the output. Every output field is a fixed token from a
  closed vocabulary (action / reason / confidence / warning), an integer, ``None``,
  or the literal local provider id.

This module decides *intent* only. It does not run OCR, choose a cloud endpoint,
read keys, or estimate cost — those belong to later, gated slices.
"""

from __future__ import annotations

from typing import Any

# Local provider id — mirrors ``pipeline.ocr_provider.TESSERACT_PROVIDER_ID`` but
# defined here so the routing core stays import-free of the OCR engine. It is a
# non-secret id (never a key/URL/path), safe to surface in a decision.
LOCAL_OCR_PROVIDER_ID = "tesseract_local"

# --- Closed output vocabularies --------------------------------------------
#
# Consumers must treat any value outside these sets as unknown-safe, never as an
# error (mirrors `_safe_method` / `_safe_classification` in extraction_metadata).

# What the policy recommends for a page.
ACTIONS = {
    "use_embedded_text",   # a good text layer exists; never OCR it
    "use_local_ocr",       # weak/scanned page → run local (Tesseract) OCR
    "skip_ocr",            # do not OCR (blank, errored, unavailable, or over budget)
    "cloud_ocr_candidate", # advisory: cloud OCR *could* help (explicitly allowed only)
    "unknown",             # not enough signal to route; caller decides conservatively
}

# Stable reason tokens — fixed strings only, never free text/paths/values.
REASONS = {
    "embedded_text_sufficient",
    "mixed_has_meaningful_text",
    "ocr_already_applied",
    "scanned_needs_ocr",
    "blank_low_text_no_visual",
    "unknown_classification",
    "classification_error",
    "local_ocr_unavailable",
    "cloud_candidate_local_unavailable",
    "ocr_budget_exhausted",
    "routing_unavailable",
}

# Coarse, non-numeric confidence — avoids implying a calibrated probability.
CONFIDENCES = {"high", "medium", "low"}

# Stable warning tokens — fixed strings only.
WARNINGS = {
    "local_ocr_unavailable",
    "cloud_ocr_disabled",
    "ocr_budget_exhausted",
    "routing_input_unrecognized",
}

# Classification vocabulary the policy understands. Mirrors
# `extraction_metadata._CLASSIFICATIONS`; anything else coerces to "unknown".
_CLASSIFICATIONS = {
    "embedded_text",
    "ocr_fallback",
    "likely_scanned",
    "blank_or_low_text",
    "mixed",
    "unknown",
    "error",
}

# The fixed, safe decision returned on any unexpected input. A module-level
# template that is copied (never shared/mutated) per call.
_SAFE_UNKNOWN_REASON = "routing_unavailable"


def default_config() -> dict[str, Any]:
    """Return the local-first, cloud-off default policy config.

    - ``allow_cloud_ocr``: cloud OCR is **off** by default (privacy-first).
    - ``local_ocr_available``: assume local Tesseract is present unless told otherwise.
    - ``max_ocr_pages``: optional hard cap on OCR'd pages for a document (None = uncapped).
    - ``page_budget_remaining``: optional remaining OCR-page allowance (None = uncapped).
    """
    return {
        "allow_cloud_ocr": False,
        "local_ocr_available": True,
        "max_ocr_pages": None,
        "page_budget_remaining": None,
    }


def decide_ocr_route(
    page_metadata: Any,
    config: Any = None,
) -> dict[str, Any]:
    """Decide the OCR route for a single page. Pure, total, never raises.

    ``page_metadata`` is a sanitized page record (as produced by
    ``extraction_metadata._safe_page``) — only its ``classification`` is read;
    no other field is trusted or echoed. ``config`` is an optional policy dict
    (see :func:`default_config`); unknown/malformed keys fall back to defaults.

    Returns a JSON-safe decision::

        {"action": ..., "provider": ... | None, "reason": ...,
         "confidence": ..., "warnings": [...]}

    On any unexpected input the result is the fixed safe decision
    (``action: "unknown"``, ``reason: "routing_unavailable"``).
    """
    try:
        cfg = _normalize_config(config)
        # Budget for a single decision: prefer an explicit remaining count, else
        # the cap. None means uncapped.
        remaining = cfg["page_budget_remaining"]
        if remaining is None:
            remaining = cfg["max_ocr_pages"]
        decision, _consumed = _decide_one(page_metadata, cfg, remaining)
        return decision
    except Exception:
        return _safe_unknown_decision()


def decide_ocr_routes(
    pages: Any,
    config: Any = None,
) -> list[dict[str, Any]]:
    """Decide OCR routes for a list of pages, applying a shared OCR-page budget.

    Pages are processed **in input order**; each page that the policy routes to
    OCR work (local OCR or a cloud candidate) consumes one unit from the shared
    budget. Once the budget is exhausted, later OCR-bound pages downgrade to
    ``skip_ocr`` with ``reason: "ocr_budget_exhausted"``. Pages that do not OCR
    (embedded text / blank / unknown / error) never consume budget.

    Deterministic: the result depends only on the page list, its order, and the
    config — never on wall-clock, randomness, or external state. Non-list input
    degrades to an empty list; a malformed individual page degrades to the fixed
    safe decision without aborting the batch.
    """
    try:
        cfg = _normalize_config(config)
    except Exception:
        cfg = default_config()

    if not isinstance(pages, list):
        return []

    remaining = cfg["page_budget_remaining"]
    if remaining is None:
        remaining = cfg["max_ocr_pages"]

    out: list[dict[str, Any]] = []
    for page in pages:
        try:
            decision, consumed = _decide_one(page, cfg, remaining)
        except Exception:
            decision, consumed = _safe_unknown_decision(), 0
        if consumed and remaining is not None:
            remaining = max(0, remaining - consumed)
        out.append(decision)
    return out


# --- internal core ----------------------------------------------------------


def _decide_one(
    page_metadata: Any,
    cfg: dict[str, Any],
    remaining: int | None,
) -> tuple[dict[str, Any], int]:
    """Core single-page decision. Returns (decision, budget_units_consumed).

    ``remaining`` is the OCR-page budget still available for this decision
    (``None`` = uncapped). ``budget_units_consumed`` is 1 only when the chosen
    action actually performs OCR work (local OCR or a cloud candidate), else 0.
    """
    classification = _safe_classification(_get_classification(page_metadata))

    # Non-OCR routes — never consume budget, never depend on availability.
    if classification == "embedded_text":
        return _decision("use_embedded_text", None, "embedded_text_sufficient", "high"), 0
    if classification == "mixed":
        # Meaningful text layer alongside images: trust the text, don't OCR.
        return _decision("use_embedded_text", None, "mixed_has_meaningful_text", "medium"), 0
    if classification == "ocr_fallback":
        # OCR already ran for this page and its text is what extraction captured;
        # re-OCRing would duplicate work and change nothing. Use the text as-is.
        return _decision("use_embedded_text", None, "ocr_already_applied", "high"), 0
    if classification == "blank_or_low_text":
        # Positively measured: no text and no visual objects → nothing to OCR.
        return _decision("skip_ocr", None, "blank_low_text_no_visual", "high"), 0
    if classification == "error":
        # A per-page extraction/OCR error makes the page unsafe to route to OCR.
        return _decision("skip_ocr", None, "classification_error", "low"), 0
    if classification == "likely_scanned":
        return _decide_scanned(cfg, remaining)

    # classification == "unknown" (or anything coerced to it): conservative —
    # never cloud, never spend budget; let the caller decide.
    return _decision("unknown", None, "unknown_classification", "low"), 0


def _decide_scanned(
    cfg: dict[str, Any],
    remaining: int | None,
) -> tuple[dict[str, Any], int]:
    """Route a `likely_scanned` page: local-first, cloud only if explicitly allowed."""
    budget_exhausted = remaining is not None and remaining <= 0

    if cfg["local_ocr_available"]:
        if budget_exhausted:
            return _decision(
                "skip_ocr", None, "ocr_budget_exhausted", "low",
                warnings=["ocr_budget_exhausted"],
            ), 0
        return _decision("use_local_ocr", LOCAL_OCR_PROVIDER_ID, "scanned_needs_ocr", "high"), 1

    # Local OCR unavailable. Cloud is an advisory candidate *only* when allowed.
    if cfg["allow_cloud_ocr"]:
        if budget_exhausted:
            return _decision(
                "skip_ocr", None, "ocr_budget_exhausted", "low",
                warnings=["ocr_budget_exhausted"],
            ), 0
        # Provider stays None: no cloud provider is implemented or configured here;
        # this only flags that a future cloud provider could serve the page.
        return _decision(
            "cloud_ocr_candidate", None, "cloud_candidate_local_unavailable", "low",
            warnings=["local_ocr_unavailable"],
        ), 1

    # Neither local nor cloud available → skip and warn (job still runs on text).
    return _decision(
        "skip_ocr", None, "local_ocr_unavailable", "low",
        warnings=["local_ocr_unavailable", "cloud_ocr_disabled"],
    ), 0


def _decision(
    action: str,
    provider: str | None,
    reason: str,
    confidence: str,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a validated, JSON-safe decision dict from closed-vocab tokens.

    Defensive: any token not in its vocabulary coerces to a safe default rather
    than passing through, so a decision can never carry an out-of-vocab string.
    """
    safe_warnings = [w for w in (warnings or []) if w in WARNINGS]
    return {
        "action": action if action in ACTIONS else "unknown",
        "provider": provider if provider == LOCAL_OCR_PROVIDER_ID else None,
        "reason": reason if reason in REASONS else _SAFE_UNKNOWN_REASON,
        "confidence": confidence if confidence in CONFIDENCES else "low",
        "warnings": safe_warnings,
    }


def _safe_unknown_decision() -> dict[str, Any]:
    """The fixed, leak-free decision used whenever input cannot be trusted."""
    return {
        "action": "unknown",
        "provider": None,
        "reason": _SAFE_UNKNOWN_REASON,
        "confidence": "low",
        "warnings": ["routing_input_unrecognized"],
    }


def _get_classification(page_metadata: Any) -> Any:
    """Read only the ``classification`` field; never trust or echo anything else."""
    if isinstance(page_metadata, dict):
        return page_metadata.get("classification")
    return None


def _safe_classification(value: Any) -> str:
    """Coerce a classification to the closed vocabulary; ``unknown`` otherwise."""
    if value in _CLASSIFICATIONS:
        return value  # type: ignore[return-value]
    return "unknown"


def _normalize_config(config: Any) -> dict[str, Any]:
    """Sanitize an optional policy config into a complete, safe dict.

    Never raises. Unknown keys are ignored; missing/malformed values fall back to
    the local-first, cloud-off defaults. Counts are coerced to non-negative ints
    or ``None``.
    """
    cfg = default_config()
    if not isinstance(config, dict):
        return cfg
    cfg["allow_cloud_ocr"] = _safe_bool(config.get("allow_cloud_ocr"), default=False)
    cfg["local_ocr_available"] = _safe_bool(config.get("local_ocr_available"), default=True)
    cfg["max_ocr_pages"] = _safe_count_or_none(config.get("max_ocr_pages"))
    cfg["page_budget_remaining"] = _safe_count_or_none(config.get("page_budget_remaining"))
    return cfg


def _safe_bool(value: Any, *, default: bool) -> bool:
    """Strict-ish bool: only real booleans count; anything else uses ``default``.

    Avoids surprising truthiness (e.g. a smuggled non-empty string flipping cloud
    OCR on) — a config flag must be an explicit ``True``/``False`` to take effect.
    """
    if isinstance(value, bool):
        return value
    return default


def _safe_count_or_none(value: Any) -> int | None:
    """Non-negative integer, or ``None`` when unset/unparseable. Booleans rejected."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None
