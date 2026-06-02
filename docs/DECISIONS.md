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

## Expanded output-section toggles live on the generation request, not in shortcuts
`include_sections` (a dict-of-bool, e.g. `{"glossary": true}`) is a real field on
`LLMJobRequest` and is threaded `LLMJobRequest → run_llm_job → generate_study_guide
→ orchestrator prompt assembly`. The single source of truth is
`INCLUDE_SECTION_FRAGMENTS` in `pipeline/orchestrator.py`, mapping each canonical
toggle key → one short, section-oriented prompt fragment.
**Why this location:** the pre-existing "module" keys (`mcqs`, `glossary`, … in
`shortcut_store.KNOWN_MODULE_KEYS` + `frontend/shortcutMeta.js`) were
**shortcut-only UI state** — they round-tripped through the Builder and
`library/shortcuts.json` but **never reached prompt assembly**, so enabling them
changed nothing in the generated guide. Putting the canonical toggles on the
generation request makes them actually affect output, and keeps the request (not a
persisted shortcut) as the thing that carries intent. Shortcuts may later persist
this field, but the request is authoritative.
**Default-off backward compatibility:** an unset/empty `include_sections` (or one
with only unknown/false keys) adds **no** fragments; the assembled system message is
**byte-identical** to the previous behaviour (verified: `build_messages` with no
toggles `== MARKDOWN_MATH_SYSTEM`; preset path `== "{system}\n\n{MARKDOWN_MATH_SYSTEM}"`).
**Merge, not duplicate:** legacy shortcut keys normalise onto canonical keys via
`INCLUDE_SECTION_ALIASES` (`mcqs→mcqs_with_answers`, `formulas→formula_sheet`,
`diagrams→diagrams_figures`); `glossary`/`flashcards`/`worked_examples` map to
themselves; the ambiguous `summary`/`key_concepts`/`practice_problems` are kept as
accepted canonical keys mapping to themselves rather than forced into a misleading
alias. Unknown keys are ignored (the repo's whitelist convention for untrusted
toggle input).
**Ordering:** enabled fragments are injected into the system message **before**
`MARKDOWN_MATH_SYSTEM`, which **remains the final appended block** in both the
default and preset paths. Toggle order follows `INCLUDE_SECTION_FRAGMENTS`
insertion order, so output is deterministic regardless of incoming dict order.
Builder UI exposure (C3) and depth/difficulty/voice (C2) are deferred.

## Bulk purge loops the guarded single-item purge (no new raw-delete path)
`POST /api/jobs/bulk/purge` (added in the Library finish slice) makes **permanent**
delete reachable from the UI's Trash view. **Why it is safe:** it does not introduce
a new deletion primitive — it simply **loops the existing guarded
`purge_trashed_job`**, which can act **only** on a job already inside `jobs/.trash/`
behind a path assertion that hard-fails any id resolving outside the trash dir. Per
the existing partial-success contract, bogus ids, traversal ids (`../escape`), and
**active** (non-trashed) jobs are **rejected** (`error: not in trash`) without
touching disk; active jobs are confirmed untouched. This preserves the
"Trash-before-purge for deletes" invariant — destructive loss still requires the deliberate
two-step (soft-delete to trash, then purge) — and creates **no** path that can
hard-delete an active job or escape the jobs tree. Verified in Docker: bulk/purge
returns ok for a trashed id and `error` for bogus/escape/active ids.

