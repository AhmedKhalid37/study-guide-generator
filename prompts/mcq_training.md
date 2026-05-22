Create a Markdown study guide focused on multiple-choice question training.

Title: {title}
Mode: {mode}

Requirements:
- Output valid Markdown only.
- Start with `# {title}`.
- Teach the concepts through MCQ patterns and answer elimination.
- Explain why correct answers are correct and why distractors are wrong.
- Use valid LaTeX math with `$...$` for inline math and `$$...$$` for display math.
- When referring to variables in prose, use `$j$`, `$k$`, `$t_k$`, and `$x_i$` directly. Do not write variables in parentheses like `(j)` or `(t_k)`.
- Never use `[ ... ]` for math.
- If writing a formula on its own line, always wrap it in `$$ ... $$`.
- Do not invent facts not supported by the source.

Suggested structure:

# {title}

## Concepts MCQs usually test

## How to recognize the right method

## Common distractors

## Formula-based MCQ patterns

## Practice MCQs with explanations

## Final answer strategy

Source text:

{source}
