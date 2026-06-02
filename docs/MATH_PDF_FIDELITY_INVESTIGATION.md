# Math / PDF Fidelity Investigation (read-only)

**Scope:** Investigation only. No renderer/theme/sanitizer/prompt code was
changed. This documents likely causes of cramped/awkward math in generated PDFs
and proposes the smallest safe next slice.

---

## 1. Branch and HEAD

- Branch: `chrome-renderer-v1`
- HEAD: `8682545` — "Reconcile handoff docs after cancel slice"
- Local == `origin/chrome-renderer-v1` (`8682545…`); working tree clean at start.

---

## 2. Files inspected

Pipeline / rendering:
- `pipeline/pdf_renderer.py` — Chromium headless print-to-PDF wrapper.
- `pipeline/html_renderer.py` — markdown→HTML, math extraction, KaTeX bridge, CSS assembly, HTML document template.
- `pipeline/math_validator.py` — KaTeX validation harness (counts + errors).
- `pipeline/markdown_sanitizer.py` — math protection + `fix_math_inner` spacing/symbol transforms.
- `scripts/validate_math.js` — Node KaTeX validation script.

Theme / KaTeX CSS:
- `themes/claude_clean.css` — the only theme; KaTeX CSS is pulled from `node_modules/katex/dist/katex.min.css` and prepended at render time (`html_renderer._load_css`).

Prompts:
- `prompts/study_guide_prompts.md`, `prompts/master_longform.md` (and siblings) — math/MCQ/formula sections.

Tests / fixtures:
- `test_scripts/test_math_regressions.py`
- `test_scripts/math_pdf_fixture.md`

Artifacts:
- Generated `jobs/*/clean.md` and `jobs/*/final.html` (display-block counts, long-line/table inspection).

---

## 3. Likely causes (most → least likely)

### A. Display equations can split across a PDF page break *(most likely)*
`themes/claude_clean.css` applies `break-inside: avoid` to `p`, `blockquote`,
`table`, `pre`, `img` — **but not to `.katex-display`** (nor to `li` containing
display math). A display equation that lands on a page boundary is therefore
free to be cut horizontally across two pages, producing the "formula lines split
weirdly / awkward near page breaks" symptom. This is the single clearest gap.

### B. Long display equations are *clipped* in print, not wrapped
KaTeX display math does **not** auto-wrap. On screen the theme uses
`.katex-display { overflow-x: auto }` (scrollable). In `@media print`
(`themes/claude_clean.css` ~lines 266–269) it switches to
`.katex-display { overflow: hidden; font-size: 0.9em }`. A PDF page cannot
scroll, so any equation wider than the ~176 mm content area (A4 210 mm − 34 mm
margins) is **clipped at the right margin** — content is silently lost and the
formula looks truncated/awkward. Artifacts contain long single-line display
equations and wide formula tables, so this is actively reachable.

### C. Compounding font-size shrink makes math look cramped
Math font size is set in several stacked rules: `.katex` 1.04em → display
`.katex 1.08em`; in print, display drops to `0.9em` (`> .katex` back to 1em),
tables go to `0.82em` with `td/th .katex` effectively `0.84em`, `pre` to
`0.75em`. The cumulative shrink — especially math inside print tables/lists —
reads as "visually cramped" even when nothing is clipped.

### D. Prompts never constrain formula width or encourage multi-line form
No math rule in `prompts/study_guide_prompts.md` (or `master_longform.md`)
tells the model to break long derivations into `\begin{aligned} … \\` lines or
to keep a display line within page width. Models emit long single-line
equations, which is the *input* that triggers causes A/B. (Prompt-side is a
cause of the content, but the layout fix belongs in CSS.)

### E. Inline math does not break mid-formula
`.katex` defaults to `white-space: nowrap`. The theme relaxes this only inside
table cells (`td/th .katex { white-space: normal }`); in body prose a long
inline formula stays on one piece and can push the line / overflow. Minor and
less common than A–C.

