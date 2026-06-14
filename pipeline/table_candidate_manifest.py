"""Table **candidate manifest** core + artifact writer (Slice 92).

Full Material Coverage foundation. Slice 83/84 added the pure non-table *visual
inclusion planner* and persisted its plan; Slice 85 added the pure *table
reconstruction policy* decision core — but that policy has, until now, only ever
consumed **synthetic** table-candidate-shaped dicts, because there is still no real
table manifest. This module builds the missing bridge: a deterministic,
**sanitized** table-candidate manifest derived purely from the already-safe
``visual_assets_manifest.json`` (Slice 82-filtered) so the policy can later run on
real signals.

Product goal (tables are not screenshots)
-----------------------------------------
A table is **not** an ordinary screenshot visual. The non-table visual inclusion
planner deliberately *skips* table-like manifest records (they belong to the table
reconstruction/simplification policy, never screenshot insertion). This module
picks up exactly those skipped table-like records and turns them into sanitized
candidates that the Slice 85 policy can evaluate — **without** reconstructing any
table, inspecting a PDF/image, OCRing, calling a provider/model, or treating the
table as an image to insert.

Scope (Slice 92 = candidate manifest + policy-input bridge)
-----------------------------------------------------------
Pure derivation + degrade-never-fail persistence only. It does NOT: reconstruct a
table, read PDFs, inspect images, OCR, crop, render, export, change a prompt, call
a provider / model / VLM / Chandra / Mistral / Gemini, or change Markdown
insertion, the visual-inclusion planner, the visual-pilot ranking/classification/
cap, material page selection, or visual-manifest filtering. It only reads the
sanitized visual manifest dict and writes ``table_candidates_manifest.json``.

Purity & safety
---------------
stdlib-only. The manifest emits **only** closed tokens, ints, ``None``, fixed
strings, bools, and a **safe generated** ``candidate_id`` (a fixed-shape sequential
id such as ``"table_candidate_0001"`` derived purely from emission order — it
carries no filename, path, slug, or other source detail). No filename, path, source
title, caption, document / OCR / table text, image ref, asset ref / asset id, image
byte, base64 / data URI, provider payload, token, URL, argv, socket path, model
path, or raw exception string can survive into it: input fields are read for
*decisions / sanitized counts only* and never echoed. Never raises; any malformed
input degrades to a safe ``skipped`` / empty manifest.
"""
from __future__ import annotations

import json
import sys
from typing import Any

MANIFEST_VERSION = 1
MANIFEST_KIND = "table_candidates_manifest"

TABLE_CANDIDATES_MANIFEST_FILENAME = "table_candidates_manifest.json"

# --- Closed status / warning vocabulary (this module owns what it emits) ------
MANIFEST_MISSING = "manifest_missing"
MANIFEST_MALFORMED = "manifest_malformed"
MANIFEST_SKIPPED = "manifest_skipped"
RECORD_MALFORMED = "record_malformed"
NOT_TABLE_LIKE = "not_table_like"
SOURCE_PAGE_MISSING = "source_page_missing"
SOURCE_PAGE_INVALID = "source_page_invalid"
RECORD_UNSAFE = "record_unsafe"
MAX_ITEMS_APPLIED = "max_items_applied"

# Deterministic emitted warning ordering (closed tokens only, never raw text).
WARNING_ORDER = [
    MANIFEST_MISSING,
    MANIFEST_MALFORMED,
    MANIFEST_SKIPPED,
    RECORD_MALFORMED,
    NOT_TABLE_LIKE,
    SOURCE_PAGE_MISSING,
    SOURCE_PAGE_INVALID,
    RECORD_UNSAFE,
    MAX_ITEMS_APPLIED,
]

# --- Closed table-kind vocabulary --------------------------------------------
KIND_GRID_TABLE = "grid_table"
KIND_DENSE_TABLE = "dense_table"
KIND_TABLE_REGION = "table_region"
KIND_TABLE_IMAGE = "table_image"
KIND_TABLE_LIKE = "table_like"

