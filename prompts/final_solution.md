Create a final-solution style Markdown guide from the source text.

Title: {title}
Mode: {mode}

Requirements:
- Output valid Markdown only.
- Start with `# {title}`.
- Present solved procedures cleanly, like an exam solution key.
- Show steps in order and keep final answers easy to find.
- Use valid LaTeX math with `$...$` for inline math and `$$...$$` for display math.
- When referring to variables in prose, use `$j$`, `$k$`, `$t_k$`, and `$x_i$` directly. Do not write variables in parentheses like `(j)` or `(t_k)`.
- Never use `[ ... ]` for math.
- If writing a formula on its own line, always wrap it in `$$ ... $$`.
- Do not invent facts not supported by the source.

Suggested structure:

# {title}

## Given information

## Key formulas

## Solution method

## Worked solutions

## Final answers

## Checks and common errors

Source text:

{source}