## Generation axes: added depth + difficulty; voice deliberately NOT added (Styles own voice/tone)
C2 adds two **global generation-directive axes** to `LLMJobRequest`: `output_depth`
(`quick`/`balanced`/`exhaustive`) and `difficulty`
(`beginner`/`normal`/`exam_level`/`advanced`). They are **optional scalar enums**,
default unset, threaded `LLMJobRequest → run_llm_job → generate_study_guide →
orchestrator` (mirroring C1 `include_sections`) and **persisted in the job manifest**
so rerender reproduces them. The single source of truth is `OUTPUT_DEPTH_FRAGMENTS`
/ `DIFFICULTY_FRAGMENTS` in `pipeline/orchestrator.py`.
**Axes ≠ sections.** These are **global directives** that change *how* the guide is
written (how deep, how it is pitched), distinct from `include_sections`, which
*adds* specific sections (glossary, MCQs, …). They are not a new section adder and
do not duplicate the include-sections mechanism.
**`voice` was NOT added — Styles own voice/tone.** The STEP-1 investigation found the
proposed `voice` enum (`simple`/`blunt`/`formal`/`baby_step`/`cram`) maps ~1:1 onto the
existing Styles system: the `baby_steps` and `exam_cram` built-in styles, plus explicit
prompt directives like "blunt second-person voice" and "plain-English first, then formal"
in `prompts/`. Adding a `voice` axis would create **two competing tone systems** with
confusing precedence against the style/preset system prompt. Per the slice's stop rule
this was confirmed with the operator, who chose to **drop voice**. Tone/voice remains
owned by Styles; pick a style (or write a custom one) to control voice.
**`difficulty` does not duplicate `mode`.** `mode` is a vestigial free-text field
(default `study_guide`, its UI control retired) injected verbatim as `Mode: {mode}` into
the user template; it carries no difficulty semantics. `difficulty` is a distinct learner-
pitch axis, so the two do not overlap.
**Validation:** unknown axis values are **rejected at the API boundary** (`HTTP 400`,
like provider/model/theme) — misspelled enums are not silently accepted. The orchestrator
additionally ignores unknown values defensively so a stale manifest can't crash a rerender.
**Assembly order** (both paths): `preset system prompt (preset path only)` → `axis/global
directive fragments` → `include_sections fragments` → `MARKDOWN_MATH_SYSTEM` (always the
**final** appended block). Axes come **before** include-section fragments because they shape
the whole guide; depth precedes difficulty for determinism. The preset system prompt stays
first so axes never displace or weaken it.
**Backward compatibility:** with both axes unset (and no sections) the assembled system
message is **byte-identical** to the previous behaviour — verified by direct equality:
default path `build_messages(...) == MARKDOWN_MATH_SYSTEM`; preset path
`== "{system}\n\n{MARKDOWN_MATH_SYSTEM}"`. Unknown/None axes add no fragment.

## Shortcut payload whitelist now carries the real generation options; legacy modules translate on read
The `builder_setup` shortcut payload whitelist (`pipeline/shortcut_store.py`) was
extended with the actual generation-affecting fields from C1/C2: `include_sections`
(a canonical dict-of-bool), `output_depth`, and `difficulty`. **Why:** the pre-existing
shortcut `modules` keys were **shortcut/UI-only state that never reached prompt
assembly** (the C1 finding), so a saved shortcut could promise sections it never
produced. Putting the canonical fields on the whitelist lets a shortcut persist the
options that actually drive generation, ahead of the Builder-wiring slice.
**`include_sections` reuses C1 normalization.** Validation goes through
`orchestrator.normalize_include_sections` + `INCLUDE_SECTION_ALIASES` — there is **no
second alias table** in the store. Unknown section keys are dropped (the repo's
whitelist convention for untrusted toggle input) and only canonical, enabled keys are
stored, in `INCLUDE_SECTION_FRAGMENTS` order.
**Axes are rejected, not coerced.** Invalid `output_depth`/`difficulty` raise
`ShortcutStoreError` (→ HTTP 400 on create/update; on import the offending shortcut is
skipped into the batch `errors` list — the same rejection convention `name`/`type`
already use), rather than being silently coerced/persisted like `input_type`/
`export_formats`. Unset axes are stored as `None`.
**Legacy `modules` translate on read, not via migration.** `_bridge_payload` derives
`include_sections` from legacy `modules` only in the **returned/exported**
representation (`_public` + `_exportable`); explicit `include_sections` **wins** and
legacy modules only **fill missing** sections (both sides reduced to canonical
enabled-only keys, so a module can only add, never override). A field-less old
shortcut is **not** forced to grow an `include_sections` key.
**`shortcuts.json` is never rewritten on read.** Stored shortcuts stay byte-for-byte
identical on disk until the user explicitly creates/updates/imports one (verified in
Docker: identical sha256 before/after a GET + export of an injected legacy shortcut;
disk still had no `include_sections`).
**Why translate-on-read beats an in-place migration:** a migration would rewrite every
user's `shortcuts.json` the first time the new code reads it — an unrequested,
hard-to-reverse mutation of real user data, risky on a single-operator tool with no
review step. Translate-on-read gives the same forward-compatible view (read, list,
export, import-preview all show canonical sections) with **zero** disk mutation, and
the canonical fields are written only when the user deliberately saves. Old shortcuts
with no new fields and no modules keep working unchanged.