# Fields a manifest record may carry a type/kind token in. Read for decisions
# only; never echoed. ``asset_type`` is today's populated field; the others are
# accepted defensively so a future provider tagging a record as e.g. ``"table"``
# is recognized, and so a hostile record cannot smuggle a token through an
# unexpected field name.
_TYPE_FIELDS = (
    "asset_type",
    "visual_kind",
    "visual_type",
    "table_signal",
    "kind",
    "type",
    "category",
)

# Any of these tokens marks a record as table-like. Ordered so the most specific
# kind wins when several are present (grid > dense > region/image > generic).
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
    "table_region": KIND_TABLE_REGION,
    "table_image": KIND_TABLE_IMAGE,
    "table_like": KIND_TABLE_LIKE,
    "tabular": KIND_TABLE_LIKE,
    "table": KIND_TABLE_LIKE,
}

# Closed confidence vocabulary. Anything else collapses to ``unknown``.
_CONFIDENCE_TOKENS = {"high", "medium", "low", "unknown"}
CONFIDENCE_UNKNOWN = "unknown"

# Safe generated candidate-id prefix. The id is purely a sequential ordinal of the
# emitted candidate; it never encodes a slug, filename, path, or any source detail.
CANDIDATE_ID_PREFIX = "table_candidate_"

# Sanitized count signal keys read from a record's ``signals`` dict (or top level)
# and re-emitted as non-negative ints. Counts only — never any text.
_COUNT_SIGNAL_KEYS = (
    "rows",
    "columns",
    "cell_text_count",
    "numeric_cell_count",
    "header_cell_count",
)

# Defensive full ceiling — guards a pathological manifest, NOT a product cap.
_FULL_CANDIDATE_HARD_CEILING = 500

_MISSING = object()


# =============================================================================
# Public API
# =============================================================================


