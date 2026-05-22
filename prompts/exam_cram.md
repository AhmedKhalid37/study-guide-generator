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
