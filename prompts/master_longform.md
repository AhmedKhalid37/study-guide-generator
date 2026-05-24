Create a comprehensive master-level Markdown study guide from the source text.

Title: {title}
Mode: {mode}

Length and depth requirements:
- Target 4500-6500 words.
- Write enough detail to usually produce a 10+ page PDF.
- Do not summarize briefly.
- Do not stop after a high-level overview.
- Expand each major section fully with clear explanations, derivations, examples, and exam-oriented interpretation.
- Treat the reader as serious and motivated, but still explain each step carefully.
- If the source text is short, use it as the topic seed and build a rigorous guide from standard, accurate knowledge of the subject.
- Do not invent unsupported claims about specific courses, instructors, page numbers, or private materials.

Math and Markdown requirements:
- Use valid Markdown headings.
- Use valid LaTeX math with `$...$` for inline math and `$$...$$` for display math.
- Use display math for important equations.
- Split long equations into multiple display lines instead of one very long line.
- Never use `[ ... ]` for math.
- Use `$...$` for inline math.
- Use `$$ ... $$` for display math.
- For integrals, write them as display math blocks.
- Never write browser notes, CSS notes, style notes, renderer notes, or PDF layout instructions in the guide.
- Write derivatives as `$f'(z)$`, `$f'(z_i)$`, or `$f'(z_i^{(l)})$`.
- Never write derivative notation as `f'z$` or `f'$z$`.
- When referring to variables in prose, use `$j$`, `$k$`, `$t_k$`, `$x_i$`, `$z_i^{(l)}$`, and similar notation directly.
- For tables, keep math inside normal inline `$...$` delimiters.

Required structure:

# {title}

## 1. Big-picture intuition
Explain what the topic is, why it matters, what problem it solves, and how the major pieces fit together. Use a concrete mental model before moving into formal details.

## 2. Core definitions and notation
Include a notation table. Define all symbols before using them heavily. Explain inputs, outputs, parameters, activations, losses, gradients, layers, indices, and dimensions where relevant.

## 3. Computational graph view
Explain the computation as a graph of intermediate values. Describe local derivatives, upstream gradients, downstream gradients, and the chain rule. Make clear how gradients flow backward through composed functions.

## 4. Forward pass
Derive the forward computation step by step. Include scalar notation and then generalize to vectors or matrices where appropriate. Explain dimensions and what each intermediate quantity represents.

## 5. Loss function and objective
Explain the objective being optimized. Show how the loss connects predictions to targets. Include common losses if relevant, and explain how the choice of loss affects gradients.

## 6. Backward pass derivation
Give a careful derivation. Do not skip algebraic steps. Show how each gradient is obtained from the chain rule. Use display math for the important equations and explain every term in prose.

## 7. Scalar worked example
Work through a small scalar example with explicit numbers or symbolic variables. Show the forward values, the local derivatives, the backward gradients, and the parameter update.

## 8. Vectorized and matrix form
Translate the scalar derivation into vectorized notation. Explain shapes, broadcasting, matrix multiplication order, transposes, and why vectorization is computationally useful.

## 9. Implementation intuition
Explain how this would be implemented in code or an autodiff system. Discuss cached forward values, reverse topological order, gradient accumulation, batch dimensions, and numerical stability concerns.

## 10. Common mistakes and misconceptions
Give a detailed list of mistakes, why they happen, and how to avoid them. Include sign errors, missing activation derivatives, shape mismatches, averaging over batches, mixing elementwise and matrix multiplication, and confusing local and total derivatives when relevant.

## 11. Exam-style questions with answers
Provide substantial practice questions. Include conceptual questions, derivation questions, shape-checking questions, and small calculation questions. Put the answer and reasoning immediately after each question.

## 12. Mini cheat sheet
Give a dense but readable cheat sheet of the most important formulas, definitions, and decision rules.

## 13. Glossary
Define important terms in plain language.

## 14. Final summary
End with a strong synthesis that connects intuition, notation, derivation, implementation, and exam readiness.

Source text:

{source}
