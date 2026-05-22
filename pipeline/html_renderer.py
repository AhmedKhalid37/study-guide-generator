from __future__ import annotations

import html
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt

BASE_DIR = Path(__file__).resolve().parents[1]
THEMES_DIR = BASE_DIR / "themes"
KATEX_CSS = BASE_DIR / "node_modules" / "katex" / "dist" / "katex.min.css"

PLACEHOLDER = "\uE100KATEX{}\uE101"


@dataclass(frozen=True)
class MathExpression:
    expr: str
    display_mode: bool


def render_markdown_file(
    markdown_path: Path,
    *,
    theme: str = "claude_clean",
    strict_math: bool = True,
) -> str:
    markdown = markdown_path.read_text(encoding="utf-8", errors="replace")
    title = _title_from_markdown(markdown) or markdown_path.stem.replace("_", " ").title()
    return render_markdown(markdown, title=title, theme=theme, strict_math=strict_math)


def render_markdown(
    markdown: str,
    *,
    title: str,
    theme: str = "claude_clean",
    strict_math: bool = True,
) -> str:
    protected, expressions = _extract_math(markdown)
    rendered_math = _render_katex(expressions, strict_math=strict_math)
    body = _markdown_to_html(protected)

    for index, rendered in enumerate(rendered_math):
        body = body.replace(PLACEHOLDER.format(index), rendered)

    css = _load_css(theme)
    return _document(title=title, body=body, css=css)


def _markdown_to_html(markdown: str) -> str:
    renderer = (
        MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": False})
        .enable("table")
        .enable("strikethrough")
    )
    return renderer.render(markdown)


def _extract_math(markdown: str) -> tuple[str, list[MathExpression]]:
    expressions: list[MathExpression] = []
    output: list[str] = []
    lines = markdown.splitlines(keepends=True)
    in_fence = False
    i = 0

    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            output.append(line)
            i += 1
            continue

        if in_fence:
            output.append(line)
            i += 1
            continue

        stripped = line.strip()
        if stripped.startswith("$$"):
            block_lines: list[str] = []
            after_open = stripped[2:]
            if after_open.endswith("$$") and len(after_open) > 2:
                expr = after_open[:-2].strip()
                output.append(_add_math(expressions, expr, display_mode=True) + "\n")
                i += 1
                continue

            if after_open:
                block_lines.append(after_open)
            i += 1
            while i < len(lines):
                candidate = lines[i]
                candidate_stripped = candidate.strip()
                if candidate_stripped.endswith("$$"):
                    before_close = candidate_stripped[:-2]
                    if before_close:
                        block_lines.append(before_close)
                    i += 1
                    break
                block_lines.append(candidate.rstrip("\n"))
                i += 1
            expr = "\n".join(block_lines).strip()
            output.append(_add_math(expressions, expr, display_mode=True) + "\n")
            continue

        output.append(_replace_inline_math(line, expressions))
        i += 1

    return "".join(output), expressions


def _replace_inline_math(line: str, expressions: list[MathExpression]) -> str:
    output: list[str] = []
    i = 0
    in_code = False

    while i < len(line):
        char = line[i]
        if char == "`":
            in_code = not in_code
            output.append(char)
            i += 1
            continue

        if char != "$" or in_code or _is_escaped(line, i):
            output.append(char)
            i += 1
            continue

        end = _find_closing_dollar(line, i + 1)
        if end is None:
            output.append(char)
            i += 1
            continue

        expr = line[i + 1:end].strip()
        if not expr:
            output.append(char)
            i += 1
            continue

        output.append(_add_math(expressions, expr, display_mode=False))
        i = end + 1

    return "".join(output)


def _find_closing_dollar(line: str, start: int) -> int | None:
    for i in range(start, len(line)):
        if line[i] == "$" and not _is_escaped(line, i):
            return i
    return None


def _is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    i = index - 1
    while i >= 0 and text[i] == "\\":
        backslashes += 1
        i -= 1
    return backslashes % 2 == 1


def _add_math(expressions: list[MathExpression], expr: str, *, display_mode: bool) -> str:
    index = len(expressions)
    expressions.append(MathExpression(expr=_normalize_math(expr), display_mode=display_mode))
    return PLACEHOLDER.format(index)


def _normalize_math(expr: str) -> str:
    return expr.replace("μ", r"\mu").replace("σ", r"\sigma")


def _render_katex(expressions: list[MathExpression], *, strict_math: bool = True) -> list[str]:
    if not expressions:
        return []

    payload = [
        {
            "expr": item.expr,
            "displayMode": item.display_mode,
            "throwOnError": strict_math,
        }
        for item in expressions
    ]
    script = r"""
const fs = require("fs");
const katex = require("katex");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const output = input.map((item) => {
    try {
    return {
      ok: true,
      html: katex.renderToString(item.expr, {
        displayMode: item.displayMode,
        throwOnError: item.throwOnError,
        strict: false
      })
    };
  } catch (error) {
    return {
      ok: false,
      expr: item.expr,
      displayMode: item.displayMode,
      error: error.message
    };
  }
});
process.stdout.write(JSON.stringify(output));
"""
    proc = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        cwd=BASE_DIR,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "KaTeX rendering failed while invoking Node.\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )

    try:
        rendered = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "KaTeX renderer returned invalid JSON.\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        ) from exc

    errors = [item for item in rendered if not item.get("ok")]
    if errors:
        details = "\n".join(
            f"- {'display' if item.get('displayMode') else 'inline'}: "
            f"{item.get('expr')}\n  {item.get('error')}"
            for item in errors
        )
        raise ValueError(f"KaTeX could not render {len(errors)} expression(s):\n{details}")

    return [item["html"] for item in rendered]


def _load_css(theme: str) -> str:
    theme_path = THEMES_DIR / f"{theme}.css"
    if not theme_path.exists():
        raise FileNotFoundError(f"Theme not found: {theme_path}")

    parts = []
    if KATEX_CSS.exists():
        parts.append(KATEX_CSS.read_text(encoding="utf-8"))
    else:
        parts.append("/* KaTeX CSS not found; math HTML will render without KaTeX styling. */")
    parts.append(theme_path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def _document(*, title: str, body: str, css: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
{css}
  </style>
</head>
<body>
  <main class="guide">
{body}
  </main>
</body>
</html>
"""


def _title_from_markdown(markdown: str) -> str | None:
    for line in markdown.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return match.group(1)
    return None