def build_table_candidates_manifest(
    visual_manifest: Any,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    """Pure builder: sanitized visual manifest dict → sanitized table candidates.

    ``visual_manifest`` is a ``visual_assets_manifest.json``-shaped dict (already
    material-page-filtered by Slice 82). Only its ``status`` and ``assets`` list are
    consulted. Each table-like record becomes a sanitized candidate; non-table
    records are skipped and counted; unsafe / malformed / page-less records are
    skipped and counted.

    ``limit`` is an optional **defensive ceiling**, NOT a product cap. Default
    ``None`` keeps every eligible candidate (still bounded by an internal hard
    ceiling). When passed as a non-negative int and more candidates exist, the list
    is truncated in input order, ``status`` becomes ``"partial"``, and
    ``max_items_applied`` is recorded.

    Returns a manifest dict with ``version``, ``kind``, ``status``
    (``completed``/``partial``/``skipped``), ``summary``, ``candidates``,
    ``warnings``. Pure and total: never raises, never reconstructs a table, never
    inspects a PDF/image, never calls a provider. On any unexpected input it
    degrades to a safe ``skipped`` manifest.
    """
    try:
        return _build(visual_manifest, limit)
    except Exception:
        return _skipped_manifest(MANIFEST_MALFORMED)


def table_policy_candidates(manifest: Any) -> list[dict[str, Any]]:
    """Flatten a built table candidate manifest into policy-input dicts.

    Returns the list of sanitized candidate dicts shaped for
    :func:`pipeline.table_reconstruction_policy.build_table_reconstruction_policy`
    (the Slice 85 policy reads ``kind`` + flat count signals + ``has_text_layer`` /
    ``confidence`` at the top level). Pure / total: only closed tokens, ints, bools,
    and ``None`` are produced; never raises and never echoes raw input. Returns
    ``[]`` for a missing / malformed / candidate-less manifest.
    """
    try:
        if not isinstance(manifest, dict):
            return []
        candidates = manifest.get("candidates")
        if not isinstance(candidates, list):
            return []
        out: list[dict[str, Any]] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            signals = candidate.get("signals")
            signals = signals if isinstance(signals, dict) else {}
            policy_candidate: dict[str, Any] = {
                "source_index": candidate.get("source_index"),
                "source_page": candidate.get("source_page"),
                # ``kind`` is a closed table token the policy recognizes directly.
                "kind": candidate.get("table_kind"),
                "confidence": candidate.get("confidence"),
                "has_text_layer": signals.get("has_text_layer") is True,
            }
            for key in _COUNT_SIGNAL_KEYS:
                policy_candidate[key] = _coerce_count(signals.get(key))
            out.append(policy_candidate)
        return out
    except Exception:
        return []


def write_table_candidates_manifest(
    job: Any,
    visual_manifest: Any = None,
) -> dict[str, Any]:
    """Persist ``table_candidates_manifest.json`` under ``job.dir``.

    ``visual_manifest`` is the already-sanitized ``visual_assets_manifest.json``-
    shaped dict (or ``None`` / a skipped stand-in). The manifest is built by the
    pure builder, which handles missing/malformed/skipped inputs by returning a safe
    ``skipped`` manifest. Any disk-write failure is swallowed (a safe message to
    stderr, no raw exception text) and the in-memory manifest is returned; this
    artifact never gates or fails guide generation.

    Returns the manifest dict that was built (whether or not the file write
    succeeded).
    """
    try:
        manifest = build_table_candidates_manifest(visual_manifest)
    except Exception:
        manifest = build_table_candidates_manifest(None)

    try:
        job.save_text(
            job.table_candidates_manifest_json,
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )
    except Exception as exc:  # never let an advisory artifact break a job
        print(
            f"Table candidates manifest skipped ({type(exc).__name__}); job continues.",
            file=sys.stderr,
        )
    return manifest


# =============================================================================
# Builder
# =============================================================================


def _build(visual_manifest: Any, limit: Any) -> dict[str, Any]:
    if visual_manifest is None:
        return _skipped_manifest(MANIFEST_MISSING)
    if not isinstance(visual_manifest, dict):
        return _skipped_manifest(MANIFEST_MALFORMED)

    status = visual_manifest.get("status")
    if isinstance(status, str) and status.strip().lower() == "skipped":
        return _skipped_manifest(MANIFEST_SKIPPED)

    assets = visual_manifest.get("assets")
    if assets is None:
        assets = []
    if not isinstance(assets, list):
        return _skipped_manifest(MANIFEST_MALFORMED)

    warnings: set[str] = set()
    source_indexes: set[int] = set()
    candidates: list[dict[str, Any]] = []
    record_count = 0
    skipped_non_table = 0
    unsafe_or_incomplete = 0

    for record in assets:
        if not isinstance(record, dict):
            warnings.add(RECORD_MALFORMED)
            unsafe_or_incomplete += 1
            continue
        record_count += 1

        source_index = _coerce_source_index(record.get("source_index"))
        if source_index is not None:
            source_indexes.add(source_index)

        table_kind = _detect_table_kind(record)
        if table_kind is None:
            skipped_non_table += 1
            warnings.add(NOT_TABLE_LIKE)
            continue

        if _is_unsafe(record):
            unsafe_or_incomplete += 1
            warnings.add(RECORD_UNSAFE)
            continue

        page, page_warning = _resolve_source_page(record)
        if page is None:
            unsafe_or_incomplete += 1
            warnings.add(page_warning)
            continue

        candidates.append(
            {
                "source_index": source_index,
                "source_page": page,
                "table_kind": table_kind,
                "confidence": _resolve_confidence(record),
                "signals": _sanitized_signals(record),
                "warnings": [],
            }
        )

    # Defensive ceiling: the smaller of the caller limit (if any) and the internal
    # hard ceiling. Truncation is in input order and marks the manifest partial.
    status_token = "completed"
    ceiling = _FULL_CANDIDATE_HARD_CEILING
    if isinstance(limit, int) and not isinstance(limit, bool) and limit >= 0:
        ceiling = min(ceiling, limit)
    if len(candidates) > ceiling:
        candidates = candidates[:ceiling]
        warnings.add(MAX_ITEMS_APPLIED)
        status_token = "partial"

    # Assign deterministic, safe generated candidate ids in emission order.
    for index, candidate in enumerate(candidates, start=1):
        candidate["candidate_id"] = f"{CANDIDATE_ID_PREFIX}{index:04d}"

    pages_with_candidates = len({c["source_page"] for c in candidates})
    summary = {
        "source_count": len(source_indexes),
        "candidate_count": record_count,
        "table_like_candidate_count": len(candidates),
        "skipped_non_table_count": skipped_non_table,
        "unsafe_or_incomplete_skipped_count": unsafe_or_incomplete,
        "page_count_with_table_candidates": pages_with_candidates,
    }
    return _finalize(status_token, summary, candidates, warnings)


# =============================================================================
# Detection / signal helpers (read for decisions; never echo raw input)
# =============================================================================


def _detect_table_kind(record: dict[str, Any]) -> str | None:
    """Return a closed table-kind token, or ``None`` if not table-like."""
    tokens: set[str] = set()
    for field in _TYPE_FIELDS:
        value = record.get(field)
        if isinstance(value, str):
            token = value.strip().lower()
            if token:
                tokens.add(token)
    for token in _TABLE_TOKENS_ORDERED:
        if token in tokens:
            return _TABLE_KIND_MAP[token]
    return None


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


def _resolve_confidence(record: dict[str, Any]) -> str:
    value = record.get("confidence")
    if isinstance(value, str):
        token = value.strip().lower()
        if token in _CONFIDENCE_TOKENS:
            return token
    return CONFIDENCE_UNKNOWN


def _sanitized_signals(record: dict[str, Any]) -> dict[str, Any]:
    """Closed, count-only signal block. Reads ``signals`` (or top level) defensively.

    Emits a fixed-shape dict of a boolean ``has_text_layer`` plus non-negative
    integer counts. No raw input string is ever echoed.
    """
    signals = record.get("signals")
    signals = signals if isinstance(signals, dict) else {}

    def _pick(key: str) -> Any:
        if key in signals:
            return signals.get(key)
        return record.get(key)

    out: dict[str, Any] = {"has_text_layer": _pick("has_text_layer") is True}
    for key in _COUNT_SIGNAL_KEYS:
        out[key] = _coerce_count(_pick(key))
    return out


# =============================================================================
# Field coercion
# =============================================================================


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


def _resolve_source_page(record: dict[str, Any]) -> tuple[int | None, str | None]:
    raw = record.get("source_page", _MISSING)
    if raw is _MISSING or raw is None:
        return None, SOURCE_PAGE_MISSING
    # Strict: a verifiable 1-based page is a positive int (never a float/str/bool).
    if not isinstance(raw, int) or isinstance(raw, bool):
        return None, SOURCE_PAGE_INVALID
    if raw <= 0:
        return None, SOURCE_PAGE_INVALID
    return raw, None


# =============================================================================
# Assembly
# =============================================================================


def _finalize(
    status: str,
    summary: dict[str, Any],
    candidates: list[dict[str, Any]],
    warnings: set[str],
) -> dict[str, Any]:
    return {
        "version": MANIFEST_VERSION,
        "kind": MANIFEST_KIND,
        "status": status,
        "summary": summary,
        "candidates": candidates,
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


def _skipped_manifest(warning: str) -> dict[str, Any]:
    summary = {
        "source_count": 0,
        "candidate_count": 0,
        "table_like_candidate_count": 0,
        "skipped_non_table_count": 0,
        "unsafe_or_incomplete_skipped_count": 0,
        "page_count_with_table_candidates": 0,
    }
    return _finalize("skipped", summary, [], {warning})
