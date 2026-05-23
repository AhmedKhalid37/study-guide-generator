from __future__ import annotations

from pipeline.llm_client import LLMConfig, generate_chat_completion
from pipeline.prompt_loader import load_prompt_template, render_prompt_template


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
        {
            "role": "system",
            "content": (
                "You create accurate, clear Markdown study guides from source text. "
                "Use valid Markdown tables and valid dollar-delimited LaTeX math."
            ),
        },
        {"role": "user", "content": user},
    ]


def generate_study_guide(
    source_text: str,
    *,
    title: str,
    mode: str = "exam",
    prompt_name: str = "basic_study_guide",
    config: LLMConfig | None = None,
) -> str:
    resolved_config = config or LLMConfig.from_env()
    messages = build_messages(source_text, title=title, mode=mode, prompt_name=prompt_name)
    return generate_chat_completion(messages, resolved_config)
