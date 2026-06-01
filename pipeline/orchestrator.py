from __future__ import annotations

from typing import Callable, Iterable, Mapping

from pipeline.llm_client import LLMConfig, generate_chat_completion
from pipeline.prompt_loader import load_prompt_template, render_prompt_template

# Formatting contract the PDF/KaTeX renderer depends on. Used as the system message
# for the default style path, and appended to a generator preset's own system prompt
# (the model-tuned presets specify "Markdown only" but not this math/table syntax).
MARKDOWN_MATH_SYSTEM = (
    "You create accurate, clear Markdown study guides from source text. "
    "Use valid Markdown tables and valid dollar-delimited LaTeX math. "
    "Write math directly as $...$ for inline and $$...$$ for display — "
    "never wrap math in backticks or code spans. For a multi-step "
    "derivation, use one display block with "
    "\\begin{aligned} ... \\end{aligned} (lines separated by \\\\ and "
    "aligned on &=) instead of many separate inline fragments. Keep "
    "long formulas out of table cells; use a short label in the table "
    "and place the full equation in a display block before or after it. "
    "Never put a literal '$' inside a math block. Render matrices, "
    "coordinate sets, and tuples with \\begin{pmatrix} ... \\end{pmatrix} "
    "or a plain Markdown table — never as comma-separated $-delimited "
    "fragments like \"$0,1$, $0,2$\"."
)

# ── Optional output-section toggles ──────────────────────────────────────────
# A generation request may ask for extra output sections via ``include_sections``
# (a dict-of-bool, e.g. {"glossary": true}). This is the SINGLE source of truth
# mapping each canonical toggle key → a short, section-oriented prompt fragment.
# When a request enables one or more toggles, the assembled fragments are injected
# into the system message *before* ``MARKDOWN_MATH_SYSTEM`` (which always stays the
# final block). When no toggles are set the system message is byte-identical to the
# previous behaviour — that backward-compat guarantee is what keeps this safe.
INCLUDE_SECTION_FRAGMENTS: dict[str, str] = {
    "glossary": "Add a glossary table of important terms with simple definitions.",
    "mcqs_with_answers": (
        "Include a set of multiple-choice questions WITH a clearly separated answer key."
    ),
    "mcqs_without_answers": (
        "Include a set of multiple-choice questions WITHOUT answers (questions only, no key)."
    ),
    "flashcards": "Include a flashcards section as front/back question-and-answer pairs.",
    "cram_sheet": "Add a last-minute cram sheet of the highest-yield facts to review just before the exam.",
    "definitions_cheat_sheet": (
        "Add a definitions cheat sheet listing the key terms with their short definitions."
    ),
    "formula_sheet": "Add a formula sheet collecting the key formulas, with each symbol defined.",
    "common_mistakes": (
        "Add a 'Common mistakes' section calling out frequent errors and misconceptions."
    ),
    "exam_alerts": (
        "Add exam alerts highlighting points that are commonly tested or easy to get wrong."
    ),
    "worked_examples": (
        "Include worked examples where the source material contains formulas, calculations, "
        "or step-by-step procedures."
    ),
    "solved_mock_exam": (
        "Include a short solved mock exam: representative questions followed by full solutions."
    ),
    "summary_tables": (
        "Use summary tables to condense comparisons, classifications, or structured facts."
    ),
    "diagrams_figures": (
        "Where a diagram or figure aids understanding, reconstruct it as a Markdown diagram or a "
        "clearly described figure."
    ),
    "citations_references": (
        "Preserve citations and source references from the material where available."
    ),
    "learning_objectives": "Open with a clear list of learning objectives for the material.",
    "self_test_checklist": (
        "Add a self-test checklist the reader can use to confirm they have mastered the material."
    ),
    "instructor_notes": (
        "Preserve instructor/professor notes and points of emphasis from the source where present."
    ),
    "slide_page_references": "Preserve useful slide/page references from the source where available.",
    # Legacy shortcut module keys kept as accepted canonical sections (backward
    # compat with library/shortcuts.json state and any old payloads). They have a
    # clear meaning, so they map to themselves rather than to a misleading alias.
    "summary": "Add a concise TL;DR summary of the most important points.",
    "key_concepts": "Highlight the key concepts in a clearly labelled section.",
    "practice_problems": "Include practice problems for the reader to attempt.",
}

# Legacy shortcut module keys whose canonical name differs. Normalised to the
# canonical key above so the old vocabulary maps onto the new one without
# duplicating fragments or inventing a parallel key set.
INCLUDE_SECTION_ALIASES: dict[str, str] = {
    "mcqs": "mcqs_with_answers",
    "formulas": "formula_sheet",
    "diagrams": "diagrams_figures",
}


