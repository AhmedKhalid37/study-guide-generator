# Math Layout Fixture (page-break / overflow / nesting)

This fixture targets the **layout** symptoms from
`docs/MATH_PDF_FIDELITY_INVESTIGATION.md` (§5–6): display equations splitting
across PDF page breaks, long single-line equations, arrows, aligned blocks, and
display math nested in lists/tables. It is meant for a **manual PDF render
spot-check** of `themes/claude_clean.css`; it does not call any external API.

## Inline math in prose

The weight $w$ updates against the loss $L = \frac12 (a_2 - y)^2$, and we track
$\frac{\partial L}{\partial w_2}$ throughout. Here is a deliberately long inline
formula that should stay on the line without overflowing:
$f(x) = a_0 + a_1 x + a_2 x^2 + a_3 x^3 + a_4 x^4 + a_5 x^5 + a_6 x^6 + a_7 x^7$.

## Short display equation (baseline)

$$
\frac{\partial L}{\partial w_2} = (a_2 - y)\, a_2 (1 - a_2)\, a_1
$$

## Long single-line display equation (overflow probe — NOT fixed in Slice 1)

$$
\frac{\partial L}{\partial w_1} = (a_2 - y)\, a_2 (1 - a_2)\, w_2\, a_1 (1 - a_1)\, x_1 + (a_2 - y)\, a_2 (1 - a_2)\, w_2\, a_1 (1 - a_1)\, x_2 + \cdots + (a_2 - y)\, a_2 (1 - a_2)\, w_2\, a_1 (1 - a_1)\, x_n
$$

## Aligned multi-line derivation

$$
\begin{aligned}
\frac{\partial L}{\partial w_2}
&= \frac{\partial L}{\partial a_2}
\cdot \frac{\partial a_2}{\partial z_2}
\cdot \frac{\partial z_2}{\partial w_2} \\
&= (a_2 - y) \cdot a_2 (1 - a_2) \cdot a_1 \\
&= \delta_2 \, a_1
\end{aligned}
$$

## Arrows and operator glyphs

Forward and backward flow: $a \to b$, $x \xrightarrow{f} y$,
$p \Rightarrow q$, and equilibrium $A \rightleftharpoons B$.

$$
x_0 \xrightarrow{\;f\;} x_1 \xrightarrow{\;g\;} x_2 \longrightarrow y
$$

## Display math inside a numbered list

1. First we define the activation:

   $$
   a_2 = \sigma(w_2 a_1 + b_2)
   $$

2. Then the gradient step:

   $$
   w \leftarrow w - \eta \frac{\partial L}{\partial w}
   $$

## Display + inline math inside a table

| Step | Inline | Display formula |
|------|--------|-----------------|
| Forward | $a_2 = \sigma(z_2)$ | $$z_2 = w_2 a_1 + b_2$$ |
| Loss | $L = \frac12(a_2-y)^2$ | $$\frac{\partial L}{\partial a_2} = a_2 - y$$ |

## Filler before a page-boundary display equation

The following paragraphs are intentional filler so the next display equation
lands near or across a page boundary in the rendered PDF. The point of Slice 1
is that the equation must move **whole** to the next page rather than being cut
horizontally across the break.

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Backpropagation
propagates the error signal backward through the network, layer by layer, using
the chain rule to attribute a share of the loss to every weight. Each weight is
then nudged in the direction that most reduces the loss. Lorem ipsum dolor sit
amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et
dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco
laboris nisi ut aliquip ex ea commodo consequat.

Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu
fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in
culpa qui officia deserunt mollit anim id est laborum. Sed ut perspiciatis unde
omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam
rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto
beatae vitae dicta sunt explicabo.

Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed
quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Neque
porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci
velit, sed quia non numquam eius modi tempora incidunt ut labore et dolore magnam
aliquam quaerat voluptatem. Ut enim ad minima veniam, quis nostrum exercitationem
ullam corporis suscipit laboriosam, nisi ut aliquid ex ea commodi consequatur.

$$
\begin{aligned}
\nabla_\theta L
&= \sum_{i=1}^{n} \frac{\partial L_i}{\partial \theta} \\
&= \sum_{i=1}^{n} (a_2^{(i)} - y^{(i)})\, a_2^{(i)} (1 - a_2^{(i)})\, a_1^{(i)}
\end{aligned}
$$

End of fixture.
