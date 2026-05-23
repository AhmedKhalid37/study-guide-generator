from __future__ import annotations

import re

PLACEHOLDER = "\uE000MATHBLOCK{}\uE001"
DOLLAR_PLACEHOLDER = "\uE002DOLLARMATH{}\uE003"
DOLLAR_PLACEHOLDER_PREFIX = "\uE002DOLLARMATH"
BRACKET_PLACEHOLDER = "\uE004BRACKETMATH{}\uE005"
LINK_PLACEHOLDER = "\uE006LINK{}\uE007"

STRUCTURE_PREFIXES = (
    "#",
    "##",
    "###",
    "---",
    "|",
    "**Q",
    "**A",
    "Step",
    "Example",
    "Answer:",
    "For hidden layers",
    "Where",
    "where",
    "Worked example",
    "Common exam traps",
    "Mini cheat sheet",
    "Practice questions",
    "Question",
    "Final answer",
    "Exam hint",
    "Definition",
    "Plain English",
    "Memory hint",
)


def escape_currency(text: str) -> str:
    # Escape literal money signs before numbers so they do not become math delimiters.
    text = re.sub(r"(?<!\\)\$\s+(?=\d)", r"\\$ ", text)
    return re.sub(r"(?<!\\)\$(?=\d)", r"\\$", text)