def normalize_include_sections(
    include_sections: Mapping[str, object] | Iterable[str] | None,
) -> list[str]:
    """Return the enabled canonical include-section keys, in a stable order.

    Accepts the canonical dict-of-bool request shape (``{"glossary": true}``) or a
    plain iterable of keys. Legacy keys are mapped through ``INCLUDE_SECTION_ALIASES``.
    Unknown/unsupported keys are ignored (matching the repo's whitelist convention
    for untrusted toggle input). Order follows ``INCLUDE_SECTION_FRAGMENTS`` so the
    assembled prompt is deterministic regardless of incoming dict ordering."""
    if include_sections is None:
        return []
    if isinstance(include_sections, Mapping):
        requested = [str(key) for key, value in include_sections.items() if value]
    elif isinstance(include_sections, (str, bytes)):
        requested = []
    elif isinstance(include_sections, Iterable):
        requested = [str(key) for key in include_sections]
    else:
        requested = []
    enabled: set[str] = set()
    for key in requested:
        canonical = INCLUDE_SECTION_ALIASES.get(key, key)
        if canonical in INCLUDE_SECTION_FRAGMENTS:
            enabled.add(canonical)
    return [key for key in INCLUDE_SECTION_FRAGMENTS if key in enabled]


def build_include_sections_block(
    include_sections: Mapping[str, object] | Iterable[str] | None,
) -> str:
    """Assemble the include-section instruction block from enabled toggles.

    Returns "" when nothing is enabled, so callers can inject it without changing
    the prompt for the default (no-toggle) request."""
    keys = normalize_include_sections(include_sections)
    if not keys:
        return ""
    lines = ["Also include the following sections in the study guide where the source supports them:"]
    lines.extend(f"- {INCLUDE_SECTION_FRAGMENTS[key]}" for key in keys)
    return "\n".join(lines)


def _system_with_sections(*parts: str) -> str:
    """Join non-empty system-prompt parts, keeping ``MARKDOWN_MATH_SYSTEM`` last.

    Callers pass parts in final order ending with ``MARKDOWN_MATH_SYSTEM``; empty
    parts (e.g. an absent include block) drop out so the no-toggle output is
    byte-identical to the previous single-block behaviour."""
    return "\n\n".join(part for part in parts if part)


def build_messages(
    source_text: str,
    *,
    title: str,
    mode: str = "exam",
    prompt_name: str = "basic_study_guide",
    include_sections: Mapping[str, object] | Iterable[str] | None = None,
) -> list[dict]:
    template = load_prompt_template(prompt_name)
    user = render_prompt_template(template, title=title, mode=mode, source=source_text)
    system = _system_with_sections(
        build_include_sections_block(include_sections),
        MARKDOWN_MATH_SYSTEM,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_messages_for_preset(
    source_text: str,
    *,
    system_prompt: str,
    include_sections: Mapping[str, object] | Iterable[str] | None = None,
) -> list[dict]:
    """Messages for a generator preset: the preset IS the system prompt (plus the
    renderer's math/table rules), and the source goes verbatim as the user turn."""
    system = _system_with_sections(
        system_prompt,
        build_include_sections_block(include_sections),
        MARKDOWN_MATH_SYSTEM,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": source_text},
    ]


def generate_study_guide(
    source_text: str,
    *,
    title: str,
    mode: str = "exam",
    prompt_name: str = "basic_study_guide",
    generator_preset: str | None = None,
    include_sections: Mapping[str, object] | Iterable[str] | None = None,
    config: LLMConfig | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> str:
    # ``on_stage`` (when provided) reports coarse progress at the boundaries that
    # already exist here. It is optional so non-job callers stay unaffected. The
    # LLM call itself is a single blocking completion, so "writing" simply spans
    # its whole duration — we can't sub-progress it without streaming.
    resolved_config = config or LLMConfig.from_env()
    if generator_preset:
        # Late import keeps the module stdlib-light and avoids a circular import.
        from pipeline import generator_presets

        if on_stage is not None:
            on_stage("loading_preset")
        system_prompt = generator_presets.resolve_system_prompt(generator_preset)
        messages = build_messages_for_preset(
            source_text, system_prompt=system_prompt, include_sections=include_sections
        )
    else:
        messages = build_messages(
            source_text,
            title=title,
            mode=mode,
            prompt_name=prompt_name,
            include_sections=include_sections,
        )
    if on_stage is not None:
        on_stage("connecting_model")
        on_stage("writing")
    return generate_chat_completion(messages, resolved_config)
