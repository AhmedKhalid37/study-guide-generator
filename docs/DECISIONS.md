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

## Preset-card model-hint matching + provider-icon fallback are frontend display-only (C4b)
The C4b preset cards and compatibility warning live entirely in the frontend
(`frontend/src/presetMeta.js` + `GeneratorPresetControls`/`GeneratorPresetCard` in
`BuilderWorkspace.jsx`) and consume the C4a backend metadata
(`/api/options.generator_presets`) — **no preset copy is hardcoded** and **no backend,
registry, prompt-assembly, or shortcut-store code changed**. Three non-obvious frontend
choices were made:
**Model-hint matching is conservative and prefers no warning.** The soft `model_hint` is
PROSE ("DeepSeek V4 Pro", "Gemma 4 (31B dense preferred)") while the user's selected value
is a model **id** ("deepseek-v4-pro", "gemma-4-…gguf"). `presetCompat` normalises both sides
to alphanumeric-only tokens (lowercase, strip non-alphanumerics) and treats it as a match on
equality OR substring-containment in either direction, testing the selected id against **both**
the prose `model_hint` **and** the cleaner `model` chip string. The `model` string is the key
rescue: "Gemma 4" → `gemma4` is contained in `gemma-4-…gguf`, where the longer prose hint
(`gemma431bdensepreferred`) would not match and would false-positive the local model. The
warning fires **only** when a `model_hint` is present, the selected model is known, and there
is a confident non-match — an absent hint or unknown model yields **no** warning. **Why:** the
prose-vs-id ambiguity makes false positives the real risk (a noisy warning on the correct
model erodes trust), so we bias to silence when unsure, per the slice's "do not warn if
unsure" rule.
**`model_hint` stays a soft advisory — the warning never blocks.** Per the existing "Soft
`model_hint`, not a hard pin" decision, the warning does not disable Generate (the button is
`disabled={running}` only), does not auto-switch the model, and does not alter the generate
payload — `buildLlmPayload` always sends the user's selected `model` and `generator_preset`
independently. The old provider-mismatch note was **replaced** by this model-hint advisory
(model-level is more precise than provider-level for the user's actual selection). Proven
end-to-end: a `claude_review` (hint "DeepSeek V4 Pro") generation with the non-hint
`deepseek-chat` model completed `done` with the manifest recording the user's `deepseek-chat`.
**Provider icons are local SVGs on a light chip, with a text-badge fallback.** Only providers
we ship a local SVG for (`deepseek`/`qwen`/`local`, normalised lowercase/trimmed) get an icon;
anything else (or a broken/missing image via `onError`) falls back to a styled text badge, so
icon loading never blocks card render. Logos render on a small **white chip** because the Qwen
and Local marks are near-black and would be invisible on the dark UI. Vite emits the SVGs as
separate hashed asset files (they exceed the 4 KB inline limit), not base64 inside the JS
bundle. No icon packages or remote downloads were added.

## Explicit Qwen 3.7 Max/Plus compatibility family — frontend display-only (C4d)
The C4d preset-card polish added a small **compatibility-family** layer to the
frontend `presetCompat` matcher (`frontend/src/presetMeta.js`): two models in the
**same explicit family** are treated as compatible, so a preset tuned for one
suppresses the advisory mismatch warning for the other. **Currently the only family
is `["qwen37max","qwen37plus"]`** (normalised `normalizeModelToken` forms). **Why:**
C4c added `qwen3.7-plus` to the registry, but the Claude-Cram preset's `model_hint`/
`model` is "Qwen 3.7 Max", so token matching alone (`qwen37max` vs `qwen37plus`) gave
no equality/containment and the card false-warned on the perfectly compatible Plus
model — exactly the kind of noisy false positive the C4b "prefer no warning" rule
exists to avoid. The fix is **deliberately conservative**: an explicit allow-list pair,
**not** a broad "any Qwen 3.x" rule (e.g. `qwen3.6-plus` still warns against the 3.7
preset), so the family can't silently mask a genuinely different model. It is **frontend
display-only** — no backend metadata, registry, prompt-assembly, shortcut-store, or
generate-payload change; the warning stays **advisory and non-blocking** (Generate is
`disabled={running}` only; the user's selected model + preset are still sent verbatim).
A companion display helper `presetModelLabel` renders the Qwen 3.7 preset's model as
**"Qwen 3.7 Max / Plus"** (one preset covers both) while every other preset shows its
backend `model` string verbatim. Verified by an esbuild harness driving the real
`presetCompat`/`presetModelLabel` (9/9: Max→no-warn, Plus→no-warn, `qwen3.6-plus`→warn,
cross-provider→warn, DeepSeek/Gemma matches→no-warn). **To extend later:** add another
explicit token pair/group to `COMPAT_FAMILIES` — keep families tight and intentional.

## PDF extraction: page-level (not whole-document) text/OCR fallback (integ-group-c)
`_extract_pdf` (`pipeline/extract.py`) now decides text-vs-OCR **per page** instead of
for the whole document. **Why:** the previous all-or-nothing gate (`if any embedded text
exists, return text for the entire file; else OCR the entire file`) mis-handled *mixed*
PDFs — a mostly-scanned deck whose title slide carried a few words of embedded text was
treated as "fully text-extracted", so OCR never ran and pages 2–N were lost (the manual
118-page `04_Neural_Networks...Backpropagation` test extracted ~97 chars / only `## Page 1`).
**Heuristic:** a page's embedded text is "meaningful" — and OCR is skipped for it — when the
stripped text is **≥ 40 chars OR has ≥ 5 word-like tokens** (`\w+`); otherwise that page is
OCR'd individually. Chosen to be conservative: the bug's title slide (97 chars) correctly
stays a *text* page while blank/image-only pages (≈0 chars) fall through to OCR, and a normal
all-text PDF never triggers unnecessary OCR. A page uses embedded text **XOR** OCR (never
both appended) so content is not duplicated; if OCR yields nothing on a sparse page, its small
embedded text is kept rather than dropping the page. **Mode reporting** gained a third value
**`pdf_mixed`** (alongside `pdf_text` / `pdf_ocr`) to reflect documents that used both paths;
mode is informational metadata only (stored in `job.json` `attachments[].mode`, never branched
on), so this widened no API contract. **Why page-level over a blanket "OCR every page":** OCR
is slow (~1–2 s/page) and lossier than embedded text, so real text pages must keep their exact
embedded text; blanket OCR would also regress quality on normal PDFs. Large-PDF UX (preflight,
page-range selection, OCR cost limits) is **deliberately out of scope** here. Regression:
`test_scripts/test_mixed_pdf_ocr.py` (synthetic page-1-text + pages-2/3-image PDF). Verified on
the real artifact: ~97 → 18,799 chars, 1 → 118 `## Page` headings, mode `pdf_mixed`.

## Consumed feature branches must not be re-merged; new work branches from `chrome-renderer-v1`
Group C shipped as a long stack of feature branches (`style-output-toggles`, `style-axes`,
`shortcut-options-bridge`, `builder-options-ui`, `preset-metadata`, `preset-cards-ui`,
`qwen37-plus-model`, `home-nav-cleanup`, `preset-card-polish`, the `library-*` branches, etc.).
That entire stack was **squashed and integrated** onto `chrome-renderer-v1` (squash `6f888b2`,
trunk now at `1d51b36`, pushed). **Those branches are now consumed/archival — do NOT merge or
rebase any of them again.** Their content already lives in the trunk; re-merging would
reintroduce superseded code, resurrect already-fixed conflicts, or duplicate history. **Rule:**
all new work branches from `chrome-renderer-v1` at `1d51b36` or later — never from an old
stacked branch. **Why:** the stack diverged from the Chrome-renderer base, so the old branches
no longer share the trunk's lineage; treating the integrated trunk as the single source of truth
keeps history linear and avoids re-litigating resolved divergence. The old branches are **kept,
not deleted** (operator preference), purely as archival reference. See
`docs/NEXT_CHAT_HANDOFF.md` for the short start-here.

## Docker hardening: compose resource limits salvaged; GHCR publish + pinned deps deferred
Two local-only commits (`61c134c`, `863f5b7`) were parked on the `hardening` branch and
investigated rather than merged wholesale. The **useful, low-risk, local-aligned** pieces were
salvaged surgically onto the trunk: `_preprocess_ocr_image` from `61c134c` (`5bde798`) and the
**compose resource limits / `no-new-privileges` hardening** from `863f5b7` (`1d51b36`:
`mem_limit: 2g`, `pids_limit: 256`, `cpus: 2.0`, `security_opt: no-new-privileges:true`,
additive to `docker-compose.yml`). `863f5b7`'s non-root/gosu/`appuser` hardening was already in
the trunk at `6f888b2`, so it was not re-applied. **Deferred (need a deliberate decision, not a
salvage):** (a) the **GHCR publish workflow + prebuilt `image:` line** — a distribution decision
that the local-only/single-operator posture does not yet justify; and (b) the **fully pinned
`requirements.txt` lockfile** — reproducibility is desirable, but a freeze must be regenerated
from the current tree, not lifted from the divergent `hardening` branch. **Why salvage-not-merge:**
the two commits also carried obsolete or divergent changes (already-superseded event-loop/OCR
edits, a comment-stripped Dockerfile, GHCR coupling), so cherry-picking the genuinely-useful hunks
onto the trunk was safer than merging branches that would otherwise reintroduce conflicts and
unwanted distribution coupling. The commits stay parked on `hardening` (kept, not deleted).

## Cooperative cancel uses a sidecar marker file + checkpoints, not a manifest field or process kill (901d44b)
Server-side cancel (`POST /api/jobs/{id}/cancel`, `901d44b`) is **cooperative and
checkpoint-based**, not preemptive. Two non-obvious choices:
**Cancel state is a sidecar marker file (`jobs/<id>/cancel.requested`), NOT a `job.json`
field.** The running job thread continuously read-modify-writes the manifest via
`set_stage`/`update`, so a cancel flag written into `job.json` by the request handler
could be **clobbered** by a concurrent manifest write from the worker (lost-update race).
The marker is **write-once by the canceller and existence-checked by the pipeline**
(`Job.request_cancel`/`raise_if_cancelled`/`clear_cancel_request` in
`pipeline/job_manager.py`), so the two sides never contend on the same mutable file. This
mirrors the existing trash-marker pattern. The endpoint itself does **not** set status —
the worker thread owns the manifest and transitions to the new terminal status `cancelled`
(distinct from `failed`, `error: null`) when it catches the `JobCancelled` signal.
**Cancel is "stop at the next safe checkpoint," not an instant abort, and never kills a
process.** `raise_if_cancelled` is checked **only at existing stage boundaries** (before
extraction, before the LLM call, after the LLM returns / before render, at the top of the
raw-markdown pipeline, and before `render_pdf`) — **never** mid-LLM-call, mid-Chromium-render,
or mid-`save_clean_md`. **Why:** the LLM HTTP call and the Chromium PDF render are
uninterruptible external waits; forcibly killing them risks corrupt partial output and a
wedged renderer, and the PDF/Chromium pipeline is load-bearing and must not be rewritten for
this. So a cancel requested during one of those waits takes effect only when that call
returns. **Nothing is deleted on cancel** — partial artifacts, the source/input, and the
user's Builder inputs/selections are preserved, so the user simply re-generates.
**Retry-from-cancelled is intentionally NOT wired** (`retry_failed_job` stays gated to
`failed`) — re-generate from the Builder instead; already-terminal jobs are a safe no-op
(no marker written, artifacts untouched).

## Large-PDF core: read-only preflight + flat `page_selections`, original anchors, no auto-split (841d3f9→60c3e78)
The large-PDF workflow (`docs/LARGE_PDF_PREFLIGHT_DESIGN.md`, shipped as Slices 1–5)
makes a big/scanned PDF inspectable and page-selectable **before** generation, without
rewriting the load-bearing extractor or OCR. Several non-obvious choices:
**Preflight is read-only and degrades to `ok`, never blocking a processable PDF.**
`POST /api/preflight/pdf` (`api/server.py` + `pipeline.extract.preflight_pdf`) probes a
**bounded, evenly spaced page sample** (not the whole document) and reuses the existing
`_is_meaningful_page_text` / `_ocr_available()` heuristics; `_extract_pdf` is **untouched**
by preflight. It returns `verdict` (`ok`/`warn`/`blocked`) + `warnings[]` + `allowed_actions[]`.
Only **encrypted/corrupt** PDFs are `blocked`; **any other inspection failure (incl.
PyMuPDF missing) degrades to `ok`** so preflight can never stop a PDF the real extractor
could process. **Why:** preflight is advisory UX, not a gate — a flaky/absent inspector
must fail open. The frontend also treats a preflight network/parse failure as a soft
warning that never blocks generation. **`split_automatically` is never emitted** (the
auto-split path is deferred).
**`page_selections` is a flat `{filename: [[start, end], …]}` (1-based inclusive), chosen
over the design doc's `{mode, first_n, ranges}` object.** "First N" is just `[[1, N]]`, so
the flat list-of-ranges form needs no mode discriminator and normalizes uniformly.
Validation (`_normalize_page_selections`) sorts + merges overlapping/adjacent ranges to a
canonical spec, rejects bad shapes with **HTTP 400** (bool rejected), and is bounded
(`MAX_PAGE_SELECTION_FILES`=20 / `MAX_PAGE_RANGES_PER_FILE`=50). It is wired into **both**
the JSON and multipart request paths (per the permanent two-path rule) and **persisted in
`job.json`**, preserved across retry. Absent/empty ⇒ `{}` ⇒ all pages ⇒ byte-equivalent to
the previous behaviour.
**Extraction keeps ORIGINAL page anchors and OCRs only selected pages.** `_extract_pdf` was
extended **surgically** with an optional `pages=` filter (PDF-only; ignored for every other
type): a single `if index not in selected: continue` at the top of the existing per-page
loop, **before** any `get_text`/OCR, so OCR never runs on unselected pages. The loop still
enumerates from 1 and emits `## Page {original index}`, so selecting pages 20–21 yields
`## Page 20`/`## Page 21`, **never** renumbered to page 1. Selections are matched by the
attachment's **original filename** (exact `dict.get`, no fuzzy/index guessing); out-of-range
pages are **dropped (not clamped)** with a warning; if no selected page is in range the
extractor returns empty cleanly (no crash). **Why original anchors:** page references in the
guide must point at the source's real page numbers to stay meaningful (consistent with
"Page-anchors, not slide-anchors").
**Deferred, deliberately:** automatic split/chunk processing; hybrid embedded-text + OCR
dedup; raising the upload ceiling (`MAX_UPLOAD_MB`, reported but unchanged); persisting the
**preflight report** in `job.json`; carrying page selections into **drafts/shortcuts** (the
attachments they reference are not persisted either, so a stored selection would be
orphaned). None are started — each is its own future slice with sign-off, not an
implementation-ready item.

## Provider settings: two-file split, write-only keys, redaction by construction
The in-app provider settings store (Slice 1, `pipeline/provider_settings_store.py`)
splits state into two gitignored files: `config/provider_settings.json` (non-secret,
`0644`) and `config/secrets.json` (raw API keys ONLY, `0600`). **Why split, not one
file:** it makes the security boundary physical, not a code convention — a reviewer
verifies "no key leaks" by checking the public serializer reads only the non-secret
file + `configured`/`key_source` flags and never serializes `secrets.json`. Keys are
**write-only over the API** (set or cleared, never read back); a blank `api_key` in a
PATCH is a no-op (never a clear) so saving other fields cannot wipe a key. The public
DTO (`_settings_to_public_dict`) has **no key field by construction**, exposing only
`configured`, a `key_source` (store/env/none), a last-4 `key_hint` (only when the key
length is > 4, so a short placeholder is never echoed whole), and `base_url_host`
(host only, userinfo stripped). **Resolution is settings -> .env -> built-in default**,
so with no store files present every lookup falls through to the prior env path,
byte-identical to before the store existed (the migration guarantee). Per-job
request provider/model still wins; the store only fills defaults; generator presets
override sampling only and never the selected provider/model. **Why env stays the
fallback (no `.env` rewrite):** consistent with "translate-on-read beats in-place
migration" — env values are consulted live, never copied into the store.

## Provider runtime settings: timeout/retry at the call boundary, transient-only retry
Wiring the stored `timeout_seconds`/`retry_count`/`thinking_default` into live
generation (provider settings Slice 3) puts timeout + retry on `LLMConfig`,
resolved once in `build_provider_config` and consumed in `generate_chat_completion`.
**Why the call boundary, not job orchestration:** one place to resolve and one place
to apply means every generation path (study-guide, style, outline, section-regen,
quiz) inherits the behavior without touching the orchestrator/job manager, and the
retry stays *internal to the single model call* — no duplicate jobs or artifacts.
**Why retry is transient-only:** retries fire only for HTTP 429, 5xx, and
connection/timeout SDK errors; 4xx (auth/model/bad-request), missing config, and
unsupported provider are deterministic — retrying just repeats the same failure (and
missing-config raises *before* any call). The provider test probe forces `retries=0`
and its own short timeout so a test fails fast instead of hammering upstream.
**Why timeout/retry have no preset tier and no new env knob:** they were never
env-configurable, and a preset tunes *sampling*, not transport — so they resolve
store → default only. **Thinking precedence (qwen-only):** explicit request/preset
value > store `thinking_default` > `True`; `qwen_thinking` defaulting to `None`
(instead of `True`) is what lets an omitted field fall through to the store, while
the Builder still sends an explicit boolean so the UI is unchanged. **Migration
guarantee preserved:** no store ⇒ no timeout, zero retries, thinking `True` ⇒
byte-identical to trunk.

## Provider fetch-models is read-only and does not auto-persist
The `POST /api/provider-settings/{provider}/fetch-models` endpoint (provider settings
Slice 4) lists a provider's upstream models by reusing the existing
OpenAI-compatible `_discover_openai_models` `/models` discovery (the same path the
`local` provider already uses) against the **effective** base URL + key
(store → `.env` → built-in default). **Why read-only:** fetching is a query, not a
mutation — it creates no job/artifacts, writes neither `provider_settings.json` nor
`secrets.json`, and **does not** auto-add the discovered ids to `custom_models`. It
returns the ids only; persisting a *selected* model belongs to the future frontend
"Refresh models" slice, where the user makes a deliberate choice. **Why no
`build_provider_config`:** model listing needs only base URL + key, so it skips the
config builder (which requires/resolves a model and would raise for a model-less
`local` provider). **Redaction unchanged:** the raw key never appears in the
response (`{provider, ok, models, source, base_url_host, error}`); `base_url_host` is
host-only; errors are classified to a coarse category and redacted of the key/full
URL before returning. **Safety on the edges:** unknown provider → HTTP 400;
unconfigured / no base URL → a safe non-OK result, never the missing-key specifics.
Provider/model precedence and preset `model_hint`-advisory behavior are untouched.

## Refresh Models UI stages fetched models but requires an explicit Save (2026-06-03)
The frontend Refresh Models control (provider settings Slice 5) treats the
read-only fetch-models result as **review-only**: fetched ids are shown, and
**Add** / **Add all new** only stage a new id into the card's **draft**
`custom_models` — nothing is written until the user runs the existing **Save**
(`PATCH /api/provider-settings/{provider}`). **Why stage-then-save, not
auto-persist:** the discovered list is whatever the upstream `/models` endpoint
returns and may include experimental, deprecated, or irrelevant ids; silently
writing them into `custom_models` (and thus into the Builder's model dropdown via
`/api/options`) would clutter the user's real choices and mutate persisted state
behind a query. Keeping the decision deliberate mirrors the backend contract
("fetch-models is read-only and does not auto-persist") at the UI layer, and keeps
the request/Save the single point where state changes. A successful fetch also
**never auto-switches** the default model or default provider, and re-seeding the
provider DTO (after Save / clear-key / page refresh) clears any shown fetch list.
Only after an explicit Save does `/api/options` surface the new ids — so a fetched
model is Builder-selectable only once the user has chosen to keep it.

## Provider Test Connection accepts empty content (2026-06-03)
The provider-settings "Test connection" probe (`POST …/{provider}/test` →
`test_provider`) now treats a returned chat-completion **choice with empty/null
content** as a **successful** connection, via a narrow `allow_empty_content=True`
kwarg on `generate_chat_completion`. **Why:** the probe sends `max_tokens=1` only
to verify **auth / connectivity / model reachability** — the content is
irrelevant (design §7: "Success = a non-error HTTP response with a choice").
Reasoning/thinking models (Qwen with thinking enabled, DeepSeek V4 Pro) spend the
single token on reasoning and return an empty visible message, so the strict
empty-content guard in `generate_chat_completion` was misclassifying a working
provider as broken (validation Finding #1). **Why not loosen it globally:** real
study-guide generation must still reject empty output so a bad/empty model
response is never silently accepted — `allow_empty_content` defaults to `False`,
so only the probe path is lenient. A response with **no** choices at all remains a
failure on both paths (it proves nothing about reachability).

## Stored default_provider is a default only (2026-06-03)
When a generation request supplies **no** provider, provider selection now
consults the stored provider-settings `default_provider` (via
`provider_config.stored_default_provider_entry`) **before** falling back to the
first-configured provider — but only when that stored default resolves to a
known, **configured** provider. The full precedence ladder is **explicit
per-request provider > stored `default_provider` > first-configured fallback**.
**Why a default and not a pin:** a per-job request is always authoritative (the
Builder sends an explicit provider/model), so the stored default must rank below
it; but it must rank above the historical "first provider in registry order"
guess so a user who sets, say, Qwen as their default actually gets Qwen when
nothing is chosen. An unset / unknown / unconfigured stored default returns `None`
and falls straight through to the old first-configured behavior, so the change is
inert unless a usable default is set (validation Finding #2 was that this tier was
missing for *provider* — it already worked for *model*). The stored `default_model`
behavior is unchanged (request model wins, else the selected provider's effective
default_model), and generator presets remain advisory — they fill sampling only and
never repin provider/model. The helper reads only the non-secret `default_provider`
field plus the already-redacted public registry, so no raw key is read or exposed.

## Shortcut inspector: additive `validity`, no migration-on-read, preview-before-apply (2026-06-04, DESIGN)
The Shortcut Inspector / Repair design
(`docs/SHORTCUT_INSPECTOR_REPAIR_DESIGN.md`) makes two non-obvious choices that
need recording even though no code ships in the design slice.
**Keep the legacy `valid`/`reason` byte-compatible and ADD a richer `validity`
object — do not repurpose `valid`.** Today `_evaluate_validity`
(`pipeline/shortcut_store.py`) returns a binary `(valid, reason)` and the
frontend's activation guard (`DesktopDashboard.handleActivateShortcut`) treats
`valid:false` as "do NOT load this setup, redirect instead". Silently widening
`valid` to mean "usable with warnings" would let a *degraded* shortcut (e.g. a
deleted style) auto-load with parts missing — a silent rewrite of intent. So the
design adds a separate `validity` object with a **3-tier status**
(`valid`/`degraded`/`broken`, = worst severity of a full `findings[]` list) and
keeps `valid == (status == "valid")` / `reason` unchanged, so every existing
consumer keeps working while new UI can distinguish "usable but warn" from
"blocked". This also fixes three real gaps in the current check: it is **binary**
(can't express degraded), **first-failure-only** (returns at the first bad
reference, hiding the rest), and **never validates the saved `model`** (a model
removed from the provider's `available_models` is silently defaulted at Builder
prefill, so the card wrongly reads valid).
**No migration-on-read; the only write is an explicit per-field repair apply.**
Consistent with the existing "translate-on-read beats in-place migration"
decision, the enriched `validity`, `GET …/inspect`, and `POST …/repair/preview`
are all **read-only** and write nothing — `shortcuts.json` stays byte-identical
until the user explicitly runs `POST …/repair/apply`. Apply reuses the existing
`update_shortcut` (in place) or `create_shortcut` (`clone:true`, original kept)
CRUD — **no new raw write path**, so the store's whitelist + atomic-write
invariants hold automatically. Repairs are **opt-in per field**
(`replace`/`remove`/`keep`/`drop_unknown`); replacement provider/model are
**preselected suggestions only, never auto-applied** (per "soft `model_hint`, not
a hard pin"); and all provider data flows through the already-redacted
`provider_config` surface, so **no raw key** is ever read or returned. Import
semantics are untouched (still whitelist-normalized with an `errors` batch); the
inspector only makes the *post-import* "needs repair" state visible and
actionable. Recommended build order: Slice 1 backend inspector (read-only),
Slice 2 frontend badges + Inspector drawer, Slice 3 repair preview + apply.

## Shortcut inspector Slice 1: legacy `valid` stays true for new degraded findings
When implementing the Slice 1 backend inspector, the legacy `valid`/`reason`
pair is computed from the **untouched** `_evaluate_validity`, and the new
`validity` object is computed independently from `_collect_findings`. This
deliberately departs from the design sketch's "`valid == (status == "valid")`":
the inspector adds checks the old code never had (`model_unavailable`,
`section_unknown`, invalid `output_depth`/`difficulty`), all of which are
**degraded**. If `valid` tracked the new status, those would flip a shortcut from
the `valid:true` it reports **today** to `valid:false` — and the activation guard
(`DesktopDashboard.handleActivateShortcut`) treats `valid:false` as "do NOT load,
redirect", so a shortcut that currently launches fine would suddenly be blocked.
**Why:** the brief's hard requirement is "`valid=true` should remain true only
where current behavior would have allowed use" and "the existing activation guard
should not break". Keeping `valid`/`reason` byte-identical satisfies both, and the
new `validity.status` is what Slice 2's UI reads to distinguish "usable but warn"
from "blocked". Net effect: a degraded-only shortcut may now show `valid:true` +
`validity.status:"degraded"` simultaneously (model/section/axis cases), while the
pre-existing broken cases (unconfigured provider, missing preset/style, bad
tool/view) keep `valid:false` exactly as before. Also decided here: an **invalid
stored axis** is reported as **degraded** (the orchestrator ignores/defaults an
out-of-enum axis at load), not broken; and `tool_route_missing` is reused for both
an unavailable tool and an unavailable library view (the `field` distinguishes
them). Inspection is fail-soft — a registry read that throws yields an
`inspection_error` *degraded* finding, never a crash or a false `broken`.

---

## Shortcut inspector Slice 2: badges are informational; activation still gates on legacy `valid` (2026-06-04)
Slice 2 adds 3-tier validity badges (Home cards + Customize rows) and a read-only
Inspector drawer, but it deliberately does **not** touch
`DesktopDashboard.handleActivateShortcut`. The new `validity.status` drives only
the **badge colour/label and the Inspector**; clicking a shortcut to *launch* it
still keys off the legacy `valid` boolean exactly as before. **Why:** the Slice 1
divergence above means a degraded-only shortcut can be `valid:true` +
`status:"degraded"` (model/section/axis) — those already launch today and must
keep launching ("degraded shortcuts remain launchable"); the pre-existing broken
cases keep `valid:false` and the existing guard keeps routing them to Models
("broken shortcuts keep legacy guard behaviour"). Re-deriving launch gating from
the new status here would either block a currently-working degraded shortcut or
silently auto-load a broken one — both violate the brief. The badge chip and the
small Info button on a card call `stopPropagation`, so opening the read-only
Inspector never also fires the card's activate handler. Consent-gated activation
of degraded shortcuts + the actual repair flow are Slice 3, not this slice.
Corollary: the **status helpers live in a pure module** (`shortcutStatus.js`, no
React) so a plain-node harness can unit-test them without a test runner, matching
the existing `verify-assets.mjs` pattern — and they include an explicit fallback
(`shortcutStatus`) for old shortcut payloads that predate the `validity` field, so
the UI never crashes on a shortcut that only carries the legacy boolean.

## Shortcut repair Slice 3A: explicit whitelisted patch, one normalizer, apply is the only write (2026-06-04)
The backend repair endpoints (`POST /api/shortcuts/{id}/repair/preview` +
`…/repair/apply`, `pipeline/shortcut_store.py`) make three non-obvious choices.
**Repair is an explicit, whitelisted patch — NOT an arbitrary JSON merge-patch.**
The request is `{mode, changes{provider, model, style, generator_preset,
output_depth, difficulty, include_sections{remove,set}, remove_fields}, clone_name}`.
Every top-level and `changes` key is whitelisted; an **unknown key is rejected with
HTTP 400**, not silently dropped, because repair is a mutation boundary where an
unrecognized instruction means the caller and server disagree about what will
happen — failing loud is safer than guessing. `remove_fields` may only drop the
*optional* builder fields (`model`/`style`/`generator_preset`/`output_depth`/
`difficulty`); **`provider` is deliberately not removable** (a generation shortcut
needs one). The proposed payload is always re-run through the existing
`_normalize_payload`, so anything outside the schema can never persist — the same
whitelist guarantee create/import already give. **Why not merge-patch:** a generic
deep-merge would let an arbitrary/unknown field ride into a saved shortcut (the
exact thing the store's whitelist exists to prevent) and would make "what does this
repair change?" unanswerable without reading the whole payload.
**Preview and apply share ONE read-only normalizer (`_prepare_repair`), and apply
is the only write.** Preview returns the proposed payload + a per-field `diff` +
the recomputed `validity` and writes nothing (`shortcuts.json` sha256 unchanged —
the same no-migration-on-read guarantee as inspect); apply persists by reusing the
**existing** `update_shortcut` (in place) or `create_shortcut` (clone) CRUD, so the
atomic write + whitelist + id generation come for free and there is **no new raw
write path**. Because both sides build the proposed record through the same code, a
preview is byte-for-byte what an apply would save. **Clone never overwrites:** it
mints a new id and leaves the original untouched, with `clone_name` (or a derived
`"<name> (repaired copy)"` suffix).
**Validation is against live config and never auto-switches provider/model.** A
replacement provider must resolve **and** be configured; a replacement model is
validated against the *repaired* provider (provider supplied in the same repair
wins, else the existing provider — and a model-only repair with no provider context
is a 400, since a model is meaningless without one); style/preset must exist; axes
must be in the store enum; `include_sections.set` keys must be canonical/alias keys.
All invalid values → 400 with a safe message, nothing written. Consistent with the
existing "Soft `model_hint`, not a hard pin" decision, a preset's `model_hint`
stays advisory — repair changes a model **only** when the caller explicitly asks,
never as a side effect. All provider data flows through the already-redacted
`provider_config` surface, so **no raw key** is ever read or returned. Repair is
scoped to `builder_setup` shortcuts (the type whose references rot against live
config); other types return a safe 400. **The frontend repair UI is Slice 3B and
deliberately not in 3A** — the read-only Inspector drawer (Slice 2) still shows a
disabled "Repair (coming next)" until 3B wires preview/apply.

## Shortcut repair Slice 3B: Apply requires a fresh preview; the draft starts empty (2026-06-04)
The frontend repair UI (`ShortcutInspector.jsx` + `frontend/src/shortcutRepair.js`,
branch `shortcut-inspector-repair-ui`) makes two non-obvious safety choices on top
of the 3A backend. **Apply is gated on a *fresh* preview of the *current* draft.**
After a successful `…/repair/preview` we remember a stable `draftSignature` (the
exact request that would be sent); the Apply button is disabled unless a preview
exists **and** its signature still equals the current draft's. Editing any
choice/value/mode/clone-name after previewing changes the signature, marks the
preview stale, and re-disables Apply with a "preview again" note — so a user can
never apply a repair they did not just see previewed. This mirrors the Builder's
existing `settingsSignature` dirty-state idea and the backend's "preview == apply"
guarantee, closing the gap where a stale preview could mislead. **The repair draft
also starts empty** (every field "keep") and `buildRepairPayload` drops empty
`replace` values, so opening the drawer or half-finishing a choice sends nothing —
combined with the explicit confirm step, there is no path from "open inspector" to
"shortcut mutated" without an explicit Preview → Apply → confirm. The frontend
never widens the backend vocabulary: only the 3A whitelisted fields/ops are
buildable, `provider` is never offered as removable (the backend rejects it), and
all candidates come from the already-redacted inspect response — **no raw key**.
Home **activation stays byte-for-byte unchanged** (still gated on legacy `valid`);
the degraded-activation confirm + "Repair instead" path from design §5.5 is
deliberately **deferred**, not silently changed.

## Degraded shortcuts stay launchable but require an explicit confirm; legacy `valid` is still the hard guard (2026-06-04)
The degraded-activation slice (branch `shortcut-inspector-degraded-activation`)
finally lets a **degraded** shortcut's `validity.status` influence *launch*
behaviour — but **only** to interpose a confirmation, never to block. A pure
`activationDecision(shortcut)` (`frontend/src/shortcutStatus.js`) is the single
source of truth and returns `launch | confirm | blocked` with the **legacy
`valid` boolean as the hard guard**: `valid === false` is **always** `blocked`
(byte-for-byte the old block behaviour), and only then does status matter —
`validity.status === "broken"` also blocks, `degraded` (with `valid !== false`)
asks, and everything else (valid, or an old payload that predates `validity`)
launches. **Why this ordering:** the Slice 1/2 divergence means a degraded
shortcut is `valid:true` + `status:"degraded"` and **launches today**; the brief
requires it to *stay* launchable, just not *silently*. Deriving the decision from
status alone would have risked blocking a `valid:true` shortcut whose status was
mislabeled, or (worse) launching a `valid:false` one whose status drifted to
`degraded`; gating on legacy `valid` **first** makes both impossible. **Continue
anyway** calls the unchanged `onActivateShortcut` path with **no repair/mutation**
— degraded parts are dropped/defaulted by the pipeline exactly as before, the
confirm only makes that consequence visible ("some saved settings may be ignored
or replaced by defaults"). **Repair instead** only opens the existing single
`ShortcutInspector` drawer (no second inspector system); it triggers **no**
preview/apply until the user drives the existing repair UI. **Broken** shortcuts,
which previously routed silently (e.g. a missing-provider `builder_setup` jumped
to Models), now surface a "This shortcut is broken." dialog offering Inspect /
Repair and **never route to Builder/Tools** — staying blocked while making the fix
discoverable. The gate lives in `HomeShortcuts.requestActivate` and reuses the
pure Slice 2 status helpers, so no status logic is duplicated and the decision is
node-testable (`verify-shortcut-activation.mjs`). Backend untouched.

## Outline templates and generator presets are separate registries; the Shortcut Edit modal must use the generator-preset one (2026-06-04)
Two distinct registries exist and must never be conflated. **Generator presets**
(`pipeline/generator_presets.py`, exposed at `/api/options.generator_presets`:
`claude_exam` / `claude_review` / `claude_cram`) drive the *system prompt + sampling
params* and populate the Builder **Style** tab's preset cards and the shortcut
payload field `generator_preset`. **Outline quick-templates** (`pipeline/presets.py`,
exposed at `/api/presets`: `exam_guide` / `report_guide` / `presentation` /
`chapter_summary` / `final_revision`) are *outline section bundles* that populate the
Builder **Outline** tab. The Shortcut Edit modal regressed by sourcing its "Generator
Preset" dropdown from `/api/presets` (the wrong registry), so it saved outline ids
into `payload.generator_preset` and the Inspector flagged them
`generator_preset_missing`. **Decision:** the modal now reads
`/api/options.generator_presets` (the same canonical list the Builder Style tab uses)
via the pure `generatorPresetOptions()` helper. A non-empty stored id absent from the
live list is shown as a trailing **"unavailable"** option — loaded, not crashed, and
**not rewritten on read** (consistent with the no-migration-on-read rule). The Outline
flow keeps using `/api/presets` unchanged.

## Shortcut `saved_prompt` is opt-in because shortcut exports may contain private user content (2026-06-04)
A builder_setup shortcut may optionally carry the typed **source prompt/text** under a
whitelisted `saved_prompt` field, but it is **opt-in and default OFF**, captured only
when the user ticks the *"Save prompt/source text with this shortcut"* checkbox.
**Why:** shortcuts are exportable/importable JSON and a study-guide source prompt can
be **private course material**; baking it into every shortcut (or saving it silently)
would leak user content into shared exports. So the key is **omitted entirely** unless
opted in, the inspector marker `saved_prompt_included` carries the **length only, never
the text** (so list/inspect responses don't echo content), and UI surfaces ("Saved
prompt" badges, import-preview line) make inclusion visible rather than hidden. It is
**user content, not a secret/key** — it is intentionally present in shortcut
read/export when the user chose to include it, which is distinct from API keys (which
are *never* exposed). Scope guards: only **typed source text** is saved (never uploaded
files, attachments, page selections, or file paths), capped at **100 000 chars**
(`MAX_SAVED_PROMPT_CHARS`), oversized **rejected** not truncated, no encryption this
slice. The backend whitelist (`_clean_saved_prompt`) is the boundary; export/import and
repair round-trip it by re-running the same normalizer.

## Local Model Manager is detection-first; direct Docker→host process spawn is rejected (2026-06-04)
The Local Model Manager (LMM) — a feature to run/use a local OpenAI-compatible model
server (llama.cpp / `llama-server`) from inside the app — is designed as a **staged,
detection-first** feature (`docs/LOCAL_MODEL_MANAGER_DESIGN.md`). **Phase 1 is
detection-only**: it checks the configured base URL, shows server status + latency,
fetches `/v1/models`, and shows a copy-able "how to start llama-server" command the
operator runs **themselves on the host** — it **never** starts/stops a process, browses
files, or takes a GGUF path. **Why detection-first:** the backend runs **inside a
non-root Docker container** (`appuser` uid 10001, `no-new-privileges:true`); Phase 1
crosses **no** container boundary and reuses primitives that already exist — the `local`
provider's base-URL resolver (`_effective_base_url`), `/models` discovery
(`_discover_openai_models`), the redaction helpers, and the `local_offline` error
category — so it is low-risk, needs no new dependency/GPU packaging, and delivers
immediate UX (is-it-up / what-models / how-to-start) at once.
**Option D — a backend-in-Docker spawning a host `llama-server` — is REJECTED.** A
container process cannot launch a process in the host PID namespace without escape
mechanisms (mounting the Docker socket, `--privileged`, host PID namespace), each of
which **destroys the security model** (Docker-socket access ≈ host root) and directly
contradicts the shipped `no-new-privileges` + non-root hardening; it is also unreliable
(PIDs/paths/GPU all live in the host namespace the container can't see) and a shell-
injection hazard. If process control is ever wanted it goes through an **optional host
companion** (Option B, Phase 2, **design-only** until sign-off) that **must** bind only
to localhost, require a token/same-user auth, accept **only** a typed/whitelisted
`llama-server` flag profile (never a free-form command, argv-array spawn only), and
restrict model files to a single user-approved, traversal-checked directory.
In-container `llama-server` (Option C) is **not** the default (GPU passthrough / image
size / model mounts / a 2 GB-limited container). **No second writer for provider
config** — base URL / default model edits stay on the existing
`PATCH /api/provider-settings/local`; the LMM status endpoints (`GET
/api/local-model/status`, `POST /api/local-model/check`) are **read-only** and return
**safe fields only** (base-URL host, reachable, latency, model count/list, default
model, a classified error, start instructions) — **no raw key, no full URL, no
userinfo** (URLs collapsed to host via `urlparse`, messages redacted + length-capped).
The next implementation slice after the design is **LMM Slice 2** (the detection-only
backend status endpoint).

## LMM Slice 2: one probing endpoint, not the design's status(cheap)/check(probe) split (2026-06-04)
The design (§4.1) sketched **two** endpoints — `GET /status` cheap/non-probing for page
open, `POST /check` for the active network probe. The implementation (branch
`local-model-status-api`, `get_local_model_status()` in `pipeline/provider_config.py`)
**collapses these into a single probing implementation**: `GET /api/local-model/status`
**does** probe (fail-fast 10 s, reusing `_discover_openai_models`) and
`POST /api/local-model/check` is a **thin alias** delegating to the same function.
**Why:** the operator opens the Local Models panel *specifically* to learn the live
state ("is my server up, what models?"), so a non-probing status would just return stale
"unknown" and force an immediate second call; one path keeps a single contract and no
duplicate discovery. The fail-fast timeout (10 s, matching fetch-models) bounds the cost,
and the DTO is identical from either route, so a future truly-cheap non-probing open can
be added later (reading the registry view) without changing the response shape. **`ok` is
deliberately decoupled from `reachable`** — `ok:true` means the status *request*
succeeded; offline / no-base-URL / malformed-URL are normal results (HTTP 200) with
`reachable:false` + a classified `error`, never a crash. Connection failures
(refused/timeout/DNS + the out-of-Docker `host.docker.internal` guard) **normalize to a
single `local_offline`** (`_classify_local_status_error`), per design §1.6 — unlike
fetch-models, which splits docker-host vs `provider_network`. The §4.2 optional
`base_url_port` was **not** added: host-only is the documented default-when-unsure, and a
bare host (via `urlparse().hostname`, which drops userinfo) is the smaller leak surface.
`actions` ships `copy_start_command` as **disabled** ("planned for a later slice") rather
than omitted — the roadmap is visible without an enabled control that does nothing
(design §5.2). The next slice is **LMM Slice 3** (the frontend Local Models panel).
