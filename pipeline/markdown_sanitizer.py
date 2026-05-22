from __future__ import annotations

import re

PLACEHOLDER = "\uE000MATHBLOCK{}\uE001"


def escape_currency(text: str) -> str:
    # Escape literal money signs before numbers so they do not become math delimiters.
    return re.sub(r"(?<!\\)\$(?=\d)", r"\\$", text)


def fix_math_inner(s: str) -> str:
    s = s.strip()

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
    if re.search(r"[=^_<>+\-*/≤≥≈∑√]", t):
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


def convert_inline_math_line(line: str) -> str:
    out: list[str] = []
    i = 0
    n = len(line)

    while i < n:
        ch = line[i]
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


def restore_blocks(text: str, blocks: list[str]) -> str:
    for i, block in enumerate(blocks):
        text = text.replace(PLACEHOLDER.format(i), block)
    return text


def merge_bare_probability_notation(text: str) -> str:
    # If a bare P(X) became P$X$, merge it into $P(X)$.
    return re.sub(r"\b([PE])\$([^$]+)\$", r"$\1(\2)$", text)


def sanitize_markdown_math(text: str) -> str:
    text = escape_currency(text)
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

    # Normalize huge blank spaces while keeping display math readable.
    out = re.sub(r"\n{4,}", "\n\n\n", out)
    return out.strip() + "\n"


def sanitize(text: str) -> str:
    return sanitize_markdown_math(text)
