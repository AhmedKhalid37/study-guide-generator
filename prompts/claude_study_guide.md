Create a Claude-style Markdown study guide from the source text.

Title: {title}
Mode: {mode}

Requirements:
- Output valid Markdown only.
- Start with `# {title}`.
- Use clear, calm, student-friendly explanations.
- Organize with descriptive headings and compact tables.
- Include memory hints, exam clues, and common mistakes when supported by the source.
- Use valid LaTeX math with `$...$` for inline math and `$$...$$` for display math.
- Write derivatives as `$f'(z)$`, `$f'(z_i)$`, or `$f'(z_i^{(l)})$`.
- Never write derivative notation as `f'z$` or `f'$z$`.
- Split long equations into multiple display lines instead of one very long line.
- When referring to variables in prose, use `$j$`, `$k$`, `$t_k$`, and `$x_i$` directly. Do not write variables in parentheses like `(j)` or `(t_k)`.
- Never use `[ ... ]` for math.
- Use `$...$` for inline math.
- Use `$$ ... $$` for display math.
- For integrals, write them as display math blocks.
- If writing a formula on its own line, always wrap it in `$$ ... $$`.
- Literal brackets should only be used for normal text, not formulas.
- Do not invent facts not supported by the source.

Suggested structure:

# {title}

## What this chapter is about

## Big picture idea

## Important concepts explained simply

## Important definitions

## Important formulas and rules

## Comparisons you must know

## Step-by-step problem logic

## Common exam traps

## Memory shortcuts

## Mini cheat sheet

## Practice questions with answers

Source text:

{source}
