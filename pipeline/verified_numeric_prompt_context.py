"""Verified-numeric **generation prompt-context** builder (Slice 173B).

Slice 173A proved that the recompute engine can INDEPENDENTLY reproduce a subset
of the committed golden numeric values and detect wrong printed ones. Slice 173B
turns ONLY that independently-verified subset into a short, deterministic,
leak-free ``prompt_block`` that an operator harness may append to a Phase 0
golden-pair generation prompt, so the writer uses recompute-proven values instead
of emitting wrong numbers — and falls back to a closed "not verified" phrase for
everything else.

No-laundering contract
----------------------
The records this module consumes come from
``quality_safety_recompute_verifier.build_generation_ready_numeric_records`` which
already gates every record behind independent verification. This module adds the
SECOND half of the discipline — what the writer is told:

* Use each listed verified value EXACTLY; do not replace it with a new estimate.
* For any numeric value NOT listed and not verifiable from the material, write the
  closed fallback ``"Not verified from provided material"`` instead of guessing.
* Never present competing unresolved numeric values.

It never injects fixture-only / source_required / unsupported / verifier_error
values (those never reach it as records), never bans questions or ordinary teaching
wording, and never repeats source content.

Off by default
--------------
``enabled`` defaults to ``False`` ⇒ ``status="skipped"`` ⇒ ``prompt_block=""`` ⇒
the generation prompt stays byte-identical. The block is produced ONLY when an
explicit internal/operator caller passes ``enabled=True``. Normal user generation
never enables it and never has golden records to pass.

Purity & safety
---------------
stdlib + typing only (imports nothing from ``pipeline`` and no provider/model/OCR/
renderer/FastAPI/frontend module). Emits ONLY a closed status token, ints, bools,
the fixed instruction/fallback strings, and the already-closed per-record fields
(student-facing label, rendered verified value, closed kind/confidence tokens). It
never reads or echoes user source text, a filename, path, title, caption, document/
OCR/table text, image/asset ref, base64/data URI, provider payload, token, URL,
argv, socket path, model path, candidate value, fixture tolerance, or raw exception
string. Never raises; malformed input degrades to a safe ``skipped`` context.
"""
from __future__ import annotations

from typing import Any

CONTEXT_VERSION = 1
CONTEXT_KIND = "verified_numeric_prompt_context"

# Closed fallback phrase the writer must use for unverified numeric values.
CLOSED_FALLBACK_PHRASE = "Not verified from provided material"

# Defensive ceiling on how many verified facts are rendered into one block. Not a
# product cap — the real subset is tiny (Slice 173A independently verifies few
# targets). Excess records are dropped from the rendered block with a closed warning.
_MAX_RENDERED_FACTS = 64

# Closed warning vocabulary owned by this module.
ENABLED_NOT_BOOL = "enabled_not_bool"
RECORDS_NOT_LIST = "records_not_list"
RECORD_SKIPPED_MALFORMED = "record_skipped_malformed"
MAX_FACTS_APPLIED = "max_facts_applied"

WARNING_ORDER = [
    ENABLED_NOT_BOOL,
    RECORDS_NOT_LIST,
    RECORD_SKIPPED_MALFORMED,
    MAX_FACTS_APPLIED,
]

# Fixed discipline lines, always emitted when the block is produced (even with zero
# verified facts) so the writer always gets the closed fallback rule.
_HEADER_LINE = "Verified numeric facts:"
_DISCIPLINE_LINES = (
    "- Use these verified values exactly when explaining the corresponding "
    "concept; do not replace them with newly estimated values.",
)
_FALLBACK_LINES = (
    f'- If a numeric value is not listed here and the material does not verify it, '
    f'write "{CLOSED_FALLBACK_PHRASE}" instead of guessing.',
    "- Never present competing unresolved numeric values for the same quantity.",
)