def escape_bad_dollar_lines(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        if stripped == "$":
            lines.append(indent + r"\$")
            continue
        if re.match(r"^\$\s+[A-Za-z]", stripped):
            lines.append(indent + r"\$" + stripped[1:])
            continue
        lines.append(line)
    return "\n".join(lines)


def protect_existing_dollar_math(text: str) -> tuple[str, list[str]]:
    blocks: list[str] = []
    lines = text.splitlines(True)
    out: list[str] = []
    in_code = False
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code = not in_code
            out.append(line)
            i += 1
            continue

        if in_code:
            out.append(line)
            i += 1
            continue

        if stripped == "$":
            out.append(line.replace("$", r"\$", 1))
            i += 1
            continue

        if _is_single_line_display_math(stripped):
            expr = stripped[2:-2].strip()
            out.append(_store_dollar_block(blocks, "$$" + fix_math_inner(expr) + "$$") + _line_ending(line))
            i += 1
            continue

        if _is_broken_display_delimiter_line(stripped):
            line = _remove_leading_display_delimiter(line)
            line = _protect_latex_inline_math(line, blocks)
            out.append(_protect_inline_dollar_math(line, blocks))
            i += 1
            continue

        if stripped.startswith("$$"):
            collected = [line]
            j = i + 1
            found_close = False
            blocked_by_structure = False

            while j < len(lines):
                candidate = lines[j]
                candidate_stripped = candidate.strip()
                if candidate_stripped == "$$" or (
                    candidate_stripped.endswith("$$")
                    and not candidate_stripped.startswith("$$")
                ):
                    collected.append(candidate)
                    found_close = True
                    break
                if (
                    "$$" in candidate
                    and not candidate_stripped.startswith("$$")
                    and _split_display_close_with_prose(lines, j, collected)
                ):
                    found_close = True
                    break
                if _is_markdown_structure(candidate_stripped):
                    blocked_by_structure = True
                    break
                collected.append(candidate)
                j += 1

            if found_close and not blocked_by_structure:
                out.append(
                    _store_dollar_block(blocks, _normalize_display_block("".join(collected)))
                    + _line_ending(lines[j])
                )
                i = j + 1
                continue

            out.append(line.replace("$", r"\$", 1))
            i += 1
            continue

        line = _protect_latex_inline_math(line, blocks)
        out.append(_protect_inline_dollar_math(line, blocks))
        i += 1

    return "".join(out), blocks


def _protect_latex_inline_math(line: str, blocks: list[str]) -> str:
    return re.sub(
        r"\\\((.+?)\\\)",
        lambda match: _store_dollar_block(blocks, "$" + fix_math_inner(match.group(1)) + "$"),
        line,
    )


def _protect_inline_dollar_math(line: str, blocks: list[str]) -> str:
    line = re.sub(
        r"(?<!\\)\$\$([^\n$]+?)(?<!\\)\$\$",
        lambda match: _store_dollar_block(blocks, "$" + fix_math_inner(match.group(1)) + "$"),
        line,
    )

    out: list[str] = []
    i = 0
    in_code = False
    while i < len(line):
        ch = line[i]
        if ch == "`":
            in_code = not in_code
            out.append(ch)
            i += 1
            continue
        if ch != "$" or in_code or _is_escaped(line, i):
            out.append(ch)
            i += 1
            continue

        end = _find_inline_dollar_close(line, i + 1)
        if end is None:
            out.append(ch)
            i += 1
            continue

        expr = line[i + 1:end].strip()
        if expr and looks_math(expr) and not _looks_like_prose_math_span(expr):
            out.append(_store_dollar_block(blocks, "$" + fix_math_inner(expr) + "$"))
            i = end + 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def _find_inline_dollar_close(line: str, start: int) -> int | None:
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


def _normalize_display_block(block: str) -> str:
    stripped = block.strip()
    if stripped.startswith("$$") and stripped.endswith("$$"):
        return "$$\n" + fix_math_inner(stripped[2:-2]) + "\n$$"
    return block


def restore_dollar_blocks(text: str, blocks: list[str]) -> str:
    for i, block in enumerate(blocks):
        text = text.replace(DOLLAR_PLACEHOLDER.format(i), block)
    return text


def _store_dollar_block(blocks: list[str], block: str) -> str:
    idx = len(blocks)
    blocks.append(block)
    return DOLLAR_PLACEHOLDER.format(idx)


def _is_single_line_display_math(stripped: str) -> bool:
    return stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4


def _line_ending(line: str) -> str:
    return "\n" if line.endswith("\n") else ""


def _is_markdown_structure(stripped: str) -> bool:
    if not stripped:
        return False
    return any(stripped.startswith(prefix) for prefix in STRUCTURE_PREFIXES)


def _is_broken_display_delimiter_line(stripped: str) -> bool:
    if not stripped.startswith("$$") or stripped == "$$" or _is_single_line_display_math(stripped):
        return False
    rest = stripped[2:].strip()
    return bool(rest) and (_is_markdown_structure(rest) or not looks_math(rest))


def _remove_leading_display_delimiter(line: str) -> str:
    before, _delimiter, after = line.partition("$$")
    return before + after.lstrip()


def _split_display_close_with_prose(lines: list[str], index: int, collected: list[str]) -> bool:
    candidate = lines[index]
    before, _delimiter, after = candidate.partition("$$")
    if not before.strip():
        return False

    collected.append(before.rstrip() + _line_ending(candidate))
    prose = after.lstrip()
    if prose:
        lines.insert(index + 1, prose)
    return True


def fix_math_inner(s: str) -> str:
    s = s.strip()
    s = normalize_unicode_math(s)

    # Preserve escaped literal money signs.
    s = re.sub(r"(?<!\\)%", r"\\%", s)

    # Avoid raw | inside table math. In LaTeX math, \mid is the right symbol.
    s = s.replace("|", r"\mid ")

    # Common artifact: =,_5C_2 or ,_nC_r from copied combinatorics notation.
    s = s.replace(",_", "{}_")

    # Leading underscore has no base in LaTeX. Use an empty base.
    s = re.sub(r"(^|[=\s({\[])(_(?:\d+|[A-Za-z]))", r"\1{}\2", s)

    # Safety: if \mid was inserted before a word, add a required space.
    # Example: \midB -> \mid B, \midmale -> \mid male
    s = re.sub(r"\\mid(?=[A-Za-z])", r"\\mid ", s)

    return s


def normalize_unicode_math(s: str) -> str:
    return s.replace("μ", r"\mu").replace("σ", r"\sigma")


def looks_math(s: str) -> bool:
    t = s.strip()
    if not t:
        return False

    # Very long English parentheticals are usually not math.
    if len(t.split()) >= 5 and "\\" not in t and not re.search(r"[=^_<>+\-*/]", t):
        return False

    # Obvious LaTeX/math markers.
    if "\\" in t:
        return True
    if re.fullmatch(r"[A-Za-z]+\'\([A-Za-z0-9_{}^\\()]+(?:\^\{[^}]+\})?\)", t):
        return True
    if re.search(r"[μσ]", t):
        return True
    if re.search(r"[=^_<>+\-*/≤≥≈∑√]", t):
        return True
    if re.fullmatch(r"-?\d+(?:\.\d+)?", t):
        return True
    if re.fullmatch(r"[A-Za-z]", t):
        return True
    if re.fullmatch(r"(?:npq|np|pq|n|p|q|r|x|X|z|Z|mu|sigma|SD|Var|E)", t):
        return True
    if re.fullmatch(r"[\d.,\s]+", t) and "," in t:
        return True
    if re.search(r"\bP\s*\([^)]", t):
        return True
    if re.search(r"\bE\s*\([^)]", t):
        return True
    if re.search(r"\b[A-Za-z]\s*\([^)]", t) and re.search(r"\d|=|\\", t):
        return True
    return False


def _looks_like_prose_math_span(s: str) -> bool:
    t = re.sub(r"\s+", " ", s.strip().lower())
    if not t:
        return False
    prose_markers = (
        "when applying",
        "because",
        "through",
        "function",
        "layer",
        "where",
        "answer",
        "example",
    )
    if any(marker in t for marker in prose_markers):
        return True
    words = re.findall(r"[A-Za-z]{3,}", t)
    math_tokens = re.findall(r"\\|[=^_<>+\-*/≤≥≈∑√]|\b[xyzijk]\b|\d", t)
    return len(words) >= 4 and len(words) > len(math_tokens) + 2


def repair_malformed_derivative_notation(text: str) -> str:
    text = re.sub(
        r"\bf'\s*\$([^$\n]+?)\$",
        lambda match: f"$f'({match.group(1).strip()})$",
        text,
    )
    text = re.sub(
        r"\bf'\s*([A-Za-z](?:_[A-Za-z0-9]+|\^\{[^}]+\})?)\$(?=\s+(?:when applying|when|because|through)\b)",
        lambda match: f"$f'({match.group(1)})$",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\blayer\s+([A-Za-z])\$(?=([.,;:)]|\s|$))",
        r"layer $\1$\2",
        text,
        flags=re.IGNORECASE,
    )
    return text


