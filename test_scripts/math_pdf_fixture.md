# Backprop Math Rendering Fixture

This fixture reproduces the math-rendering bug where models emit inline math
wrapped in backtick code spans, escaped dollars in numeric update lines, and
formulas inside tables. After sanitizing it must render as real KaTeX, not as
literal `$...$` code text.

## Inline math (backtick-wrapped — the bug)

The weight `$w$` listens to neuron `$j$`, with loss `$L = \frac12 (a_2 - y)^2$`.
We want `$\frac{\partial L}{\partial w_2}$` and `$\frac{\partial L}{\partial w_1}$`.

## Display derivative equation

$$
\frac{\partial L}{\partial w_2} = \frac{\partial L}{\partial a_2} \cdot \frac{\partial a_2}{\partial z_2} \cdot \frac{\partial z_2}{\partial w_2}
$$

## Chain-rule multi-line (aligned)

$$
\begin{aligned}
\frac{\partial L}{\partial w_2}
&= \frac{\partial L}{\partial a_2}
\cdot \frac{\partial a_2}{\partial z_2}
\cdot \frac{\partial z_2}{\partial w_2} \\
&= (a_2-y)a_2(1-a_2)a_1
\end{aligned}
$$

$$
\frac{\partial L}{\partial w_1} = (a_2-y)a_2(1-a_2)w_2a_1(1-a_1)x
$$

## Update lines (escaped-dollar bug)

**Update:**
`$w_2$` new = `$0.5 - 0.1 \cdot 0.093 = 0.4907$`
`$w_1$` new = `$0.5 - 0.1 \cdot 0.049 = 0.4951$`

A genuine price like $5.00 off should stay as money, not become math.

## Formulas inside a table

| Step | What you do | Formula |
|------|-------------|---------|
| Forward | Compute predictions | `$a_2 = \sigma(w_2 a_1 + b_2)$` |
| Loss | Measure error | `$L = \frac12 (a_2 - y)^2$` |
| Backprop (output weight) | Chain rule from loss to weight | `$\frac{\partial L}{\partial w_2} = (a_2 - y) \cdot a_2(1-a_2) \cdot a_1$` |
| Update | Move weight opposite gradient | `$w \leftarrow w - \eta \frac{\partial L}{\partial w}$` |

## Real code should stay code

Run `pip install katex` and read `$PATH`; the call `print("$x")` is not math.
