"""Claude-quality guide **prompt-contract** builder (Slice 102).

Slices 82–99 taught generation about *material coverage* and added an optional
dual-explanation study-quality layer. Slice 102 begins a guide-*quality* correction
phase: it encodes a distilled, source-of-truth set of generation directives — the
"guide quality contract" — that long/comprehensive exam guides must follow, so the
app's output discipline and depth approach a human-authored reference guide.

Product goal (distilled — no source evidence embedded)
------------------------------------------------------
Comprehensive exam guides should: assume zero prior knowledge; never leak the
model's own reasoning, uncertainty, prompt/user-intent analysis, planning notes,
process narration, or meta-commentary (Slice 151 hardened the final-output
hygiene clause after a measured reasoning leak); never fabricate math; stay numerically
self-consistent; finish every worked example; show all arithmetic; build beginner
intuition for hard mechanics; put high-yield reference data in labelled tables;
include the required consolidation sections; and teach in a confident, exam-focused
voice with exam-alert flags.

The distilled rules are encoded here as fixed, deterministic, leak-free text. The
product spec that motivated them lives OUTSIDE the repo; none of its real evidence
quotes, arithmetic, source deck names, or output/reference filenames are copied here
— only the generic directives.

Scope (Slice 102 = prompt-context only, here)
---------------------------------------------
Pure derivation only. This module calls no LLM / provider / model / VLM / Chandra /
Mistral / Gemini / cloud, changes no provider/model selection, inspects no
PDF/image, reads no image bytes, reconstructs no table, extracts no table text,
renders nothing, exports nothing, changes no figure-insertion / material-selection /
visual-manifest-filter / Ask-Guide behaviour, and adds no UI. It reads ONLY safe
scalar request signals (depth/difficulty axis enums, preset id, style id, mode, and
an optional explicit ``comprehensive`` bool) and returns a sanitized context dict
whose ``prompt_block`` is safe to append to the generation prompt.

Purity & safety
---------------
stdlib-only (imports nothing from ``pipeline`` and no provider/model/OCR/renderer/
FastAPI/frontend module). The context emits **only** a closed status token, ints,
bools, and fixed instruction strings. It never reads or echoes user source text, a
filename, path, source title, caption, document / OCR / table text, image ref, asset
ref, image byte, base64 / data URI, provider payload, token, URL, argv, socket path,
model path, or raw exception string. Never raises; any malformed input degrades to a
safe context.
"""
from __future__ import annotations

from typing import Any

CONTEXT_VERSION = 1
CONTEXT_KIND = "guide_quality_prompt_contract"

# --- Comprehensive-guide signal sources --------------------------------------
# An "exhaustive" depth axis, or any of the longform/exam generator presets /
# longform styles, marks a guide as comprehensive (full structural contract).
# A "quick" depth axis explicitly opts OUT (core rules only). These are safe,
# closed id sets — never source content.
_COMPREHENSIVE_PRESET_IDS = frozenset({"claude_exam", "claude_review", "claude_cram"})
_COMPREHENSIVE_STYLE_IDS = frozenset({"master_longform", "exam_cram"})
_EXHAUSTIVE_DEPTH = "exhaustive"
_QUICK_DEPTH = "quick"

# --- Closed warning vocabulary (this module owns what it emits) --------------
COMPREHENSIVE_INFERRED = "comprehensive_inferred"
CORE_ONLY = "core_only"
OUTPUT_DEPTH_UNKNOWN = "output_depth_unknown"

WARNING_ORDER = [
    COMPREHENSIVE_INFERRED,
    CORE_ONLY,
    OUTPUT_DEPTH_UNKNOWN,
]

_KNOWN_DEPTHS = frozenset({"", "quick", "balanced", "exhaustive", "auto"})

