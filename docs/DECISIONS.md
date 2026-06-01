# DECISIONS.md — Non-obvious choices and why

> Append-only. Add a new dated entry when a non-obvious decision is made; do not
> rewrite history. Newest at the bottom.

---

## Generator presets are separate from styles
Generator presets (Claude-Exam / Review / Cram) carry a **full system prompt
plus tuned sampling parameters** and live in their own container/registry,
distinct from the `prompts/` style system. **Why:** styles define guide *type*
and are user-editable/AI-generatable; presets bundle prompt + sampling behavior
as a curated, tuned unit. Keeping them separate avoids leaking sampling config
into the style schema and lets each evolve independently. Presets inject their
system prompt and then **append** `MARKDOWN_MATH_SYSTEM` so math rules always
apply on top.

## Trash-before-purge for deletes
Deletion is two-stage: soft-delete moves `jobs/<id>/` → `jobs/.trash/<id>/`
(reversible), and permanent purge can act **only** on a job already in the
trash, behind a path guard that rejects any id resolving outside `jobs/.trash/`.
**Why:** a single hard-delete on a single-operator tool is too easy to fire by
accident and unrecoverable. The trash gate makes destructive loss require a
deliberate second step, and the path assertion makes it structurally impossible
to delete an active job or escape the jobs tree.

## Math validation degrades, does not fail
A math validation failure marks the offending spans and ends the job as
`completed_with_warnings` instead of failing it. **Why:** a single bad equation
should never throw away an otherwise-complete, expensive LLM generation. The
user gets the guide plus a visible warning and can fix/re-render, rather than
losing everything.

## Whitelist import parsing for shortcuts/import-export
Shortcut import/export (`library/shortcuts.json`) validates against a field
**whitelist** rather than trusting the incoming JSON shape. **Why:** import is an
untrusted-input boundary; a whitelist prevents unknown/malicious fields from
being persisted or echoed back, and keeps the on-disk schema stable regardless
of what an exported file claims to contain.

## Soft `model_hint`, not a hard pin
Presets/styles express a preferred model as a **soft hint**, not a hard pin to a
specific model. **Why:** providers and available models change; hard-pinning
would break presets when a model is renamed/retired or the configured provider
differs. The hint prefills/suggests but the user's actual provider+model
selection wins.

## Page-anchors, not slide-anchors
Anchoring/navigation is built around **page anchors** rather than slide anchors.
**Why:** the output is paginated study-guide documents (PDF/HTML), not slide
decks; page anchors map directly to the rendered artifact and stay meaningful
across PDF/HTML/DOCX, whereas slide anchors would assume a structure the output
doesn't have.

## Env-configurable truncation caps (Option A; Option B deferred)
Attachment/content truncation caps are **environment-configurable** with fixed
defaults (200k / 600k), and the truncation warning is preset-aware. **Why:**
Option A (static, env-tunable caps) ships a safe, predictable limit now without
per-provider plumbing. The richer **Option B — provider-aware caps** (sizing the
limit to each provider's real context window) is **deferred**; it adds
provider-introspection complexity that isn't justified yet for a single-operator
tool. Revisit if multi-provider context limits start causing real truncation
pain.
