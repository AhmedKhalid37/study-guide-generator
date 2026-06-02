from __future__ import annotations

import re
from dataclasses import dataclass

from markdown_it import MarkdownIt


@dataclass
class Section:
    """A parsed section of a Markdown document.

    index:          0-based position in the list returned by parse_sections.
    heading_text:   The heading's inline content ("" for the preamble).
    heading_level:  1-6 for h1-h6, 0 for the preamble section.
    start_token:    Index of heading_open token in flat token list (-1 for preamble).
    end_token:      Index of last token in this section (-1 for empty preamble).
    start_line:     0-indexed first source line of this section.
    end_line:       0-indexed line just after this section (exclusive).
    raw_markdown:   Verbatim source text for this section.
    """

    index: int
    heading_text: str
    heading_level: int
    start_token: int
    end_token: int
    start_line: int
    end_line: int
    raw_markdown: str


_MD = MarkdownIt()


def parse_sections(markdown_text: str) -> list[Section]:
    """Parse *markdown_text* into a list of Section objects.

    Sections are determined by heading level: a section spans from its heading
    line up to (but not including) the next heading of equal-or-higher level.
    Content before the first heading becomes a *preamble* section (index 0,
    heading_level 0, heading_text "").

    Correctness guarantees:
    - Headings inside fenced code blocks are NOT tokenised as heading_open by
      markdown-it-py and are therefore ignored.
    - Repeated heading titles are handled correctly: sections are identified by
      token/line position, never by title string.
    - Nested sub-headings: each section spans until the next heading of
      equal-or-higher level (or EOF), so sub-sections are fully contained within
      their parent section's span.
    """
    tokens = _MD.parse(markdown_text)
    source_lines = markdown_text.splitlines(keepends=True)
    total_lines = len(source_lines)

    # Collect (token_list_idx, heading_level, heading_text, start_line) for every heading.
    headings: list[tuple[int, int, str, int]] = []
    for i, token in enumerate(tokens):
        if token.type == "heading_open" and token.map is not None:
            level = int(token.tag[1])  # 'h1' -> 1, 'h2' -> 2, …
            text = (
                tokens[i + 1].content
                if (i + 1 < len(tokens) and tokens[i + 1].type == "inline")
                else ""
            )
            headings.append((i, level, text, token.map[0]))

    sections: list[Section] = []

    # ── Preamble (content before the first heading) ──────────────────────────
    preamble_end = headings[0][3] if headings else total_lines
    if preamble_end > 0 or not headings:
        sections.append(
            Section(
                index=0,
                heading_text="",
                heading_level=0,
                start_token=-1,
                end_token=-1,
                start_line=0,
                end_line=preamble_end,
                raw_markdown="".join(source_lines[:preamble_end]),
            )
        )

    # ── Heading sections ─────────────────────────────────────────────────────
    for h_idx, (tok_idx, level, text, start_line) in enumerate(headings):
        # A section ends at the first subsequent heading of equal-or-higher level.
        end_line = total_lines
        for _, next_level, _, next_start in headings[h_idx + 1 :]:
            if next_level <= level:
                end_line = next_start
                break

        # end_token: last token index in the flat list that belongs to this section.
        end_tok = len(tokens) - 1
        for nxt_tok_idx, nxt_level, _, _ in headings[h_idx + 1 :]:
            if nxt_level <= level:
                end_tok = nxt_tok_idx - 1
                break

        sections.append(
            Section(
                index=len(sections),
                heading_text=text,
                heading_level=level,
                start_token=tok_idx,
                end_token=end_tok,
                start_line=start_line,
                end_line=end_line,
                raw_markdown="".join(source_lines[start_line:end_line]),
            )
        )

    return sections


def splice_section(markdown_text: str, section: Section, new_content: str) -> str:
    """Replace *section*'s raw markdown in *markdown_text* with *new_content*.

    Uses the parser-derived line positions — never string matching — so that
    sections with duplicate heading titles are always spliced at the correct
    position.
    """
    source_lines = markdown_text.splitlines(keepends=True)
    prefix = "".join(source_lines[: section.start_line])
    suffix = "".join(source_lines[section.end_line :])
    # Ensure a newline boundary between the new content and the next section.
    if new_content and not new_content.endswith("\n") and suffix:
        new_content += "\n"
    return prefix + new_content + suffix


def normalize_heading(text: str) -> str:
    """Normalise a heading for loose comparison: strip inline markup, lowercase, collapse spaces."""
    # Strip bold / italic markers
    text = re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_\n]+)_{1,3}", r"\1", text)
    # Strip inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Strip remaining markdown punctuation
    text = re.sub(r"[*_`#]", "", text)
    return " ".join(text.lower().split())


def _word_jaccard(a: str, b: str) -> float:
    wa = set(a.split())
    wb = set(b.split())
    if not wa and not wb:
        return 1.0
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def check_outline_compliance(
    outline_titles: list[str],
    doc_sections: list[Section],
) -> list[dict]:
    """Compare *outline_titles* against headings present in *doc_sections*.

    Each result dict contains:
        required_title  – the original outline section title
        status          – "found" | "renamed" | "missing"
        matched_heading – the doc heading that was matched (None if missing)

    Algorithm:
      Pass 1 — exact normalised match → "found".
      Pass 2 — best word-Jaccard match (threshold 0.30) → "renamed".
      Otherwise → "missing".

    A doc heading is consumed after being matched and cannot be reused.
    """
    heading_sections = [s for s in doc_sections if s.heading_level > 0]
    doc_norm = [normalize_heading(s.heading_text) for s in heading_sections]
    available = list(range(len(heading_sections)))

    results: list[dict | None] = [None] * len(outline_titles)
    unmatched: list[tuple[int, str, str]] = []

    # Pass 1: exact normalised matches.
    for out_i, title in enumerate(outline_titles):
        norm = normalize_heading(title)
        matched: int | None = None
        for ai in available:
            if doc_norm[ai] == norm:
                matched = ai
                break
        if matched is not None:
            available.remove(matched)
            results[out_i] = {
                "required_title": title,
                "status": "found",
                "matched_heading": heading_sections[matched].heading_text,
            }
        else:
            unmatched.append((out_i, title, norm))

    # Pass 2: similarity-based (renamed) matches.
    for out_i, title, norm in unmatched:
        best_score = 0.30
        best_ai: int | None = None
        for ai in available:
            score = _word_jaccard(norm, doc_norm[ai])
            if score > best_score:
                best_score = score
                best_ai = ai
        if best_ai is not None:
            available.remove(best_ai)
            results[out_i] = {
                "required_title": title,
                "status": "renamed",
                "matched_heading": heading_sections[best_ai].heading_text,
            }
        else:
            results[out_i] = {
                "required_title": title,
                "status": "missing",
                "matched_heading": None,
            }

    return results  # type: ignore[return-value]
