"""Purpose presets: a named bundle of an outline template + a style preset.

Selecting a preset in the Builder pre-fills the outline sections and the style
selector. The user can still edit both before generating, so these are starting
points, not locked configurations.

Stdlib-only so it can be imported from both the pipeline and the API layer.
Each preset references a built-in style by id; if that style is ever missing,
:func:`apply_preset` falls back to ``basic_study_guide`` rather than failing.
"""

from __future__ import annotations

from typing import Any

from pipeline import style_store

_FALLBACK_STYLE = "basic_study_guide"

# Ordered list — this is the display order in the Builder dropdown. Each preset
# bundles an outline (section title + one-line instructions) with a style id.
PRESETS: list[dict[str, Any]] = [
    {
        "id": "exam_guide",
        "name": "Exam Cram",
        "description": "Dense, high-yield exam guide built for fast review.",
        "style_preset_id": "exam_cram",
        "outline_sections": [
            {"title": "Exam Overview", "instructions": "State the exam scope and the highest-yield topics."},
            {"title": "Key Definitions", "instructions": "List must-know terms with one-line definitions."},
            {"title": "Core Formulas", "instructions": "Compile every formula with each variable defined."},
            {"title": "Worked Examples", "instructions": "Show 2-3 representative solved problems."},
            {"title": "Common Pitfalls", "instructions": "Call out frequent mistakes and exam traps."},
            {"title": "Rapid Review", "instructions": "A bullet-point cheat sheet for last-minute scanning."},
        ],
    },
    {
        "id": "report_guide",
        "name": "Academic Report",
        "description": "Formal, structured report with introduction through conclusion.",
        "style_preset_id": "master_longform",
        "outline_sections": [
            {"title": "Introduction", "instructions": "Introduce the topic, scope, and objectives."},
            {"title": "Background", "instructions": "Provide the necessary context and prior work."},
            {"title": "Main Analysis", "instructions": "Present the core arguments and evidence in depth."},
            {"title": "Discussion", "instructions": "Interpret the findings and weigh the implications."},
            {"title": "Conclusion", "instructions": "Summarize the key takeaways and closing thoughts."},
            {"title": "References", "instructions": "List sources and suggested further reading."},
        ],
    },
    {
        "id": "presentation",
        "name": "Presentation",
        "description": "Slide-ready outline with large headings and minimal text per section.",
        "style_preset_id": "basic_study_guide",
        "outline_sections": [
            {"title": "Title & Agenda", "instructions": "A one-line title and a short agenda of topics."},
            {"title": "Key Idea 1", "instructions": "One slide-sized idea with a few bullet points."},
            {"title": "Key Idea 2", "instructions": "Another concise idea with supporting bullets."},
            {"title": "Key Idea 3", "instructions": "A third focused idea, kept to minimal text."},
            {"title": "Summary", "instructions": "Recap the main points in a few bullets."},
            {"title": "Questions", "instructions": "Prompts for discussion or review."},
        ],
    },
    {
        "id": "chapter_summary",
        "name": "Chapter Summary",
        "description": "Big picture, key terms, examples, and common mistakes for one chapter.",
        "style_preset_id": "basic_study_guide",
        "outline_sections": [
            {"title": "Big Picture", "instructions": "Explain the chapter's central idea in plain language."},
            {"title": "Key Terms", "instructions": "Define the essential vocabulary."},
            {"title": "Examples", "instructions": "Give concrete examples that illustrate the concepts."},
            {"title": "Common Mistakes", "instructions": "Highlight misconceptions and how to avoid them."},
        ],
    },
    {
        "id": "final_revision",
        "name": "Final Revision",
        "description": "Compressed, formula-heavy format for exam-week revision.",
        "style_preset_id": "exam_cram",
        "outline_sections": [
            {"title": "Formula Sheet", "instructions": "All key formulas compiled, with variables defined."},
            {"title": "Core Concepts", "instructions": "An ultra-condensed summary of the must-know concepts."},
            {"title": "Worked Examples", "instructions": "A few high-yield solved problems."},
            {"title": "Memory Cues", "instructions": "Mnemonics and quick recall aids."},
            {"title": "Final Checklist", "instructions": "A last-minute checklist before the exam."},
        ],
    },
]

_PRESETS_BY_ID = {preset["id"]: preset for preset in PRESETS}


def list_presets() -> list[dict[str, Any]]:
    """Return all presets as safe dicts (id, name, description, style, sections)."""
    return [_public(preset) for preset in PRESETS]


def get_preset(preset_id: str) -> dict[str, Any] | None:
    preset = _PRESETS_BY_ID.get(preset_id)
    return _public(preset) if preset else None


def apply_preset(preset_id: str) -> dict[str, Any] | None:
    """Return the {outline, style} payload the Builder uses to pre-fill its form.

    ``outline`` is an enabled outline with the preset's sections; ``style`` is the
    preset's style id, falling back to ``basic_study_guide`` if the referenced
    style no longer exists.
    """
    preset = _PRESETS_BY_ID.get(preset_id)
    if preset is None:
        return None
    style_id = preset["style_preset_id"]
    if not style_store.style_exists(style_id):
        style_id = _FALLBACK_STYLE
    sections = [
        {"title": section["title"], "instructions": section["instructions"]}
        for section in preset["outline_sections"]
    ]
    return {
        "outline": {"enabled": True, "sections": sections},
        "style": style_id,
        "preset_id": preset["id"],
    }


def _public(preset: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": preset["id"],
        "name": preset["name"],
        "description": preset["description"],
        "style_preset_id": preset["style_preset_id"],
        "outline_sections": [
            {"title": section["title"], "instructions": section["instructions"]}
            for section in preset["outline_sections"]
        ],
    }