### F. Sanitizer spacing/symbol transforms *(least likely to be the visual cause)*
`markdown_sanitizer.fix_math_inner` rewrites spacing/symbols (`|`→`\mid `,
limit compaction in `normalize_evaluation_bars`, `,d x`→`\,dx`, leading-`_`
fixes). These are correctness-oriented and heavily regression-tested; they
affect *what* renders more than *how* it's spaced on the page. Unlikely to be
the primary "cramped" cause, but worth ruling out per-example.

**Not a cause:** the Chromium invocation (`pdf_renderer.py`) and the
markdown-it pipeline (`html_renderer._markdown_to_html`) — they faithfully
print whatever the HTML/CSS lays out. The fidelity issues are CSS layout +
LLM formula shape, not the print backend.

---

## 4. Which files own each symptom

| Symptom | Owner |
|---|---|
| Math spacing / font size | `themes/claude_clean.css` (`.katex`, `.katex-display`, `@media print` block) |
| Formula wrapping / overflow / clipping | `themes/claude_clean.css` (`@media print` `overflow: hidden`) |
| Display math split across page breaks | `themes/claude_clean.css` (missing `break-inside: avoid` on `.katex-display`) |
| Arrows / operator glyphs & spacing | KaTeX (`node_modules/katex`), invoked in `html_renderer._render_katex`; plus `fix_math_inner` |
| Single-line vs multi-line formula shape | `prompts/*.md` |
| PDF page geometry (margins/size) | `themes/claude_clean.css` `@page` (load-bearing — do not casually change) |

---

## 5. Examples needed to reproduce reliably

1. A **long single-line display equation** wider than the ~176 mm content area
   (e.g. a full chain-rule expansion) → tests clipping (cause B).
2. A display equation **positioned to straddle a page break** (needs enough
   filler content before it) → tests splitting (cause A).
3. A **tall multi-line `aligned` block** near a page boundary → tests A on
   multi-row math.
4. **Display math inside a list item** and **inside a table cell** → tests the
   `li .katex-display` / `td .katex-display` shrink paths (cause C).
5. **Arrow-heavy math**: `\to`, `\leftarrow`, `\Rightarrow`, `\xrightarrow{}`,
   `\rightleftharpoons` → tests "awkward arrows."
6. **Long inline formula** in body prose → tests inline non-breaking (cause E).

The existing `test_scripts/math_pdf_fixture.md` covers backtick-unwrapping,
escaped-dollar money, and table math, but **does not** target overflow,
page-break straddling, arrows, or list/display nesting.

---

## 6. Recommended synthetic regression fixture

Add (in a later slice) `test_scripts/math_layout_fixture.md` containing, in one
document:

- **Inline math** in prose, including one deliberately long inline formula.
- **A short display equation** (baseline).
- **A long single-line display equation** that exceeds content width.
- **An `\begin{aligned}` multi-line derivation** with several `\\` rows.
- **Arrows**: `$a \to b$`, `$x \xrightarrow{f} y$`, `$\Rightarrow$`,
  `$\rightleftharpoons$`.
- **Display math inside a numbered list item.**
- **Display + inline math inside a table row.**
- **~1 page of filler prose followed by a display equation**, so it reliably
  lands near/over a page break.

Pair it with assertions in `test_scripts/test_math_regressions.py`:
- HTML contains `katex-display` and `<span class="katex"` (renders as math).
- No raw LaTeX leaks into `<code>` (existing pattern).
- After the CSS slice: assert the CSS exposes `break-inside: avoid` for
  `.katex-display` (cheap guard against regression of the fix).

A true visual/clipping check needs a rendered PDF; keep that as a manual
`scripts/render_pdf.sh` spot-check rather than an automated assertion, to avoid
coupling CI to a Chromium binary.

---

## 7. Recommended first implementation slice (smallest safe)

**Slice 1 — stop display equations splitting across pages (CSS-only).**

In `themes/claude_clean.css`, add `break-inside: avoid;` to `.katex-display`
(both base and the `@media print` block), matching the existing treatment of
`table`/`pre`/`blockquote`/`img`. This is:
- additive, reversible, and confined to one file;
- directly targets cause **A**, the clearest defect;
- does not touch the Chromium pipeline, the math extraction bridge, the
  sanitizer, or `@page` geometry.

