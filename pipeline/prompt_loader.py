from __future__ import annotations

from pathlib import Path

from pipeline import style_store

BASE_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = BASE_DIR / "prompts"


def load_prompt_template(name: str = "basic_study_guide") -> str:
    """Resolve a built-in or custom style id to its raw template markdown."""
    try:
        return style_store.resolve_prompt_text(name)
    except style_store.StyleNotFoundError as exc:
        raise FileNotFoundError(str(exc)) from exc


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
