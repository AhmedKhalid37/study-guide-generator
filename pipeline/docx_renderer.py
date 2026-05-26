"""Convert a cleaned Markdown file into an editable .docx (Word) document.

Source of truth is the job's ``clean.md`` — the same sanitized Markdown the PDF
and HTML are rendered from. This module never re-runs the LLM and never touches
the PDF/HTML render path; it is a standalone, dependency-light converter built on
``markdown-it-py`` (already used by the HTML renderer) + ``python-docx``.

Supported Markdown features:
  - headings (h1–h6 -> Word Heading styles)
  - paragraphs with **bold**, *italic*, ~~strikethrough~~, `inline code`, links
  - bullet and numbered lists (incl. one level of nesting)
  - fenced/indented code blocks (monospace, preserved)
  - tables (rendered as a Word grid table)
  - horizontal rules

Known limitations (documented, not silent):
  - Math is preserved as literal LaTeX text (``$...$`` / ``$$...$$``), not rendered
    as equations — DOCX has no KaTeX equivalent in this pipeline.
  - Images are emitted as a ``[image: alt]`` text placeholder (not embedded).
  - Deeply nested lists collapse to the deepest supported Word list style (3).
  - Raw HTML in Markdown is rendered as plain text, not interpreted.
"""

from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt

# Mirror the HTML renderer's Markdown dialect so DOCX and HTML agree on structure
# (tables + strikethrough enabled). html:False — we never interpret raw HTML here.
_PARSER = (
    MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": False})
    .enable("table")
    .enable("strikethrough")
)

_CODE_FONT = "Courier New"


def render_docx(markdown_path, output_path):
    """Render ``markdown_path`` (a clean.md) into a .docx at ``output_path``."""
    from docx import Document

    source = Path(markdown_path)
    target = Path(output_path)
    text = source.read_text(encoding="utf-8", errors="replace")

    document = Document()
    _emit_blocks(document, _PARSER.parse(text))

    target.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(target))
    return target


def _emit_blocks(document, tokens) -> None:
    list_stack: list[str] = []  # "bullet" | "ordered", deepest last
    i = 0
    n = len(tokens)
    while i < n:
        token = tokens[i]
        kind = token.type

        if kind == "heading_open":
            level = min(int(token.tag[1:] or 1), 9)
            paragraph = document.add_heading(level=level)
            _emit_inline(paragraph, tokens[i + 1])
            i += 3  # heading_open, inline, heading_close
            continue

        if kind == "paragraph_open":
            inline = tokens[i + 1]
            if list_stack:
                paragraph = document.add_paragraph(style=_list_style(list_stack[-1], len(list_stack)))
            else:
                paragraph = document.add_paragraph()
            _emit_inline(paragraph, inline)
            i += 3  # paragraph_open, inline, paragraph_close
            continue

        if kind == "bullet_list_open":
            list_stack.append("bullet")
            i += 1
            continue
        if kind == "ordered_list_open":
            list_stack.append("ordered")
            i += 1
            continue
        if kind in ("bullet_list_close", "ordered_list_close"):
            if list_stack:
                list_stack.pop()
            i += 1
            continue
        if kind in ("list_item_open", "list_item_close"):
            i += 1
            continue

        if kind in ("fence", "code_block"):
            _emit_code_block(document, token.content)
            i += 1
            continue

        if kind == "hr":
            document.add_paragraph("—" * 24)
            i += 1
            continue

        if kind == "table_open":
            i = _emit_table(document, tokens, i)
            continue

        # blockquote_open/close, html_block, and any unhandled wrappers: skip the
        # marker; their inner inline/paragraph tokens are emitted by the rules above.
        i += 1


def _list_style(kind: str, depth: int) -> str:
    """Map a list kind + nesting depth to a Word built-in list style name."""
    base = "List Bullet" if kind == "bullet" else "List Number"
    if depth <= 1:
        return base
    return f"{base} {min(depth, 3)}"


def _emit_inline(paragraph, inline_token) -> None:
    if inline_token is None or inline_token.type != "inline":
        return
    bold = italic = strike = False
    for child in inline_token.children or []:
        ctype = child.type
        if ctype == "text":
            run = paragraph.add_run(child.content)
            if bold:
                run.bold = True
            if italic:
                run.italic = True
            if strike:
                run.font.strike = True
        elif ctype == "code_inline":
            run = paragraph.add_run(child.content)
            run.font.name = _CODE_FONT
        elif ctype == "strong_open":
            bold = True
        elif ctype == "strong_close":
            bold = False
        elif ctype == "em_open":
            italic = True
        elif ctype == "em_close":
            italic = False
        elif ctype in ("s_open",):
            strike = True
        elif ctype in ("s_close",):
            strike = False
        elif ctype == "softbreak":
            paragraph.add_run(" ")
        elif ctype == "hardbreak":
            paragraph.add_run().add_break()
        elif ctype == "image":
            alt = child.content or (child.attrs.get("alt") if hasattr(child, "attrs") else "") or "image"
            paragraph.add_run(f"[image: {alt}]")
        elif ctype in ("link_open", "link_close"):
            # Render link text inline; the URL itself is dropped to keep the
            # document clean (text content arrives via the text children).
            continue
        elif child.content:
            paragraph.add_run(child.content)


def _emit_code_block(document, content: str) -> None:
    text = content.rstrip("\n")
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    run.font.name = _CODE_FONT


def _emit_table(document, tokens, start: int) -> int:
    """Build a Word table from a markdown-it table token run. Returns next index."""
    rows: list[list] = []
    current: list | None = None
    i = start + 1
    n = len(tokens)
    while i < n and tokens[i].type != "table_close":
        ttype = tokens[i].type
        if ttype == "tr_open":
            current = []
        elif ttype == "tr_close":
            if current is not None:
                rows.append(current)
            current = None
        elif ttype in ("th_open", "td_open") and current is not None:
            inline = tokens[i + 1] if i + 1 < n and tokens[i + 1].type == "inline" else None
            current.append(inline)
        i += 1

    if rows:
        ncols = max(len(row) for row in rows)
        table = document.add_table(rows=0, cols=ncols)
        try:
            table.style = "Table Grid"
        except KeyError:
            pass
        for row_index, row in enumerate(rows):
            cells = table.add_row().cells
            for col in range(ncols):
                inline = row[col] if col < len(row) else None
                paragraph = cells[col].paragraphs[0]
                _emit_inline(paragraph, inline)
                if row_index == 0:
                    for run in paragraph.runs:
                        run.bold = True

    return i + 1  # advance past table_close