## Builder section/axis metadata: the frontend never owns the key set (C3)
The Builder's output-section and axis controls are driven by
`frontend/src/sectionMeta.js`, but that file deliberately holds **only display
metadata** — labels, the four cosmetic groups (Practice/Reference/Exam help/
Source-aware), help text, and the axis option tables. **The canonical key set lives
in the backend** (`INCLUDE_SECTION_FRAGMENTS` + the axis fragment maps in
`pipeline/orchestrator.py`). **Why:** the orchestrator validates against that map and
silently drops anything else, so a key the frontend invents would render a dead toggle
that produces nothing. Keeping the frontend as a labels-only mirror means the UI can
never promise a section the backend won't honour; the grouping is purely for
readability and re-orders freely without affecting the request. The keys were verified
1:1 against the orchestrator at build time. **Do not widen the section vocabulary in
`sectionMeta.js` alone** — add the fragment in the orchestrator first.

## The multipart `/api/jobs/llm` parser dropped generation options (C3 fix)
`/api/jobs/llm` accepts two transports: a JSON body (no attachments) and
multipart/form-data (with attachments). `LLMJobRequest` is a Pydantic model, so the
**JSON path** picked up `include_sections`/`output_depth`/`difficulty` for free, but
the **multipart path** (`_parse_llm_request`) hand-builds the model from named form
fields and only parsed `outline` — so the new C3 options were **silently dropped
whenever a generation had an attachment**. This was invisible to a build/compile check
and to the no-attachment smoke path; it only shows up as "my sections didn't apply when
I uploaded a file." Fixed by mirroring the existing `outline` handling: the axes are
read as plain form text (unset → `None`) and `include_sections` is parsed from its JSON
string (bad/non-dict JSON falls back to the default `{}`, never a 500). **Lesson:** any
field added to `LLMJobRequest` must be wired into the multipart branch too — the two
transports do not share parsing.

## Generator preset display metadata is additive + display-only (C4a)
The three generator presets (`claude_exam`/`claude_review`/`claude_cram`) live in
`_PRESET_DEFS` in `pipeline/generator_presets.py` — that registry is the **canonical
source** for both their generation params and their descriptive metadata. C4a added
three **display-only** descriptive fields ahead of the preset-card UI (C4b): `purpose`
(short purpose label), `recommended_use` (one-line "best with …" guidance), and `model`
(a clean model-name string for an icon/model chip, distinct from the longer prose
`model_hint`). They are exposed through the **existing** `_public()` → `list_generator_presets()`
→ `/api/options.generator_presets` path — no new endpoint. **Why these are safe:** none
of the new fields are read by any resolution path. Generation reads only `block` (→ system
prompt via `resolve_system_prompt`), the sampling params (`temperature`/`top_p`/
`max_tokens`/`thinking`), and `provider`/`model_hint`/`name` (for the soft mismatch
warning text only). Verified by grep: `purpose`/`recommended_use`/`model` appear **only**
in the registry defs and `_public`, nowhere in `orchestrator.py`/`run_llm_job.py`/the
`/api/jobs/llm` handler. A live `claude_review` generation completed `done` and the job
manifest recorded `generator_preset: claude_review` unchanged, with **no** display field
leaking into the manifest. **`model_hint` stays a soft advisory — not a hard pin.** Per the
existing "Soft `model_hint`, not a hard pin" decision, the preset path only **soft-warns**
on a provider mismatch (`generator_preset_warning`) and never blocks; the user's actual
provider+model selection still wins. C4a does not change that — it adds no enforcement.
**Safe serialization:** `_public` reads the new fields via `.get()`, so a preset that omits
an optional descriptive field serializes it as `None` rather than raising. Existing preset
ids are unchanged. The **frontend preset cards / compatibility warning are deferred to C4b**;
do not hardcode card data in the frontend — it must consume this backend metadata.

## `/api/jobs/llm` has two request-construction paths — wire + verify BOTH (permanent rule)
`/api/jobs/llm` accepts two transports and they **do not share request parsing**: a JSON
body (no attachments, parsed for free by the `LLMJobRequest` Pydantic model) and a
multipart/form-data body (with attachments, hand-built field-by-field in
`_parse_llm_request`). **Permanent rule:** any future request field added to `LLMJobRequest`
must be (a) wired into the multipart `_parse_llm_request` branch as well, and (b) verified
in **both** paths by tests/smoke — a build/compile check and a no-attachment smoke run will
**not** catch a field dropped only on the multipart side. This rule exists because C3 found
the multipart path silently dropped `include_sections`, `output_depth`, and `difficulty`
(they applied on the JSON path but vanished whenever a generation had an attachment); see
"The multipart `/api/jobs/llm` parser dropped generation options (C3 fix)" above. C4a adds
no `LLMJobRequest` field, so it does not exercise this rule, but it codifies it so future
slices do.
