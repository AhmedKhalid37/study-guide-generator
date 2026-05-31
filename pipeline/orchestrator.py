from __future__ import annotations

from typing import Callable

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


def build_messages(
    source_text: str,
    *,
    title: str,
    mode: str = "exam",
    prompt_name: str = "basic_study_guide",
) -> list[dict]:
    template = load_prompt_template(prompt_name)
    user = render_prompt_template(template, title=title, mode=mode, source=source_text)
    return [
        {"role": "system", "content": MARKDOWN_MATH_SYSTEM},
        {"role": "user", "content": user},
    ]


def build_messages_for_preset(source_text: str, *, system_prompt: str) -> list[dict]:
    """Messages for a generator preset: the preset IS the system prompt (plus the
    renderer's math/table rules), and the source goes verbatim as the user turn."""
    return [
        {"role": "system", "content": f"{system_prompt}\n\n{MARKDOWN_MATH_SYSTEM}"},
        {"role": "user", "content": source_text},
    ]


def generate_study_guide(
    source_text: str,
    *,
    title: str,
    mode: str = "exam",
    prompt_name: str = "basic_study_guide",
    generator_preset: str | None = None,
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
        messages = build_messages_for_preset(source_text, system_prompt=system_prompt)
    else:
        messages = build_messages(source_text, title=title, mode=mode, prompt_name=prompt_name)
    if on_stage is not None:
        on_stage("connecting_model")
        on_stage("writing")
    return generate_chat_completion(messages, resolved_config)
