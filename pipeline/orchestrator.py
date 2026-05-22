from __future__ import annotations

from pipeline.llm_client import LLMConfig, generate_chat_completion
from pipeline.prompt_loader import load_prompt_template


def build_messages(source_text: str, *, title: str, mode: str = "exam") -> list[dict]:
    template = load_prompt_template("basic_study_guide")
    user = template.format(title=title, mode=mode, source=source_text)
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
    config: LLMConfig | None = None,
) -> str:
    resolved_config = config or LLMConfig.from_env()
    messages = build_messages(source_text, title=title, mode=mode)
    return generate_chat_completion(messages, resolved_config)
