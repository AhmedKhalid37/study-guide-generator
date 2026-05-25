from __future__ import annotations

from pathlib import Path

from pipeline import style_store

BASE_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = BASE_DIR / "prompts"


def load_prompt_template(name: str = "basic_study_guide") -> str:
    """Resolve a built-in/custom style id to its raw template markdown.

    Falls back to a direct read of ``prompts/<name>.md`` for non-style prompt
    files (e.g. the system/user scaffolding) so the original contract — load any
    prompt file by name — keeps working.
    """
    try:
        return style_store.resolve_prompt_text(name)
    except style_store.StyleNotFoundError:
        path = PROMPTS_DIR / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}") from None
        return path.read_text(encoding="utf-8")


def render_prompt_template(
    template: str,
    *,
    title: str,
    mode: str,
    source: str,
) -> str:
    return (
        template.replace("{title}", title)
        .replace("{mode}", mode)
        .replace("{source}", source)
    )
