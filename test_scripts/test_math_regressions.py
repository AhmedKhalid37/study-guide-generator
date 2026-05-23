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
    test_prompt_templates_render_with_latex_braces()
    test_html_renderer_inline_math()
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


if __name__ == "__main__":
    main()
