"""Generator presets: full SYSTEM prompts + recommended sampling params.

A *generator preset* is a different container from the other two prompt concepts:

* a **style** (``style_store``) is a *user-message* template with
  ``{title}/{mode}/{source}`` slots; it never reaches the system role and carries
  no sampling params.
* a **purpose preset** (``presets``) is an outline + style-id prefill for the UI.
* a **generator preset** (this module) is a complete *system* prompt paired with
  the sampling parameters it was tuned for. Selecting one replaces the system role
  for the LLM call and overrides temperature / top_p / max_tokens.

The three presets are model-tuned (Gemma 4, DeepSeek V4 Pro, Qwen 3.7 Max). Their
prompt **bodies** live in ``prompts/study_guide_prompts.md`` as the single source of
truth: this module parses the fenced ```text blocks under the ``### C1/C2/C3``
headings at call time, so editing that file changes the injected prompt. The
**sampling params** are kept here as code constants because the markdown states them
as prose ranges ("temp 0.3-0.4"); the midpoints chosen below are the canonical
values surfaced through the API.

Stdlib-only so it can be imported from both the pipeline and the API layer.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_MD = BASE_DIR / "prompts" / "study_guide_prompts.md"


class GeneratorPresetError(RuntimeError):
    """Raised when a preset's prompt body cannot be resolved from the source md."""


# Ordered: this is the display order in the Builder. ``block`` is the heading id
# parsed out of study_guide_prompts.md; ``provider`` is the recommended (pinned)
# provider the prompt was tuned for — the API soft-warns on a mismatch rather than
# blocking, so a user can still run any preset against any configured provider.
_PRESET_DEFS: list[dict[str, Any]] = [
    {
        "id": "claude_exam",
        "name": "Claude-Exam",
        "description": (
            "Maximum scaffolding for a weaker local model: rigid skeleton, explicit "
            "assessment-type rules, in-prompt worked-example demo, hard "
            "anti-summarization."
        ),
        "model_hint": "Gemma 4 (31B dense preferred)",
        "provider": "local",
        "block": "C1",
        "temperature": 0.35,
        "top_p": 0.9,
        "max_tokens": None,
        "thinking": True,
    },
    {
        "id": "claude_review",
        "name": "Claude-Review",
        "description": (
            "Compact, principle-driven prompt for a frontier reasoner: states the "
            "philosophy + module menu, trusts the model with the math, hard "
            "anti-verbosity / anti-meta rules."
        ),
        "model_hint": "DeepSeek V4 Pro",
        "provider": "deepseek",
        "block": "C2",
        "temperature": 0.4,
        "top_p": None,
        "max_tokens": None,
        "thinking": True,
    },
    {
        "id": "claude_cram",
        "name": "Claude-Cram",
        "description": (
            "Anti-abstention override for a high-recall-but-hedging model: "
            "completeness beats caution, omission is the failure mode, no hedging."
        ),
        "model_hint": "Qwen 3.7 Max",
        "provider": "qwen",
        "block": "C3",
        "temperature": 0.4,
        "top_p": None,
        "max_tokens": None,
        "thinking": True,
    },
]

_PRESETS_BY_ID = {preset["id"]: preset for preset in _PRESET_DEFS}


def _parse_block(md_text: str, block_id: str) -> str | None:
    """Extract the first ```text fenced block following a ``### <block_id>`` heading.

    Returns ``None`` if the heading or its fenced block is missing (e.g. the md was
    renamed), so callers can degrade gracefully instead of crashing.
    """
    heading = re.search(rf"^###\s+{re.escape(block_id)}\b.*$", md_text, re.MULTILINE)
    if heading is None:
        return None
    # Search only the slice after the heading; the next ```text fence is this
    # section's block (each C-section has exactly one, after its Settings note).
    rest = md_text[heading.end():]
    fence = re.search(r"```text\s*\n(.*?)\n```", rest, re.DOTALL)
    if fence is None:
        return None
    return fence.group(1).strip() or None


def _read_source() -> str:
    try:
        return SOURCE_MD.read_text(encoding="utf-8")
    except OSError as exc:
        raise GeneratorPresetError(
            f"Generator preset source is unreadable: {SOURCE_MD}"
        ) from exc


def generator_preset_exists(preset_id: str) -> bool:
    return preset_id in _PRESETS_BY_ID


def get_generator_preset(preset_id: str) -> dict[str, Any] | None:
    """Return the internal preset definition (incl. params), or None if unknown."""
    return _PRESETS_BY_ID.get(preset_id)


def resolve_system_prompt(preset_id: str) -> str:
    """Return the full system-prompt body for a preset from the source md."""
    preset = _PRESETS_BY_ID.get(preset_id)
    if preset is None:
        raise GeneratorPresetError(f"Unknown generator preset: {preset_id}")
    body = _parse_block(_read_source(), preset["block"])
    if not body:
        raise GeneratorPresetError(
            f"Could not find the {preset['block']} prompt block in {SOURCE_MD.name}. "
            "Its heading or fenced ```text block may have been renamed."
        )
    return body


def _public(preset: dict[str, Any], md_text: str) -> dict[str, Any]:
    # Exposes metadata + params for the UI, but never the prompt body (parity with
    # how styles are listed in /api/options). ``available`` tells the UI whether the
    # body still resolves from the md so a broken preset can be greyed out.
    return {
        "id": preset["id"],
        "name": preset["name"],
        "description": preset["description"],
        "model_hint": preset["model_hint"],
        "provider": preset["provider"],
        "params": {
            "temperature": preset["temperature"],
            "top_p": preset["top_p"],
            "max_tokens": preset["max_tokens"],
            "thinking": preset["thinking"],
        },
        "available": bool(md_text and _parse_block(md_text, preset["block"])),
    }


def list_generator_presets() -> list[dict[str, Any]]:
    """Return all presets as safe public dicts (metadata + params, no bodies)."""
    try:
        md_text = _read_source()
    except GeneratorPresetError:
        md_text = ""
    return [_public(preset, md_text) for preset in _PRESET_DEFS]
