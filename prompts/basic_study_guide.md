Create a complete Markdown study guide from the source text.

Title: {title}
Mode: {mode}

Requirements:
- Start with `# {title}`.
- Explain the topic in clear student-friendly language.
- Preserve important facts and terminology from the source.
- Use Markdown headings for organization.
- Use tables for comparisons or compact summaries.
- Use valid LaTeX math with `$...$` for inline math and `$$...$$` for display math.
- When referring to variables in prose, use `$j$`, `$k$`, `$t_k$`, and `$x_i$` directly. Do not write variables in parentheses like `(j)` or `(t_k)`.
- Never use `[ ... ]` for math.
- Use `$$ ... $$` for display math.
- If writing a formula on its own line, always wrap it in `$$ ... $$`.
- Literal brackets should only be used for normal text, not formulas.
- Do not invent facts not supported by the source text.

Suggested structure:

# {title}

## What this is about

## Key ideas

## Important definitions

## Formulas and rules

## Worked examples

## Common exam traps

## Mini cheat sheet

## Practice questions with answers

Source text:

{source}
