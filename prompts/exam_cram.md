Create an exam-cram Markdown study guide from the source text.

Title: {title}
Mode: {mode}

Requirements:
- Output valid Markdown only.
- Start with `# {title}`.
- Focus on what a student must remember for an exam.
- Prefer compact tables, bullet points, and short explanations.
- Include likely exam wording and traps when supported by the source.
- Use valid LaTeX math with `$...$` for inline math and `$$...$$` for display math.
- Write derivatives as `$f'(z)$`, `$f'(z_i)$`, or `$f'(z_i^{(l)})$`.
- Never write derivative notation as `f'z$` or `f'$z$`.
- Split long equations into multiple display lines instead of one very long line.
- When referring to variables in prose, use `$j$`, `$k$`, `$t_k$`, and `$x_i$` directly. Do not write variables in parentheses like `(j)` or `(t_k)`.
- Never use `[ ... ]` for math.
- If writing a formula on its own line, always wrap it in `$$ ... $$`.
- Do not invent facts not supported by the source.

Suggested structure:

# {title}

## Must-know ideas

## Definitions to memorize

## Formulas to memorize

## Exam clues

## Common traps

## One-page cram sheet

## Quick practice

Source text:

{source}