Verify with: `npm --prefix frontend run build` (unaffected), `python -m
compileall …` (unaffected), `python test_scripts/test_math_regressions.py`,
and a manual PDF render of the new fixture to confirm equations no longer cut
across pages.

**Deferred follow-ups (separate slices, in order):**
- **Slice 2 — overflow instead of clip (cause B):** replace print
  `.katex-display { overflow: hidden }` with a non-clipping strategy (e.g.
  allow horizontal shrink-to-fit / a scaled wrapper). Higher risk — must be
  measured against real wide equations; do not bundle with Slice 1.
- **Slice 3 — font-size rationalization (cause C):** consolidate the stacked
  print font-size rules for math in tables/lists.
- **Slice 4 — prompt guidance (cause D):** add a math-formatting rule asking
  for `aligned` multi-line form on long derivations. Prompt-only; no code.

---

## 8. Risk notes — do NOT touch in these slices

Load-bearing and explicitly out of scope:
- `pipeline/pdf_renderer.py` — Chromium flags / headless invocation. The CLAUDE.md
  rule "do not rewrite the PDF pipeline casually" applies.
- `html_renderer.py` math extraction, `PLACEHOLDER` scheme, and the Node/KaTeX
  bridge (`_render_katex`, `throwOnError`/`strict_math`).
- `markdown_sanitizer.py` transforms — covered by a large regression suite;
  changing `fix_math_inner`/protection risks silent math-correctness regressions.
- `@page { size: A4; margin: 18mm 17mm }` — changing margins/size reflows every
  document and shifts all page-break behavior.
- KaTeX version, `node_modules`, and dependency lockfiles.
- Out-of-scope subsystems per task: Local Model Manager, provider settings,
  shortcut store, Library/export, generator presets.

CSS edits are low-risk but global: any `.katex-display` change affects every
guide, so validate against multi-page, table-heavy, and list-heavy samples
before committing.

---

## 9. Confirmation

No application source was modified during this investigation. The only change is
the addition of this report under `docs/`. Renderer, theme, sanitizer, prompts,
and pipeline code are byte-for-byte unchanged. Verified via `git status` /
`git diff --stat` (docs-only).

---

## 10. Slice 1 follow-up (CSS-only) — page-break guard added

Slice 1 (`Prevent display math page breaks`) added `break-inside: avoid` +
`page-break-inside: avoid` to `.guide .katex-display` in **both** the base CSS
and the `@media print` block, matching the existing protection on
`table`/`pre`/`blockquote`/`img`. CSS-only; no renderer/sanitizer/prompt/
geometry/dependency change.

**Honest empirical result (real Chromium PDF render of a new
`test_scripts/math_layout_fixture.md`, before vs. after):** KaTeX display math
in this pipeline **already renders atomically and does not split mid-equation**,
even without the new rule. A fitting display block (incl. tall multi-row
`aligned`) jumps **whole** to the next page in both old and new CSS — KaTeX's
internal HTML (vlist / positioned spans) exposes no in-equation fragmentation
break points, and `.katex-display` additionally carries `overflow` (a scroll
container is monolithic). The only observed "split" is an equation **taller than
the printable page area**, which is a *forced overflow* that `break-inside`
cannot prevent — that is the **clipping** symptom (cause B), still deferred.

So Slice 1 is **defensive / consistency hardening**, not a fix for a reproduced
visible split: it keeps display math in the same break-protected family as the
other block elements and becomes load-bearing if a later slice removes the
`overflow` clipping behavior. **Cause B (overflow/clipping), cause C
(font-size), and cause D (prompt guidance) remain deferred** to Slices 2–4 as
described in §7 — none are claimed fixed here.

---

## 11. Slice 2 (CSS-only) — long display math overflow/clipping (cause B)

Slice 2 (`Improve long display math overflow`) changed the **print** rule for
`.guide .katex-display` from `overflow: hidden` to `overflow: visible` (the only
functional change; the `0.9em` print font-size is unchanged). CSS-only; no
renderer/sanitizer/prompt/`@page`-geometry/dependency change.