# --- The distilled directives (generic; no source evidence) ------------------
# Core rules apply to every generated guide. They are phrased model-agnostically;
# on a thinking-capable model all deliberation stays in the private reasoning
# channel and never reaches the output.
_CORE_RULES: tuple[str, ...] = (
    "Resolve all ambiguity silently. The guide must read as settled fact and show "
    "only conclusions, never the reasoning used to reach them.",
    "Never leak reasoning or uncertainty. Do not write self-questions in "
    "explanatory prose, hedges, or words like \"Actually\", \"it seems\", "
    "\"I think\", \"let's infer\", \"confusing\", \"unclear\", \"I'm not sure\", "
    "\"presumably\", or \"the slide is\". If a source is ambiguous, choose the most "
    "defensible reading and state it plainly.",
    "Output only the finished study guide. The guide must contain only "
    "student-facing study content — never internal reasoning, hidden analysis, "
    "analysis of the prompt or instructions, commentary on what the prompt or user "
    "is asking for, planning or drafting notes, process narration about what you "
    "are about to do, or meta-commentary about the guide itself. Start directly "
    "with the guide's content and include nothing that is not part of the guide.",
    "Never fabricate math. State a formula, derivative, or numeric result only if "
    "it is taken from the source or computed by you with the steps shown. If you "
    "are not certain of a closed form, describe the behaviour in words instead of "
    "writing a formula.",
    "Finish every worked example. If a model has multiple outputs, classes, or "
    "cases, compute all of them and state the final decision explicitly; never stop "
    "at a partial result.",
    "Show all arithmetic. Substitute the numbers, show each product or sum on its "
    "own line, then the result, so the reader can reproduce every line without "
    "mental math.",
    "Reuse every value consistently. A weight, proximity, hyperparameter, or "
    "intermediate result must not appear with two different values anywhere in the "
    "guide.",
    "Define every term before it is used. Give the source wording where wording "
    "matters, plus a plain-English restatement.",
    "After every formula, add a one-line plain-English translation of what it says.",
    "For every non-obvious mechanic, include a beginner-friendly intuition block, "
    "and a from-scratch derivation wherever a calculation is involved.",
    "Put exam-required reference data — weights and biases, hyperparameters, "
    "mappings, comparisons, and advantages/disadvantages — in labelled tables, not "
    "only in prose or ASCII diagrams.",
    "Write in a confident, directive exam-tutor voice. Tell the reader what matters "
    "and where marks are lost.",
    "Flag exam-likely or easily-missed points with a consistent marker: "
    "⚠️ EXAM ALERT.",
    "Simplicity and comprehensiveness never trade off. Keep each piece simple to "
    "read while still covering everything; do not summarise or drop content to save "
    "space.",
)

# Structural skeleton required of comprehensive/long guides, in order. Existing
# styles may phrase headings slightly differently; the companion lint allows safe
# aliases rather than demanding these exact words.
_STRUCTURE_RULES: tuple[str, ...] = (
    "Header: the lecture or topic name, source attribution, and one line on how the "
    "guide is organised (grouped by topic, not slide order).",
    "How to use this guide (short).",
    "Big Picture: the 3-6 exam-critical questions this material answers.",
    "Notation / terms you must know, as a table.",
    "Topic sections in logical order (not slide order). For each topic: a "
    "definition plus plain-English restatement; every formula followed by a "
    "translation; fully worked example(s) carried to the final answer with all "
    "arithmetic; an intuition block for hard mechanics; exam-alert callouts; and an "
    "interpretation of each result.",
    "Summary / comparison tables, including advantages and disadvantages where "
    "relevant.",
    "Formula sheet: every formula in one place with its meaning and source page.",
    "Definitions cheat sheet, as a table.",
    "Common Mistakes That Lose Marks.",
    "Consolidation / pipeline section for process topics: an end-to-end flow plus a "
    "decision table.",
    "Mock Exam: multiple questions, each with a full step-by-step worked solution.",
    "Last-Minute Cram Sheet: the densest high-yield recap.",
    "Self-Test Checklist using \"Can I...?\" items.",
)

_CORE_HEADER = (
    "Guide quality contract (these rules take precedence over any weaker or "
    "conflicting instruction elsewhere in this prompt):"
)
_STRUCTURE_HEADER = "Required comprehensive guide structure (produce all sections, in order):"


# =============================================================================
# Public API
# =============================================================================


