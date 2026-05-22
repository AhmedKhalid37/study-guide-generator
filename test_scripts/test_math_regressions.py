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


def main() -> None:
    test_sanitizer_regressions()
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
