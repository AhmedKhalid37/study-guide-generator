"""Deterministic, safe numeric math-correctness verifier (Slice 18 core).

This module inspects generated guide Markdown / plain text and checks *simple
numeric math claims* such as ``2 + 3 = 5`` or ``exp(1.43) / (1 + exp(1.43)) ≈
0.806``. It produces a structured, JSON-serializable report with per-claim
verdicts: ``ok``, ``mismatch``, or ``unparseable``.

IMPORTANT — this is **not** ``pipeline/math_validator.py``. That module validates
math *rendering* (KaTeX syntax) via the node validator. This module checks
*numeric correctness* of the asserted values. The two concepts are intentionally
separate; do not conflate them.

Slice 18 is **pure core only**: this module is not wired into jobs, artifacts,
the API, the frontend, or ``validation.json``. It never writes files (apart from
the optional CLI printing to stdout) and never affects guide generation.

Safety model:
  * No ``eval``/``exec``; expressions are parsed with :mod:`ast` and walked with
    an explicit whitelist of node types, operators, functions, and constants.
  * No attribute access, no names besides whitelisted constants, no imports, no
    filesystem/network/process access.
  * Input length, expression length, token count, AST node count, and ``**``
    exponent magnitude are all bounded to avoid pathological work or hangs.
  * Every verifier exception is caught and downgraded to ``unparseable`` — the
    verifier never raises on bad input and never marks a claim ``mismatch`` when
    it merely failed to understand it.

Public API:
    verify_math_claims(text, *, source_name=None, ...) -> MathVerificationReport

Optional CLI:
    python -m pipeline.math_verifier path/to/file.md
"""
from __future__ import annotations

import ast
import json
import math
import operator
import re
import sys
from dataclasses import asdict, dataclass, field

# ── Tunables / bounds ───────────────────────────────────────────────────────

VERSION = 1

DEFAULT_TOLERANCE_ABS = 1e-6
DEFAULT_TOLERANCE_REL = 1e-3

MAX_TEXT_LEN = 200_000      # total input characters considered
MAX_LINE_LEN = 2_000        # lines longer than this are skipped (pathological)
MAX_CLAIMS = 5_000          # hard cap on extracted claims
MAX_EXPR_LEN = 200          # normalized expression characters
MAX_EXPR_TOKENS = 100       # rough token count in a normalized expression
MAX_EXPR_NODES = 120        # AST node count
MAX_POW_EXPONENT = 100      # reject huge exponents in ``a ** b``
MAX_POW_BASE = 1e6          # reject huge bases in ``a ** b``

STATUS_OK = "ok"
STATUS_MISMATCH = "mismatch"
STATUS_UNPARSEABLE = "unparseable"


# ── Result dataclasses ──────────────────────────────────────────────────────

@dataclass
class ClaimResult:
    id: str
    line: int
    text: str
    expression: str
    claimed: str
    computed: str | None
    status: str
    reason: str
    tolerance_abs: float
    tolerance_rel: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MathVerificationReport:
    version: int
    source_name: str | None
    summary: dict
    claims: list[ClaimResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "source_name": self.source_name,
            "summary": dict(self.summary),
            "claims": [claim.to_dict() for claim in self.claims],
        }

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ── Safe AST evaluator ──────────────────────────────────────────────────────

class _UnsafeExpression(Exception):
    """Raised when an expression contains something outside the whitelist."""


_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}

_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Small, explicit function whitelist. ``log`` accepts an optional base, matching
# ``math.log``; ``ln`` is an alias for natural log.
_ALLOWED_FUNCS = {
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "ln": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "abs": abs,
}

_ALLOWED_CONSTS = {
    "pi": math.pi,
    "e": math.e,
    "E": math.e,
    "tau": math.tau,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        # bool is a subclass of int; reject it and any non-numeric constant
        # (strings, bytes, None) so e.g. malicious string literals never slip in.
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise _UnsafeExpression("non-numeric constant")
        return float(node.value)

    if isinstance(node, ast.BinOp):
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise _UnsafeExpression("operator not allowed")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_POW_EXPONENT or abs(left) > MAX_POW_BASE:
                raise _UnsafeExpression("exponent magnitude too large")
        return op(left, right)

    if isinstance(node, ast.UnaryOp):
        op = _UNARYOPS.get(type(node.op))
        if op is None:
            raise _UnsafeExpression("unary operator not allowed")
        return op(_eval_node(node.operand))

    if isinstance(node, ast.Call):
        # Only direct calls to whitelisted bare-name functions. Anything with an
        # attribute target (``os.system``), keywords, *args, or starred args is
        # rejected before any evaluation happens.
        if not isinstance(node.func, ast.Name):
            raise _UnsafeExpression("call target not allowed")
        fn = _ALLOWED_FUNCS.get(node.func.id)
        if fn is None:
            raise _UnsafeExpression(f"unknown function {node.func.id}")
        if node.keywords:
            raise _UnsafeExpression("keyword arguments not allowed")
        if len(node.args) == 0 or len(node.args) > 2:
            raise _UnsafeExpression("bad argument count")
        args = [_eval_node(arg) for arg in node.args]
        return float(fn(*args))

    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_CONSTS:
            return _ALLOWED_CONSTS[node.id]
        raise _UnsafeExpression(f"name {node.id}")

    raise _UnsafeExpression(f"node {type(node).__name__} not allowed")


def _classify_unsafe(message: str) -> str:
    if message.startswith("unknown function"):
        return "unknown_function"
    if message.startswith("name "):
        return "unresolved_variable"
    if "exponent" in message:
        return "expression_too_complex"
    return "unsupported_syntax"


# ── Markdown / text cleaning ────────────────────────────────────────────────

_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

# Math wrappers, stripped longest-delimiter first so $$ wins over $.
_WRAPPER_PATTERNS = (
    re.compile(r"\$\$(.+?)\$\$", re.DOTALL),
    re.compile(r"\$(.+?)\$"),
    re.compile(r"\\\((.+?)\\\)"),
    re.compile(r"\\\[(.+?)\\\]"),
)


def _strip_inline_code(line: str) -> str:
    return _INLINE_CODE_RE.sub(" ", line)


def _strip_math_wrappers(line: str) -> str:
    for pattern in _WRAPPER_PATTERNS:
        line = pattern.sub(r" \1 ", line)
    return line


# ── Relation handling ───────────────────────────────────────────────────────

# After normalization a relation is either exact ``=`` or approximate ``≈``.
# The standalone ``=`` must not be part of ``==``, ``<=``, ``>=``, ``!=``, ``:=``.
_REL_RE = re.compile(r"(≈|(?<![<>=!:])=(?!=))")

_MATH_HINT_RE = re.compile(r"[0-9]|[+\-*/^×·÷√]")

# A single token that may legitimately appear in a numeric expression: a
# whitelisted function/constant name (word-boundaried so it never matches a
# fragment of a prose word), a number, an operator/grouping char, a LaTeX
# backslash command, or whitespace.
_EXPR_NAME = r"sqrt|exp|log10|log2|log|ln|sin|cos|tan|abs|pi|tau|e|E"
_EXPR_TOKEN = (
    r"(?:\b(?:" + _EXPR_NAME + r")\b"
    r"|\d+\.?\d*|\.\d+"
    r"|\\[A-Za-z]+"
    r"|[+\-*/^().,×·÷√−{}]"
    r"|\s)"
)
# Longest suffix of *segment* composed entirely of expression tokens.
_TRAILING_EXPR_RE = re.compile(r"(" + _EXPR_TOKEN + r"+)\s*$")


def _trailing_expression(segment: str) -> str:
    """Trim a prose lead-in, returning the trailing math expression.

    ``The sum is simple: 2 + 3`` → ``2 + 3``. The trim is only applied when the
    extracted run is bounded on the left by a non-word character (e.g. ``:`` or
    the start of the segment). When the run is glued to a word character — as in
    ``x + 2`` where ``x`` is a variable — the full segment is kept so it parses
    to an unresolved variable (``unparseable``) instead of silently dropping the
    variable and producing a false result.
    """
    match = _TRAILING_EXPR_RE.search(segment)
    if not match:
        return segment.strip()
    start = match.start(1)
    if start > 0:
        prev = segment[start - 1]
        if prev.isalnum() or prev == "_":
            return segment.strip()
    return match.group(1).strip()


def _normalize_relations(line: str) -> str:
    line = line.replace("\\approx", "≈").replace("\\to", "→")
    for token in ("≅", "≃", "~=", "→", "->"):
        line = line.replace(token, "≈")
    return line


def _looks_like_math(segment: str) -> bool:
    return bool(_MATH_HINT_RE.search(segment))


def _extract_pairs(line: str) -> list[tuple[str, str, str]]:
    """Return ``(left, op, right)`` triples for each relation in *line*.

    ``op`` is normalized to ``=`` (exact) or ``≈`` (approximate). A pair is only
    emitted when at least one side looks like math (contains a digit or math
    operator), which keeps ordinary prose containing ``=`` from being extracted.
    """
    line = _normalize_relations(line)
    matches = list(_REL_RE.finditer(line))
    if not matches:
        return []

    # Build the segments between operators along with the operator text.
    segments: list[str] = []
    ops: list[str] = []
    last = 0
    for m in matches:
        segments.append(line[last:m.start()])
        ops.append(m.group(0))
        last = m.end()
    segments.append(line[last:])

    pairs: list[tuple[str, str, str]] = []
    for i, op in enumerate(ops):
        left = segments[i].strip()
        right = segments[i + 1].strip()
        if not left or not right:
            continue
        if not (_looks_like_math(left) or _looks_like_math(right)):
            continue
        pairs.append((_trailing_expression(left), op, right))
    return pairs


# ── Number parsing ──────────────────────────────────────────────────────────

_LEADING_NUMBER_RE = re.compile(
    r"^\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+)?(?:[eE][+-]?\d+)?)"
)


def _parse_number(text: str) -> tuple[float | None, int]:
    """Parse the leading numeric literal of *text*.

    Returns ``(value, decimal_places)`` or ``(None, 0)`` when *text* does not
    begin with a number. Decimal places drive the rounding tolerance for
    approximate claims.
    """
    text = text.replace("−", "-")  # unicode minus
    m = _LEADING_NUMBER_RE.match(text)
    if not m:
        return None, 0
    raw = m.group(1)
    if raw in ("", "+", "-", ".", "+.", "-."):
        return None, 0
    cleaned = raw.replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None, 0
    mantissa = cleaned.split("e")[0].split("E")[0]
    decimals = len(mantissa.split(".")[1]) if "." in mantissa else 0
    return value, decimals


# ── Expression normalization ────────────────────────────────────────────────

_FRAC_RE = re.compile(r"\\(?:d|t)?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_SQRT_BRACE_RE = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
_SQRT_PAREN_RE = re.compile(r"√\s*\(([^()]*)\)")
_SQRT_NUM_RE = re.compile(r"√\s*([0-9.]+)")
_BACKSLASH_FUNC_RE = re.compile(r"\\(sqrt|exp|log|ln|sin|cos|tan)\b")
_THOUSANDS_RE = re.compile(r"(?<=\d),(?=\d\d\d(?:\D|$))")
_TOKEN_RE = re.compile(r"[A-Za-z_]\w*|\d+\.?\d*|\.\d+|\*\*|[+\-*/%^()]")


def _normalize_expr(expr: str) -> str:
    expr = expr.replace("−", "-")
    expr = expr.replace("\\left", "").replace("\\right", "")
    expr = expr.replace("\\cdot", "*").replace("\\times", "*")
    expr = expr.replace("×", "*").replace("·", "*").replace("÷", "/")
    expr = expr.replace("π", "pi")
    expr = _FRAC_RE.sub(r"((\1)/(\2))", expr)
    expr = _SQRT_BRACE_RE.sub(r"sqrt(\1)", expr)
    expr = _SQRT_PAREN_RE.sub(r"sqrt(\1)", expr)
    expr = _SQRT_NUM_RE.sub(r"sqrt(\1)", expr)
    expr = _BACKSLASH_FUNC_RE.sub(r"\1", expr)
    expr = _THOUSANDS_RE.sub("", expr)
    expr = expr.replace("^", "**")
    expr = expr.replace("{", "(").replace("}", ")")
    return expr.strip()


# ── Number formatting ───────────────────────────────────────────────────────

def _format_number(value: float) -> str:
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return "%.10g" % value


# ── Claim evaluation ────────────────────────────────────────────────────────

def _evaluate_claim(
    line_no: int,
    left_text: str,
    op: str,
    right_text: str,
    *,
    tolerance_abs: float,
    tolerance_rel: float,
) -> ClaimResult:
    approx = op == "≈"
    claim = ClaimResult(
        id="",
        line=line_no,
        text=f"{left_text} {op} {right_text}".strip(),
        expression=left_text,
        claimed=right_text,
        computed=None,
        status=STATUS_UNPARSEABLE,
        reason="",
        tolerance_abs=tolerance_abs,
        tolerance_rel=tolerance_rel,
    )

    claimed_val, claimed_decimals = _parse_number(right_text)
    if claimed_val is None:
        claim.reason = "non_numeric_claim"
        return claim

    expr_norm = _normalize_expr(left_text)
    if not expr_norm:
        claim.reason = "empty_expression"
        return claim
    if len(expr_norm) > MAX_EXPR_LEN:
        claim.reason = "expression_too_long"
        return claim
    if len(_TOKEN_RE.findall(expr_norm)) > MAX_EXPR_TOKENS:
        claim.reason = "too_many_tokens"
        return claim

    try:
        tree = ast.parse(expr_norm, mode="eval")
    except SyntaxError:
        claim.reason = "parse_error"
        return claim

    if sum(1 for _ in ast.walk(tree)) > MAX_EXPR_NODES:
        claim.reason = "expression_too_complex"
        return claim

    try:
        computed = _eval_node(tree)
    except _UnsafeExpression as exc:
        claim.reason = _classify_unsafe(str(exc))
        return claim
    except ZeroDivisionError:
        claim.reason = "division_by_zero"
        return claim
    except (ValueError, OverflowError, ArithmeticError):
        claim.reason = "math_domain_error"
        return claim
    except Exception:  # pragma: no cover - defensive catch-all, never mismatch
        claim.reason = "evaluation_error"
        return claim

    if not isinstance(computed, (int, float)) or not math.isfinite(computed):
        claim.reason = "non_finite_result"
        return claim

    computed = float(computed)
    claim.computed = _format_number(computed)

    diff = abs(computed - claimed_val)
    abs_ok = diff <= tolerance_abs
    rel_ok = diff <= tolerance_rel * abs(claimed_val)
    round_ok = False
    if approx:
        # An approximate value written to N decimals may legitimately differ by
        # up to one unit in the last place (chained-rounding slack), e.g.
        # exp(1.43)/(1+exp(1.43)) = 0.80690 vs a claimed 0.806. This keeps
        # rounded guide claims out of `mismatch` without admitting real errors.
        one_ulp = 10 ** (-claimed_decimals)
        round_ok = diff <= one_ulp + 1e-12

    if abs_ok or rel_ok or round_ok:
        claim.status = STATUS_OK
        claim.reason = "exact" if diff == 0 else "within_tolerance"
    else:
        claim.status = STATUS_MISMATCH
        claim.reason = "value_mismatch"
    return claim


# ── Public API ──────────────────────────────────────────────────────────────

def verify_math_claims(
    text: str,
    *,
    source_name: str | None = None,
    tolerance_abs: float = DEFAULT_TOLERANCE_ABS,
    tolerance_rel: float = DEFAULT_TOLERANCE_REL,
) -> MathVerificationReport:
    """Verify simple numeric math claims found in *text*.

    Conservative, line-based Tier-A extraction: fenced code blocks and inline
    code spans are skipped, simple math wrappers are unwrapped, and only claims
    of the form ``expression <relation> number`` are considered. Ambiguous
    claims are reported as ``unparseable`` rather than ``mismatch``.
    """
    claims: list[ClaimResult] = []

    if isinstance(text, str) and text:
        body = text[:MAX_TEXT_LEN]
        in_fence = False
        for line_no, raw_line in enumerate(body.splitlines(), start=1):
            stripped = raw_line.lstrip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if len(raw_line) > MAX_LINE_LEN:
                continue
            line = _strip_math_wrappers(_strip_inline_code(raw_line))
            for left, op, right in _extract_pairs(line):
                claims.append(
                    _evaluate_claim(
                        line_no,
                        left,
                        op,
                        right,
                        tolerance_abs=tolerance_abs,
                        tolerance_rel=tolerance_rel,
                    )
                )
                if len(claims) >= MAX_CLAIMS:
                    break
            if len(claims) >= MAX_CLAIMS:
                break

    for index, claim in enumerate(claims, start=1):
        claim.id = f"claim_{index:04d}"

    summary = {
        "total": len(claims),
        STATUS_OK: sum(1 for c in claims if c.status == STATUS_OK),
        STATUS_MISMATCH: sum(1 for c in claims if c.status == STATUS_MISMATCH),
        STATUS_UNPARSEABLE: sum(1 for c in claims if c.status == STATUS_UNPARSEABLE),
    }

    return MathVerificationReport(
        version=VERSION,
        source_name=source_name,
        summary=summary,
        claims=claims,
    )


# ── Optional CLI ────────────────────────────────────────────────────────────

def _main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m pipeline.math_verifier <path>", file=sys.stderr)
        return 2
    path = argv[0]
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read(MAX_TEXT_LEN + 1)
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 1
    report = verify_math_claims(text, source_name=path.rsplit("/", 1)[-1])
    print(report.to_json(indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main(sys.argv[1:]))