def infer_comprehensive(
    output_depth: str | None = None,
    preset_id: str | None = None,
    style_id: str | None = None,
    mode: str | None = None,
) -> bool:
    """Decide whether a request is a comprehensive/long guide (full structure).

    Precedence: an explicit ``quick`` depth opts out; an ``exhaustive`` depth opts
    in; otherwise any longform/exam generator preset or longform style opts in. Pure
    and total — only safe scalar ids are inspected; ``mode`` is accepted for future
    use but not currently load-bearing. Never raises.
    """
    try:
        depth = _norm(output_depth)
        if depth == _QUICK_DEPTH:
            return False
        if depth == _EXHAUSTIVE_DEPTH:
            return True
        if _norm(preset_id) in _COMPREHENSIVE_PRESET_IDS:
            return True
        if _norm(style_id) in _COMPREHENSIVE_STYLE_IDS:
            return True
        return False
    except Exception:
        return False


def build_guide_quality_prompt_contract(
    *,
    output_depth: str | None = None,
    difficulty: str | None = None,
    preset_id: str | None = None,
    style_id: str | None = None,
    mode: str | None = None,
    comprehensive: bool | None = None,
) -> dict[str, Any]:
    """Pure builder: safe request signals -> guide-quality prompt contract.

    Returns a context dict with ``version``, ``kind``, ``status``
    (``completed``/``skipped``), ``summary`` (``comprehensive`` +
    ``core_rule_count`` + ``structure_rule_count`` + ``prompt_item_count``),
    ``prompt_block`` (the deterministic contract text), and ``warnings`` (closed
    tokens only). The core rules are always included; the full structural contract
    is added only for comprehensive/long guides. ``comprehensive`` may be forced via
    the explicit bool; otherwise it is inferred from the depth axis / preset / style.

    Pure and total: never raises, calls no provider, inspects no PDF/image, OCRs
    nothing, reconstructs no table. On any unexpected input it degrades to a safe
    ``skipped`` context with an empty ``prompt_block``.
    """
    try:
        return _build(output_depth, difficulty, preset_id, style_id, mode, comprehensive)
    except Exception:
        return _skipped(set(), comprehensive_flag=False)


# =============================================================================
# Builder
# =============================================================================


def _build(
    output_depth: Any,
    difficulty: Any,
    preset_id: Any,
    style_id: Any,
    mode: Any,
    comprehensive: Any,
) -> dict[str, Any]:
    warnings: set[str] = set()

    depth = _norm(output_depth)
    if depth and depth not in _KNOWN_DEPTHS:
        warnings.add(OUTPUT_DEPTH_UNKNOWN)

    if comprehensive is True or comprehensive is False:
        is_comprehensive = bool(comprehensive)
    else:
        is_comprehensive = infer_comprehensive(
            _norm(output_depth) or None,
            _norm(preset_id) or None,
            _norm(style_id) or None,
            _norm(mode) or None,
        )
        warnings.add(COMPREHENSIVE_INFERRED if is_comprehensive else CORE_ONLY)

    lines: list[str] = [_CORE_HEADER]
    lines.extend(f"- {rule}" for rule in _CORE_RULES)
    structure_count = 0
    if is_comprehensive:
        structure_count = len(_STRUCTURE_RULES)
        lines.append("")
        lines.append(_STRUCTURE_HEADER)
        lines.extend(
            f"{index}. {rule}" for index, rule in enumerate(_STRUCTURE_RULES, start=1)
        )

    core_count = len(_CORE_RULES)
    return {
        "version": CONTEXT_VERSION,
        "kind": CONTEXT_KIND,
        "status": "completed",
        "summary": {
            "comprehensive": is_comprehensive,
            "core_rule_count": core_count,
            "structure_rule_count": structure_count,
            "prompt_item_count": core_count + structure_count,
        },
        "prompt_block": "\n".join(lines),
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


# =============================================================================
# Assembly
# =============================================================================


def _norm(value: Any) -> str:
    """Lower-cased, stripped string for a scalar id/enum; '' for anything else."""
    if isinstance(value, str):
        return value.strip().lower()
    return ""


def _skipped(warnings: set[str], *, comprehensive_flag: bool) -> dict[str, Any]:
    return {
        "version": CONTEXT_VERSION,
        "kind": CONTEXT_KIND,
        "status": "skipped",
        "summary": {
            "comprehensive": bool(comprehensive_flag),
            "core_rule_count": 0,
            "structure_rule_count": 0,
            "prompt_item_count": 0,
        },
        "prompt_block": "",
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }
