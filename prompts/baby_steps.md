Create a baby-step Markdown study guide from the source text.

Title: {title}
Mode: {mode}

Requirements:
- Output valid Markdown only.
- Start with `# {title}`.
- Explain as if the student is seeing the topic for the first time.
- Break every idea into small steps.
- Use simple words before technical terms.
- Use valid LaTeX math with `$...$` for inline math and `$$...$$` for display math.
- When referring to variables in prose, use `$j$`, `$k$`, `$t_k$`, and `$x_i$` directly. Do not write variables in parentheses like `(j)` or `(t_k)`.
- Never use `[ ... ]` for math.
- If writing a formula on its own line, always wrap it in `$$ ... $$`.
- Do not invent facts not supported by the source.

Suggested structure:

# {title}

## Big picture in simple words

## New words you need first

## Step-by-step explanation

## Formulas explained slowly

## Tiny examples

## Common mistakes

## Final recap

Source text:

{source}