**Diagnosis (STEP 1, confirmed by real Chromium PDF renders):**
1. *What causes the clipping?* The **print** `.katex-display { overflow: hidden }`
   rule. On screen the block is `overflow-x: auto` (scrollable — nothing lost);
   in print a PDF page can't scroll, so `overflow: hidden` **silently discards**
   any part of the equation past the content box. The *reason* equations get that
   wide is KaTeX's `white-space: nowrap` (display math never auto-wraps), not the
   sanitizer or tables. Empirically, with `overflow: hidden` even a fairly modest
   single-line equation lost its right tail (end-marker text absent from the PDF
   text layer); the same equation with `overflow: visible` kept it.
2. *Smallest CSS-only mitigation?* Stop hiding the horizontal overflow in print.
   `@page` has only margins (18mm/17mm) and **no header/footer/page-number**, so
   the side margins are empty — a too-wide equation renders **left-anchored** (its
   readable start is always kept) and extends into that empty margin instead of
   vanishing. Only equations wider than the **whole A4 page** still clip, now at
   the physical page edge rather than the much narrower content box.
3. *General fix or only an improvement?* **Only an improvement.** KaTeX does not
   auto-wrap display math and CSS cannot reflow it, so arbitrarily long single-line
   equations cannot be made to fully fit CSS-only. Aggressive font shrinking does
   not help either (measured: even `0.5em` did not fit the longest probes, and it
   reintroduces the *cramping* this work is meant to reduce). So this slice
   **reduces** silent truncation; it does not guarantee every equation fits.
4. *What stays deferred?* Genuine **semantic multi-line wrapping** of long
   derivations is prompt-side (**cause D / Slice 4** — ask the model for
   `\begin{aligned} … \\` form). **Font-size rationalization** across
   tables/lists (**cause C / Slice 3**) is untouched here.

**Before/after (real markdown→HTML→PDF Chromium path):** with end-marker probe
equations of increasing length, `overflow: hidden` clipped the right marker at
**every** length tested (even short-ish ones); `overflow: visible` **kept** the
moderate lengths (recovered into the margin) and only the equations wider than the
full page still clipped at the physical edge. The real `math_layout_fixture.md`
renders cleanly (long single-line equation no longer truncated within the content
box; aligned block, arrows, display-in-list, and the sanitized table case all
unchanged — verified identical before/after). **No claim of perfect wrapping.**

---

## 12. Slice 3 (prompt-only) — long-formula guidance (cause D)

Slice 3 (`Guide long formulas into aligned math`) is **prompt-side only**. It
extends `MARKDOWN_MATH_SYSTEM` in `pipeline/orchestrator.py` (the math/table
contract appended **last** in both the default and the generator-preset system
messages) with a concise rule:

- avoid very long single-line display equations (they overflow PDF page width);
- when an equation or derivation is long, break it across multiple lines inside
  `\begin{aligned} ... \end{aligned}`, one step per line, each line kept
  reasonably short;
- write prose explanations as ordinary text outside math delimiters — never
  wrap an explanatory sentence in `$...$` or `$$...$$`.

**This addresses the prompt-side *input* (cause D), not renderer wrapping.** It
tries to make the model *emit* shorter, multi-line display math so fewer
equations are wide enough to hit the clipping behavior described in §11. It does
**not** change the renderer, KaTeX bridge, sanitizer, CSS, or `@page` geometry,
and it cannot reflow an over-wide equation the model still emits — that residual
remains the deferred CSS/renderer limit from §11. The existing aligned/MCQ/table
rules are unchanged (the new text generalizes the "prose is not math" rule that
already lives in the `mcqs_with_answers` section fragment; it does not duplicate
or contradict it). Ordering is preserved: a preset's own system prompt stays
first, `MARKDOWN_MATH_SYSTEM` stays the final appended block. Verified by
`test_scripts/test_long_formula_guidance.py` (default + preset + formula-heavy
paths all carry the guidance with the math block still last) plus the standard
build/compile/docker/smoke suite. **Font-size rationalization (cause C / Slice 3
in §7's numbering) remains untouched.**