def convert_inline_math_line(line: str) -> str:
    out: list[str] = []
    i = 0
    n = len(line)

    while i < n:
        ch = line[i]
        if ch == "`":
            end = line.find("`", i + 1)
            if end == -1:
                out.append(ch)
                i += 1
            else:
                out.append(line[i : end + 1])
                i = end + 1
            continue

        if ch != "(":
            out.append(ch)
            i += 1
            continue

        depth = 0
        j = i
        while j < n:
            if line[j] == "(":
                depth += 1
            elif line[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1

        if j >= n or depth != 0:
            out.append(ch)
            i += 1
            continue

        inner = line[i + 1:j]
        if (
            DOLLAR_PLACEHOLDER_PREFIX in inner
            or "$" in inner
            or r"\(" in inner
            or r"\)" in inner
        ):
            out.append(ch)
            i += 1
            continue
        if looks_math(inner):
            out.append("$" + fix_math_inner(inner) + "$")
            i = j + 1
        else:
            out.append(ch)
            i += 1

    return "".join(out)


def protect_and_convert_display_math(text: str) -> tuple[str, list[str]]:
    blocks: list[str] = []
    lines = text.splitlines(True)
    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.strip() == "[":
            j = i + 1
            content: list[str] = []

            # Only allow short display-math blocks.
            # This prevents one bad [ from swallowing half the chapter.
            while j < len(lines) and j <= i + 12:
                if lines[j].strip() == "]":
                    break
                content.append(lines[j])
                j += 1

            if j < len(lines) and j <= i + 12 and lines[j].strip() == "]":
                inner = "".join(content).strip()

                has_markdown_structure = any(
                    x.lstrip().startswith(("#", "|", "---", "* ", "- "))
                    or _is_markdown_structure(x.strip())
                    for x in content
                )

                looks_like_formula = bool(
                    re.search(
                        r"\\|[=^_<>+\-*/≤≥≈∑√]|\bP\s*\(|\bZ\b|\bX\b|\d",
                        inner,
                    )
                )

                if inner and looks_like_formula and not has_markdown_structure:
                    idx = len(blocks)
                    blocks.append("\n\n$$\n" + fix_math_inner(inner) + "\n$$\n\n")
                    out.append(PLACEHOLDER.format(idx))
                    i = j + 1
                    continue

        out.append(line)
        i += 1

    return "".join(out), blocks


def protect_one_line_bracket_math(text: str) -> tuple[str, list[str]]:
    blocks: list[str] = []
    lines: list[str] = []
    in_code = False

    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            lines.append(line)
            continue
        if in_code:
            lines.append(line)
            continue

        match = re.fullmatch(r"(\s*)\[(.+?)\](\s*)", line)
        if not match:
            lines.append(line)
            continue

        inner = match.group(2).strip()
        if _looks_like_markdown_link(line) or not _looks_like_bracket_formula(inner):
            lines.append(line)
            continue

        idx = len(blocks)
        blocks.append("\n\n$$\n" + fix_math_inner(inner) + "\n$$\n\n")
        lines.append(BRACKET_PLACEHOLDER.format(idx))

    return "\n".join(lines), blocks


def restore_bracket_blocks(text: str, blocks: list[str]) -> str:
    for i, block in enumerate(blocks):
        text = text.replace(BRACKET_PLACEHOLDER.format(i), block)
    return text


def protect_markdown_links(text: str) -> tuple[str, list[str]]:
    blocks: list[str] = []

    def replace(match: re.Match) -> str:
        idx = len(blocks)
        blocks.append(match.group(0))
        return LINK_PLACEHOLDER.format(idx)

    return re.sub(r"\[[^\]\n]+\]\([^) \n]+(?:\s+\"[^\"]+\")?\)", replace, text), blocks


def restore_markdown_links(text: str, blocks: list[str]) -> str:
    for i, block in enumerate(blocks):
        text = text.replace(LINK_PLACEHOLDER.format(i), block)
    return text


def _looks_like_markdown_link(line: str) -> bool:
    return bool(re.search(r"\[[^\]]+\]\([^)]+\)", line))


def _looks_like_bracket_formula(inner: str) -> bool:
    if not inner:
        return False
    if re.search(r"\\(?:frac|mu|sigma|text|cap|mid)\b", inner):
        return True
    if re.search(r"[=<>^_]", inner):
        return True
    if re.search(r"\\(?:cap|mid)\b", inner):
        return True
    if re.search(r"\bP\s*\([^)]", inner):
        return True
    return False


def restore_blocks(text: str, blocks: list[str]) -> str:
    for i, block in enumerate(blocks):
        text = text.replace(PLACEHOLDER.format(i), block)
    return text


def merge_bare_probability_notation(text: str) -> str:
    # If a bare P(X) became P$X$, merge it into $P(X)$.
    return re.sub(r"\b([PE])\$([^$]+)\$", r"$\1(\2)$", text)


def sanitize_markdown_math(text: str) -> str:
    text = repair_malformed_derivative_notation(text)
    text, dollar_blocks = protect_existing_dollar_math(text)
    text, bracket_blocks = protect_one_line_bracket_math(text)
    text, link_blocks = protect_markdown_links(text)
    text = escape_currency(text)
    text = escape_bad_dollar_lines(text)
    protected, blocks = protect_and_convert_display_math(text)

    lines = []
    in_code = False
    for line in protected.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            lines.append(line)
            continue
        if in_code:
            lines.append(line)
            continue
        lines.append(convert_inline_math_line(line))

    out = "\n".join(lines)
    out = merge_bare_probability_notation(out)
    out = restore_blocks(out, blocks)
    out = restore_bracket_blocks(out, bracket_blocks)
    out = restore_dollar_blocks(out, dollar_blocks)
    out = restore_markdown_links(out, link_blocks)

    out = out.replace("ESCAPED_DOLLAR", r"\$")
    out = out.replace("DISPLAY_MATH_BLOCK", "")

    # Normalize huge blank spaces while keeping display math readable.
    out = re.sub(r"\n{4,}", "\n\n\n", out)
    return out.strip() + "\n"


def sanitize(text: str) -> str:
    return sanitize_markdown_math(text)
