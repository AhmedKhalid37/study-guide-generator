"""Deterministic, advisory guide-lint core (Slice 19).

This module inspects generated guide Markdown for *structural and rendering-risk*
issues and produces a JSON-serializable report of findings. It is purely
**advisory**: it never mutates the input, never fails generation, and is not
wired into jobs, artifacts, the API, ``validation.json``, the frontend, or the
UI. It is the structural sibling of :mod:`pipeline.math_verifier` (numeric
correctness) and is deliberately separate from :mod:`pipeline.math_validator`
(KaTeX *render* validation, which this module reuses but never changes).

Rules implemented (Slice 19):
  1. ``empty_heading``          — a heading with no body before the next heading.
  2. broken-table family        — ``separator_without_header``,
                                  ``header_separator_mismatch``,
                                  ``malformed_separator``, ``body_row_mismatch``.
  3. ``unbalanced_math``        — unbalanced ``$…$`` / ``$$…$$`` / ``\\(…\\)`` /
                                  ``\\[…\\]`` delimiters.
  4. ``katex_render`` / ``katex_skipped`` — reuse the existing Node/KaTeX bridge
                                  (``scripts/validate_math.js`` via
                                  :func:`pipeline.math_validator.validate`);
                                  degrade to an info finding when Node/KaTeX is
                                  unavailable, never crash.
  5. ``missing_section``        — an ``expected_sections`` entry absent from the
                                  document headings (normalized match).

Markdown safety: fenced code blocks are ignored for heading/table/math checks,
inline code spans are ignored for math checks, the input is never mutated, and no
HTML is ever produced or rendered.

Severities: ``error`` (definite render break), ``warning`` (likely problem /
ambiguous), ``info`` (advisory / skipped check).

Public API:
    lint_guide_markdown(markdown, *, source_name=None, expected_sections=None,
                        run_katex=True) -> GuideLintReport

Optional CLI:
    python -m pipeline.guide_lint path/to/file.md
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ── Tunables / bounds ───────────────────────────────────────────────────────

VERSION = 1

MAX_TEXT_LEN = 200_000        # total input characters considered
MAX_FINDINGS = 2_000          # hard cap so a pathological doc cannot flood
KATEX_TIMEOUT_SECONDS = 30    # subprocess timeout for the Node/KaTeX bridge
EXCERPT_LEN = 160             # max excerpt length stored in a finding

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

_HEADING_RE = re.compile(r"^(#{1,6})(?=\s|$)(.*)$")


# ── Result dataclasses ──────────────────────────────────────────────────────

@dataclass
class LintFinding:
    id: str
    rule: str
    severity: str
    line: int
    message: str
    excerpt: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GuideLintReport:
    version: int
    source_name: str | None
    summary: dict
    findings: list[LintFinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "source_name": self.source_name,
            "summary": dict(self.summary),
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ── Small helpers ────────────────────────────────────────────────────────────

_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _truncate(text: str, limit: int = EXCERPT_LEN) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _code_mask(lines: list[str]) -> list[bool]:
    """Return a per-line mask that is True for fenced-code-block lines.

    The opening and closing fence delimiter lines are themselves masked. Only
    ``` / ~~~ fences are recognised (matching the rest of the pipeline); the
    closing marker must use the same fence character that opened it so a ~~~
    inside a ``` block does not close it early.
    """
    mask = [False] * len(lines)
    fence: str | None = None
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if fence is None:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                fence = stripped[0]
                mask[i] = True
        else:
            mask[i] = True
            if stripped.startswith(fence * 3):
                fence = None
    return mask


# ── Rule 1: empty headings ────────────────────────────────────────────────────

def _collect_headings(lines: list[str], code: list[bool]) -> list[tuple[int, int, str]]:
    """Return ``(line_index, level, text)`` for each ATX heading outside code."""
    headings: list[tuple[int, int, str]] = []
    for i, line in enumerate(lines):
        if code[i]:
            continue
        m = _HEADING_RE.match(line)
        if m:
            headings.append((i, len(m.group(1)), m.group(2).strip()))
    return headings


def _lint_empty_headings(
    lines: list[str],
    code: list[bool],
    headings: list[tuple[int, int, str]],
    add,
) -> None:
    n = len(lines)
    for k, (idx, level, _text) in enumerate(headings):
        if k + 1 < len(headings):
            next_idx, next_level = headings[k + 1][0], headings[k + 1][1]
        else:
            next_idx, next_level = n, None
        gap = lines[idx + 1:next_idx]
        if any(seg.strip() for seg in gap):
            continue  # has body content (paragraph/list/table/math/image/code)
        if next_level is not None and next_level > level:
            continue  # grouping heading whose body lives under a child heading
        add(
            "empty_heading",
            SEVERITY_WARNING,
            idx + 1,
            "Heading has no body content before the next heading.",
            lines[idx],
        )


# ── Rule 2: broken Markdown tables ────────────────────────────────────────────

_DASH_CELL_RE = re.compile(r"^:?-+:?$")


def _split_cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [cell.strip() for cell in s.split("|")]


def _is_dash_cell(cell: str) -> bool:
    return bool(_DASH_CELL_RE.match(cell.strip()))


def _is_sep_candidate(line: str) -> bool:
    """A row that *looks intended* as a table separator (has a dash cell)."""
    if "|" not in line:
        return False
    return any(_is_dash_cell(cell) for cell in _split_cells(line))


def _is_valid_separator(line: str) -> bool:
    if "|" not in line:
        return False
    cells = _split_cells(line)
    return bool(cells) and all(_is_dash_cell(cell) for cell in cells)


def _lint_tables(lines: list[str], code: list[bool], add) -> None:
    n = len(lines)
    i = 0
    while i < n:
        if code[i]:
            i += 1
            continue
        cur = lines[i]
        # A header is a pipe row that is not itself a separator candidate,
        # immediately followed by a separator-candidate row.
        if (
            "|" in cur
            and not _is_sep_candidate(cur)
            and i + 1 < n
            and not code[i + 1]
            and _is_sep_candidate(lines[i + 1])
        ):
            sep = lines[i + 1]
            header_cols = len(_split_cells(cur))
            if not _is_valid_separator(sep):
                add(
                    "malformed_separator",
                    SEVERITY_WARNING,
                    i + 2,
                    "Table separator row has malformed cells.",
                    sep,
                )
                # Skip the rest of this malformed pipe block to avoid noise.
                i += 2
                while i < n and not code[i] and lines[i].strip() and "|" in lines[i]:
                    i += 1
                continue
            sep_cols = len(_split_cells(sep))
            if header_cols != sep_cols:
                add(
                    "header_separator_mismatch",
                    SEVERITY_WARNING,
                    i + 2,
                    f"Table header has {header_cols} columns but the separator "
                    f"row has {sep_cols}.",
                    sep,
                )
            j = i + 2
            while (
                j < n
                and not code[j]
                and lines[j].strip()
                and "|" in lines[j]
                and not _is_sep_candidate(lines[j])
            ):
                body_cols = len(_split_cells(lines[j]))
                if body_cols != header_cols:
                    add(
                        "body_row_mismatch",
                        SEVERITY_WARNING,
                        j + 1,
                        f"Table row has {body_cols} columns but the header has "
                        f"{header_cols}.",
                        lines[j],
                    )
                j += 1
            i = j
            continue
        if _is_valid_separator(cur):
            add(
                "separator_without_header",
                SEVERITY_WARNING,
                i + 1,
                "Table separator row has no header row directly above it.",
                cur,
            )
        i += 1


# ── Rule 3: unbalanced math delimiters ────────────────────────────────────────

def _scrub_for_math(lines: list[str], code: list[bool]) -> list[str]:
    """Blank fenced-code lines and inline-code spans so math counts ignore them."""
    out: list[str] = []
    for i, line in enumerate(lines):
        if code[i]:
            out.append("")
        else:
            out.append(_INLINE_CODE_RE.sub(" ", line))
    return out


def _lint_dollar_math(scrub: list[str], add) -> None:
    # Pass 1: $$ display delimiters. Blank each $$ so the inline pass ignores it.
    display_open: int | None = None
    working: list[str] = []
    for ln, text in enumerate(scrub, start=1):
        t = text.replace("\\$", "  ")
        pos = 0
        while True:
            k = t.find("$$", pos)
            if k < 0:
                break
            display_open = None if display_open is not None else ln
            t = t[:k] + "  " + t[k + 2:]
            pos = k + 2
        working.append(t)
    if display_open is not None:
        add(
            "unbalanced_math",
            SEVERITY_ERROR,
            display_open,
            "Unbalanced '$$' display-math delimiter.",
            scrub[display_open - 1] if display_open - 1 < len(scrub) else "$$",
        )

    # Pass 2: single $ inline delimiters (ambiguous with currency → warning).
    inline_open: int | None = None
    for ln, t in enumerate(working, start=1):
        pos = 0
        while True:
            k = t.find("$", pos)
            if k < 0:
                break
            inline_open = None if inline_open is not None else ln
            pos = k + 1
    if inline_open is not None:
        add(
            "unbalanced_math",
            SEVERITY_WARNING,
            inline_open,
            "Unbalanced '$' inline-math delimiter (or an unescaped currency '$').",
            scrub[inline_open - 1] if inline_open - 1 < len(scrub) else "$",
        )


def _lint_paired_math(scrub: list[str], open_tok: str, close_tok: str, label: str, add) -> None:
    pattern = re.compile(re.escape(open_tok) + "|" + re.escape(close_tok))
    depth = 0
    open_line: int | None = None
    for ln, text in enumerate(scrub, start=1):
        for m in pattern.finditer(text):
            if m.group() == open_tok:
                depth += 1
                if depth == 1:
                    open_line = ln
            else:
                if depth > 0:
                    depth -= 1
                else:
                    add(
                        "unbalanced_math",
                        SEVERITY_ERROR,
                        ln,
                        f"Found '{close_tok}' with no matching '{open_tok}' ({label}).",
                        text,
                    )
    if depth > 0 and open_line is not None:
        add(
            "unbalanced_math",
            SEVERITY_ERROR,
            open_line,
            f"Unbalanced '{open_tok}' delimiter with no matching '{close_tok}' ({label}).",
            scrub[open_line - 1],
        )


def _lint_math_delimiters(lines: list[str], code: list[bool], add) -> None:
    scrub = _scrub_for_math(lines, code)
    _lint_dollar_math(scrub, add)
    _lint_paired_math(scrub, "\\(", "\\)", "inline LaTeX", add)
    _lint_paired_math(scrub, "\\[", "\\]", "display LaTeX", add)


# ── Rule 4: KaTeX / render validation bridge ──────────────────────────────────

def _find_expr_line(lines: list[str], expr: str) -> int:
    needle = expr.strip().splitlines()[0].strip() if expr.strip() else ""
    needle = needle[:40]
    if not needle:
        return 0
    for i, line in enumerate(lines, start=1):
        if needle in line:
            return i
    return 0


def _lint_katex(markdown: str, lines: list[str], add) -> None:
    """Reuse the existing Node/KaTeX bridge; degrade to info if unavailable."""
    tmp_path: str | None = None
    try:
        from pipeline.math_validator import validate  # local import: optional path

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(markdown)
            tmp_path = handle.name

        result = validate(Path(tmp_path))

        if "skipped" in (result.raw_stderr or "").lower():
            add(
                "katex_skipped",
                SEVERITY_INFO,
                0,
                "KaTeX/Node validation unavailable; render check skipped.",
                "",
            )
            return

        if result.ok:
            return

        if not result.errors:
            # Non-zero exit with no parsed errors (e.g. katex module missing in
            # the Node runtime). Treat as a skipped check, not a guide problem.
            add(
                "katex_skipped",
                SEVERITY_INFO,
                0,
                "KaTeX/Node validation could not run; render check skipped.",
                "",
            )
            return

        for err in result.errors:
            add(
                "katex_render",
                SEVERITY_ERROR,
                _find_expr_line(lines, err.expr),
                f"KaTeX render error: {err.message.strip()}",
                err.expr,
            )
    except Exception:  # noqa: BLE001 — advisory check must never crash linting
        add(
            "katex_skipped",
            SEVERITY_INFO,
            0,
            "KaTeX/Node validation raised an error; render check skipped.",
            "",
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ── Rule 5: expected / required sections ───────────────────────────────────────

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _normalize_heading(text: str) -> str:
    return _NON_ALNUM_RE.sub(" ", text.lower()).strip()


def _lint_expected_sections(
    expected_sections: list[str] | None,
    headings: list[tuple[int, int, str]],
    add,
) -> None:
    if not expected_sections:
        return
    present = [_normalize_heading(text) for (_i, _lvl, text) in headings]
    present = [p for p in present if p]
    for raw in expected_sections:
        if not isinstance(raw, str):
            continue
        want = _normalize_heading(raw)
        if not want:
            continue
        found = False
        for have in present:
            if have == want:
                found = True
                break
            if len(want) >= 3 and (want in have or have in want):
                found = True
                break
        if not found:
            add(
                "missing_section",
                SEVERITY_WARNING,
                0,
                f"Expected section '{raw.strip()}' was not found among the headings.",
                raw.strip(),
            )


# ── Public API ─────────────────────────────────────────────────────────────────

def lint_guide_markdown(
    markdown: str,
    *,
    source_name: str | None = None,
    expected_sections: list[str] | None = None,
    run_katex: bool = True,
) -> GuideLintReport:
    """Lint *markdown* for structural / rendering-risk issues (advisory only).

    The input is never mutated. Findings are conservative: ambiguous Markdown is
    reported as a ``warning`` rather than an ``error``. The KaTeX render check is
    optional and degrades to an info finding when Node/KaTeX is unavailable. This
    function never raises on bad input and never affects guide generation.
    """
    raw: list[tuple[str, str, int, str, str]] = []

    def add(rule: str, severity: str, line: int, message: str, excerpt: str) -> None:
        if len(raw) >= MAX_FINDINGS:
            return
        raw.append((rule, severity, line, message, _truncate(excerpt)))

    if not isinstance(markdown, str):
        markdown = ""
    body = markdown[:MAX_TEXT_LEN]
    lines = body.splitlines()
    code = _code_mask(lines)
    headings = _collect_headings(lines, code)

    _lint_empty_headings(lines, code, headings, add)
    _lint_tables(lines, code, add)
    _lint_math_delimiters(lines, code, add)
    _lint_expected_sections(expected_sections, headings, add)
    if run_katex:
        _lint_katex(body, lines, add)

    # Stable order: by line, then by original discovery order.
    ordered = sorted(enumerate(raw), key=lambda pair: (pair[1][2], pair[0]))
    findings: list[LintFinding] = []
    for new_index, (_orig, (rule, severity, line, message, excerpt)) in enumerate(
        ordered, start=1
    ):
        findings.append(
            LintFinding(
                id=f"lint_{new_index:04d}",
                rule=rule,
                severity=severity,
                line=line,
                message=message,
                excerpt=excerpt,
            )
        )

    summary = {
        "total": len(findings),
        SEVERITY_ERROR: sum(1 for f in findings if f.severity == SEVERITY_ERROR),
        SEVERITY_WARNING: sum(1 for f in findings if f.severity == SEVERITY_WARNING),
        SEVERITY_INFO: sum(1 for f in findings if f.severity == SEVERITY_INFO),
    }

    return GuideLintReport(
        version=VERSION,
        source_name=source_name,
        summary=summary,
        findings=findings,
    )


# ── Optional CLI ─────────────────────────────────────────────────────────────

def _main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m pipeline.guide_lint <path>", file=sys.stderr)
        return 2
    path = argv[0]
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read(MAX_TEXT_LEN + 1)
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 1
    report = lint_guide_markdown(text, source_name=path.rsplit("/", 1)[-1])
    print(report.to_json(indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main(sys.argv[1:]))