def build_verified_numeric_prompt_context(
    generation_ready_records: Any,
    *,
    enabled: bool | None = False,
    max_facts: int | None = None,
) -> dict[str, Any]:
    """Pure builder: verified generation-ready records -> prompt context.

    Returns a context dict with ``version``, ``kind``, ``status``
    (``completed``/``skipped``), ``summary`` (closed counts), ``prompt_block`` (the
    deterministic instruction text when enabled, else ``""``), and ``warnings``
    (closed tokens only). ``enabled`` defaults ``False`` ⇒ skipped / empty block.
    Pure and total: never raises, calls no provider, inspects no PDF/image, OCRs
    nothing. On any unexpected input it degrades to a safe ``skipped`` context.
    """
    try:
        return _build(generation_ready_records, enabled, max_facts)
    except Exception:
        return _skipped(set(), enabled_flag=False, fact_count=0)


def _build(records: Any, enabled: Any, max_facts: Any) -> dict[str, Any]:
    warnings: set[str] = set()

    # Only a real ``True`` enables. ``None``/``False`` are the normal off cases; any
    # other type is malformed input that degrades to off with a closed warning.
    if enabled is None or enabled is False:
        return _skipped(warnings, enabled_flag=False, fact_count=0)
    if enabled is not True:
        warnings.add(ENABLED_NOT_BOOL)
        return _skipped(warnings, enabled_flag=False, fact_count=0)

    rows = records
    if isinstance(rows, dict):
        # Accept the full generation-ready envelope or just its ``records`` list.
        rows = rows.get("records")
    if not isinstance(rows, list):
        warnings.add(RECORDS_NOT_LIST)
        rows = []

    ceiling = _MAX_RENDERED_FACTS
    if (
        isinstance(max_facts, int)
        and not isinstance(max_facts, bool)
        and 0 <= max_facts < _MAX_RENDERED_FACTS
    ):
        ceiling = max_facts

    fact_lines: list[str] = []
    for record in rows:
        line = _fact_line(record)
        if line is None:
            warnings.add(RECORD_SKIPPED_MALFORMED)
            continue
        if len(fact_lines) >= ceiling:
            warnings.add(MAX_FACTS_APPLIED)
            break
        fact_lines.append(line)

    block = _render_block(fact_lines)

    return {
        "version": CONTEXT_VERSION,
        "kind": CONTEXT_KIND,
        "status": "completed",
        "summary": {
            "enabled": True,
            "verified_fact_count": len(fact_lines),
            "fallback_instruction_present": True,
        },
        "prompt_block": block,
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


def _fact_line(record: Any) -> str | None:
    """Render one verified-value bullet, or ``None`` if the record is malformed.

    Consumes ONLY the closed verified fields. A record missing a verified value or
    carrying a non-``use_verified_value`` instruction is rejected (never rendered),
    so an unverified value can never reach the block.
    """
    if not isinstance(record, dict):
        return None
    if record.get("instruction_token") != "use_verified_value":
        return None
    label = record.get("expected_label")
    if not isinstance(label, str) or not label:
        label = record.get("target_id")
    if not isinstance(label, str) or not label:
        return None
    value = record.get("verified_value_rendered")
    if not isinstance(value, str) or not value:
        return None
    return f"- {label} = {value}"


def _render_block(fact_lines: list[str]) -> str:
    lines: list[str] = [_HEADER_LINE]
    lines.extend(_DISCIPLINE_LINES)
    lines.extend(fact_lines)
    lines.extend(_FALLBACK_LINES)
    return "\n".join(lines)


def _skipped(warnings: set[str], *, enabled_flag: bool, fact_count: int) -> dict[str, Any]:
    return {
        "version": CONTEXT_VERSION,
        "kind": CONTEXT_KIND,
        "status": "skipped",
        "summary": {
            "enabled": bool(enabled_flag),
            "verified_fact_count": int(fact_count),
            "fallback_instruction_present": False,
        },
        "prompt_block": "",
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }
