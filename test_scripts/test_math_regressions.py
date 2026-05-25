from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.html_renderer import render_markdown
from pipeline.markdown_sanitizer import sanitize
from pipeline.math_validator import validate
from pipeline.prompt_loader import PROMPTS_DIR, load_prompt_template, render_prompt_template


def main() -> None:
    test_sanitizer_regressions()
    test_parenthetical_math_regressions()
    test_numeric_inline_math_and_money_regressions()
    test_broken_display_math_does_not_swallow_prose()
    test_derivative_inline_math_regressions()
    test_table_rows_keep_inline_math()
    test_square_bracket_display_math_regressions()
    test_evaluation_bar_mid_regressions()
    test_prompt_templates_render_with_latex_braces()
    test_html_renderer_inline_math()
    test_backtick_wrapped_math_is_unwrapped()
    test_math_pdf_fixture_renders_without_raw_latex()
    print("math regression tests passed")


def test_sanitizer_regressions() -> None:
    source = r"""# Sanitizer Cases

$μ$
$σ$
$1-\text{left area}$
$z=\frac{x-\mu}{\sigma}$
$P(X<900)$
$70,000 is money.
$ 70,000 is money.
$ Suppose:
$ This means:
[ z = \frac{x-\mu}{\sigma} ]
[ P(X < 900) = P(Z < -0.68) ]
[Google](https://google.com)
[important note]
"""
    clean = sanitize(source)

    assert "$\\mu$" in clean
    assert "$\\sigma$" in clean
    assert "$1-\\text{left area}$" in clean
    assert "$z=\\frac{x-\\mu}{\\sigma}$" in clean
    assert "$P(X<900)$" in clean
    assert "\\$70,000 is money." in clean
    assert "\\$ 70,000 is money." in clean
    assert "\\$ Suppose:" in clean
    assert "\\$ This means:" in clean
    assert "$$\nz = \\frac{x-\\mu}{\\sigma}\n$$" in clean
    assert "$$\nP(X < 900) = P(Z < -0.68)\n$$" in clean
    assert "[Google](https://google.com)" in clean
    assert "[important note]" in clean
    assert "$μ$" not in clean
    assert "$σ$" not in clean

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(clean)
        clean_path = Path(tmp.name)

    result = validate(clean_path)
    assert result.ok, result.to_json_dict()
    assert result.display_blocks == 2, result.to_json_dict()
    assert result.inline_formulas == 5, result.to_json_dict()


def test_parenthetical_math_regressions() -> None:
    source = r"""for (j=1) and (j=2)
from hidden node (j) to output (k)
from input (i) to hidden (j)
equal to (t_k)
one-hot (t=(1,0,0))
error_k· (w_{1k}^{[o]})
not (x_i)
this is important (remember this)
the flower (iris) has petals
see chapter (normal distribution)
[Google](https://google.com)
`code (x_i)`
There are two sets: for \(j=1\) and \(j=2\).
"""
    clean = sanitize(source)

    assert "for $j=1$ and $j=2$" in clean
    assert "from hidden node $j$ to output $k$" in clean
    assert "from input $i$ to hidden $j$" in clean
    assert "equal to $t_k$" in clean
    assert "one-hot $t=(1,0,0)$" in clean
    assert "error_k· $w_{1k}^{[o]}$" in clean
    assert "not $x_i$" in clean
    assert "this is important (remember this)" in clean
    assert "the flower (iris) has petals" in clean
    assert "see chapter (normal distribution)" in clean
    assert "[Google](https://google.com)" in clean
    assert "`code (x_i)`" in clean
    assert "There are two sets: for $j=1$ and $j=2$." in clean
    assert "$There are two sets" not in clean
    assert "$from hidden node" not in clean
    assert "$equal to" not in clean

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(clean)
        clean_path = Path(tmp.name)

    result = validate(clean_path)
    assert result.ok, result.to_json_dict()


def test_numeric_inline_math_and_money_regressions() -> None:
    source = r"""The answer is $0$.
The class is $1$.
The probability is $0.5$.
The z-score is $-1$.
The value is $2.0$.
Money example: $70,000 should stay money.
Price: $0.99 should stay money.
"""
    clean = sanitize(source)

    assert "The answer is $0$." in clean
    assert "The class is $1$." in clean
    assert "The probability is $0.5$." in clean
    assert "The z-score is $-1$." in clean
    assert "The value is $2.0$." in clean
    assert "Money example: \\$70,000 should stay money." in clean
    assert "Price: \\$0.99 should stay money." in clean

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(clean)
        clean_path = Path(tmp.name)

    result = validate(clean_path)
    assert result.ok, result.to_json_dict()
    assert result.inline_formulas == 5, result.to_json_dict()


def test_broken_display_math_does_not_swallow_prose() -> None:
    source = r"""$$
\delta_i^{(L)} = x $$For hidden layers $l < L$:
### Gradient of loss

### Parameter update (gradient descent)

$$For hidden layers $l < L$:

where $\eta$ is the learning rate.
## Worked example
"""
    clean = sanitize(source)

    assert "$$For hidden layers" not in clean
    assert "For hidden layers $l < L$:" in clean
    assert "### Gradient of loss" in clean
    assert "### Parameter update (gradient descent)" in clean
    assert "where $\\eta$ is the learning rate." in clean
    assert "## Worked example" in clean
    assert "$$\n### Gradient of loss\n$$" not in clean
    assert "$$\n### Parameter update (gradient descent)\n$$" not in clean
    assert "$$\nwhere " not in clean

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(clean)
        clean_path = Path(tmp.name)

    result = validate(clean_path)
    assert result.ok, result.to_json_dict()


def test_derivative_inline_math_regressions() -> None:
    source = r"""Forgetting to multiply by $f'(z)$ when applying the chain rule.
Forgetting to multiply by f'z$ when applying the chain rule through a non-linear activation function in layer j$.
Forgetting to multiply by f'$z$ when applying the chain rule.
The derivative is $f'(z_i^{(l)})$.
The layer is $j$.
The answer is $0$.
"""
    clean = sanitize(source)

    assert "Forgetting to multiply by $f'(z)$ when applying the chain rule." in clean
    assert (
        "Forgetting to multiply by $f'(z)$ when applying the chain rule through "
        "a non-linear activation function in layer $j$."
    ) in clean
    assert "Forgetting to multiply by $f'(z)$ when applying the chain rule." in clean
    assert "The derivative is $f'(z_i^{(l)})$." in clean
    assert "The layer is $j$." in clean
    assert "The answer is $0$." in clean
    assert "f'z$" not in clean
    assert "f'$z$" not in clean
    assert "whenapplying" not in clean
    assert "layerj" not in clean

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(clean)
        clean_path = Path(tmp.name)

    result = validate(clean_path)
    assert result.ok, result.to_json_dict()


def test_table_rows_keep_inline_math() -> None:
    source = r"""| Symbol | Meaning | Explanation |
|---|---|---|
| $f'(z)$ | Local Gradient | The derivative of the activation function evaluated at $z$. |
| $\delta_i^{(l)}$ | Error term | The error signal for neuron $i$ in layer $l$. |
| $w_{ij}^{(l)}$ | Weight | Weight from neuron $j$ to neuron $i$. |
| $a$ | Activation | The final output of the neuron, $f(z)$. |

$$
. |
| $f'(z)$ | Local Gradient | The derivative of the activation function evaluated at $z$. |
"""
    clean = sanitize(source)

    assert "| $f'(z)$ | Local Gradient |" in clean
    assert "| $\\delta_i^{(l)}$ | Error term |" in clean
    assert "| $w_{ij}^{(l)}$ | Weight |" in clean
    assert "| $a$ | Activation | The final output of the neuron, $f(z)$. |" in clean
    assert "$f$z$$" not in clean
    assert "$$\n| $" not in clean

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(clean)
        clean_path = Path(tmp.name)

    result = validate(clean_path)
    assert result.ok, result.to_json_dict()
    assert not any("| $f'(z)$ |" in error.expr for error in result.errors)


def test_square_bracket_display_math_regressions() -> None:
    source = r"""[ a \le x \le b,\quad c \le y \le d,\quad p \le z \le q. ]

[ \int_{z=p}^{z=q} f(x,y,z),dz ]

[ \int_{y=c}^{y=d} \left[ \text{result from step 2} \right] dy ]

[ \iiint\limits_{R} \sin x , \cos y , dz,dy,dx, ]

\[
\int \sin(k u),du = -\frac{1}{k}\cos(k u) + C
\]

[important note]
[see chapter 3]
[Google](https://google.com)
"""
    clean = sanitize(source)

    assert "$$\na \\le x \\le b,\\quad c \\le y \\le d,\\quad p \\le z \\le q.\n$$" in clean
    assert "$$\n\\int_{z=p}^{z=q} f(x,y,z)\\,dz\n$$" in clean
    assert "$$\n\\int_{y=c}^{y=d} \\left[ \\text{result from step 2} \\right] dy\n$$" in clean
    assert "$$\n\\iiint\\limits_{R} \\sin x , \\cos y \\,dz\\,dy\\,dx,\n$$" in clean
    assert "$$\n\\int \\sin(k u)\\,du = -\\frac{1}{k}\\cos(k u) + C\n$$" in clean
    assert "[ \\int" not in clean
    assert "[ \\iiint" not in clean
    assert "[important note]" in clean
    assert "[see chapter 3]" in clean
    assert "[Google](https://google.com)" in clean

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(clean)
        clean_path = Path(tmp.name)

    result = validate(clean_path)
    assert result.ok, result.to_json_dict()
    assert result.display_blocks == 5, result.to_json_dict()


def test_evaluation_bar_mid_regressions() -> None:
    source = r"""$-\cos(z)\Big\mid_{0}^{1}$
$2\sin(x)\cos(y)\bigg\mid_{0}^{\pi/2}$
$\sin(y)\Big\mid_{0}^{\pi}$
$\cos(y) \cdot z \big\mid _{z=0}^{1}$
$P(A \mid B)$ should remain valid
$\{x \mid x > 0\}$ should remain valid
"""
    clean = sanitize(source)

    assert "$-\\cos(z)\\Big|_{0}^{1}$" in clean
    assert "$2\\sin(x)\\cos(y)\\bigg|_{0}^{\\pi/2}$" in clean
    assert "$\\sin(y)\\Big|_{0}^{\\pi}$" in clean
    assert "$\\cos(y) \\cdot z \\big|_{z=0}^{1}$" in clean
    assert "$P(A \\mid B)$ should remain valid" in clean
    assert "$\\{x \\mid x > 0\\}$ should remain valid" in clean
    assert "\\Big\\mid" not in clean
    assert "\\bigg\\mid" not in clean
    assert "\\big\\mid _" not in clean

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(clean)
        clean_path = Path(tmp.name)

    result = validate(clean_path)
    assert result.ok, result.to_json_dict()


def test_prompt_templates_render_with_latex_braces() -> None:
    for prompt_path in PROMPTS_DIR.glob("*.md"):
        template = load_prompt_template(prompt_path.stem)
        rendered = render_prompt_template(
            template,
            title="Test",
            mode="exam",
            source=r"Source text with $\frac{x-\mu}{\sigma}$.",
        )

        assert "{title}" not in rendered
        assert "{mode}" not in rendered
        assert "{source}" not in rendered
        if "{title}" in template:
            assert "Test" in rendered
        if "{mode}" in template:
            assert "exam" in rendered
        if "{source}" in template:
            assert "Source text" in rendered
        if "z_i^{(l)}" in template:
            assert "z_i^{(l)}" in rendered
        if "{source}" in template:
            assert r"\frac{x-\mu}{\sigma}" in rendered


def test_html_renderer_inline_math() -> None:
    markdown = r"""# Test $μ$ and $σ$

The mean $μ$ is the center.

The standard deviation $σ$ is spread.

| Meaning | Formula |
|---|---|
| right area | $1-\text{left area}$ |
| z score | $z=\frac{x-\mu}{\sigma}$ |
| probability | $P(X<900)$ |

Money example: $70,000 should stay money.
"""
    html = render_markdown(markdown, title="Inline Math Smoke Test")

    assert '<span class="katex"' in html
    assert "$μ$" not in html
    assert "$σ$" not in html
    assert "$1-\\text" not in html
    assert "$z=\\frac" not in html
    assert "$P(X<900)$" not in html
    assert "Money example: $70,000 should stay money." in html


def test_backtick_wrapped_math_is_unwrapped() -> None:
    source = r"""# Backtick math

Inline `$x$` and `$\frac{\partial L}{\partial w_2}$` must become real math.

**Update:**
`$w_2$` new = `$0.5 - 0.1 \cdot 0.093 = 0.4907$`

A genuine price like $5.00 off should stay as money.

Real code: `pip install katex`, `$PATH`, and `print("$x")` must stay code.

$$
\begin{aligned}
a &= b \\
  &= c
\end{aligned}
$$
"""
    clean = sanitize(source)

    # Backtick-wrapped math is unwrapped into real inline math.
    assert "$x$" in clean
    assert "`$x$`" not in clean
    assert r"$\frac{\partial L}{\partial w_2}$" in clean
    assert r"`$\frac" not in clean

    # The numeric update line is real math now — no escaped math delimiter.
    assert "$w_2$ new = $0.5 - 0.1 \\cdot 0.093 = 0.4907$" in clean
    assert "\\$0.5" not in clean

    # Genuine currency is still escaped so it is not treated as math.
    assert "\\$5.00 off should stay as money." in clean

    # Real code spans are preserved untouched.
    assert "`pip install katex`" in clean
    assert "`$PATH`" in clean
    assert '`print("$x")`' in clean

    # Aligned display block survives intact.
    assert r"\begin{aligned}" in clean

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(clean)
        clean_path = Path(tmp.name)

    result = validate(clean_path)
    assert result.ok, result.to_json_dict()


def test_math_pdf_fixture_renders_without_raw_latex() -> None:
    fixture = ROOT / "test_scripts" / "math_pdf_fixture.md"
    clean = sanitize(fixture.read_text(encoding="utf-8"))
    html = render_markdown(clean, title="Backprop Fixture")

    import re

    # Inline + display math actually rendered as KaTeX.
    assert '<span class="katex"' in html
    assert "katex-display" in html

    # No raw LaTeX leaked into <code> spans (the "scattered fragments" symptom).
    code_spans = re.findall(r"<code>(.*?)</code>", html, flags=re.DOTALL)
    leaked = [
        span
        for span in code_spans
        if any(tok in span for tok in ("\\frac", "\\partial", "\\cdot", "\\sigma", "\\leftarrow"))
    ]
    assert not leaked, f"raw LaTeX leaked into code spans: {leaked[:3]}"

    # Backtick-wrapped math no longer renders as literal `$...$` code text.
    dollar_code = [span for span in code_spans if span.strip().startswith("$") and span.strip().endswith("$")]
    assert not dollar_code, f"dollar-math still rendered as code: {dollar_code[:3]}"

    # Genuine code with a dollar is preserved (not turned into math).
    assert "$PATH" in html

    # Aligned multi-line derivation rendered (KaTeX emits an mtable for aligned).
    assert "mtable" in html

    # Table cell math rendered as KaTeX, not literal text.
    assert html.count('<span class="katex"') >= 6


if __name__ == "__main__":
    main()
