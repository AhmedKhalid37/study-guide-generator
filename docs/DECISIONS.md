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

## LMM Slice 3: Local Models panel is a Providers sub-panel + an in-page scroll link, not a nav item (2026-06-04)
The design (§5) left the panel's home open — "a sub-panel of the Providers page **or** a
sibling nav item." The implementation (branch `local-model-status-ui`,
`LocalModelsPanel.jsx` mounted at the bottom of `ProviderSettingsWorkspace.jsx`) chose the
**sub-panel inside the existing Models page**, adding **no** sixth sidebar destination.
**Why:** the panel is operational/read-only and explicitly links back to the Local
provider card for every config edit (Providers is the single writer, §5.3); putting the
status *next to* the thing it links to keeps one mental model and avoids a nav item that
exists only to show one card. The **"Edit local provider settings" action** is wired as an
**in-page scroll-to-card** (`document.getElementById("provider-card-local")` +
`scrollIntoView` + a brief cosmetic `sg-card-flash` ring) rather than a route or anchor —
this SPA has **no client-side routing/anchor support** (sections are React state in
`DesktopDashboard`), so a scroll+highlight is the lowest-risk way to honor the design's
"link to Providers ▸ Local" without inventing a router. A second non-obvious call: the
pure `localServerState` maps **not-reachable-with-no-error-info to a calm `offline`**, not
`error` — a server that simply did not answer is the expected idle state, not a fault, so
the panel stays calm; only a *classified* non-offline error (auth/model) shows the red
`error` tier. Missing/garbage status (e.g. an **old backend** with no endpoint) maps to
`unknown` + a "status unavailable" card instead of a crash. The **Copy start command** chip
stays disabled here (enabling it with the §9 profile is **Slice 4**). No new dependency —
the helpers are pure ESM unit-tested by a node harness, mirroring `shortcutStatus.js`.

## LMM Slice 4: the command helper emits static, whitelisted templates and NEVER executes (2026-06-05)
The "Copy llama-server command" affordance deferred by Slice 3 is now real, but as a
**display helper only** — it builds a command string the operator copies and runs
themselves; the app **never** executes, spawns, starts, or stops anything. The command is
served by a **read-only** `GET /api/local-model/command-profile`
(`get_local_model_command_profiles()` in `pipeline/provider_config.py`) and assembled from
a **fixed, hardcoded flag whitelist** (`_LOCAL_COMMAND_PROFILES`): each profile is an
`argv` template of literal `llama-server` flags + bounded literal values; the **only**
substitution token is `{model_path}`, which always resolves to the placeholder
`/path/to/model.gguf`. **No request input is accepted** — there is no POST, no body, no
model path from the frontend (only the placeholder string), no host filesystem read, and
**no GGUF scan**. The display `command` is rendered from `argv` via `shlex.quote` (display-
safe quoting only); `argv` is kept as the source of truth so a future host companion
(Slice 5+) can validate it without re-parsing a string. **Why a separate endpoint instead
of folding the command into `/status`:** the status DTO is a hot, frequently-probed path
and its Slice 2 shape (and test) is a stable contract; the command profiles are static and
cacheable, so a distinct read-only endpoint keeps the status response unchanged and lets
the helper load once. **Why the Slice 2 `actions[copy_start_command]` stays `disabled`:**
flipping it would break the Slice 2 status test + the Slice 3 frontend harness for no gain;
instead the panel **suppresses** that now-superseded "Planned" chip and renders the
first-class `CommandHelper` block (driven by the new endpoint), so there is exactly one
copy affordance and **zero** behavior change to `/status`. Two profiles ship
(`llama_server_default` GPU offload, `llama_server_cpu` CPU-only) to exercise the
"profiles" plural and a UI picker; `--threads`/`--flash-attn` are **deliberately omitted**
from the defaults (let llama.cpp auto-pick threads; flash-attn is version-sensitive) — the
schema can carry them later without breaking the contract. `--host 0.0.0.0` is **kept and
called out** because binding `127.0.0.1` makes the server unreachable from the container
(the #1 local-setup gotcha). Safety is enforced + tested: no subprocess/spawn anywhere
(asserted by source inspection **and** a `subprocess.Popen` monkeypatch that fails the test
if called), no raw key, host-only URL (no userinfo/port/path/query). No new dependency —
backend uses stdlib `shlex`; the frontend helpers are pure ESM unit-tested by a node
harness. The next step is **LMM Phase-1 validation / docs reconciliation** (Slice 5, the
host companion DESIGN, stays sign-off-gated).

## Ask Your Guide is a dedicated first-class workspace, not a Library-only button (2026-06-05, DESIGN)
The **Ask Your Guide** feature (`docs/ASK_YOUR_GUIDE_DESIGN.md`, Slice 1 design) is a
**dedicated top-level workspace/tab** (`AskGuideWorkspace`) alongside
Builder/Library/Styles/Providers — guide+session picker (left), chat (center),
sources/context/citations panel (right/drawer) — **not** a button hidden inside Library
or the Job Details drawer. **Why:** chatting with a guide is a distinct, repeatable task
(select a guide, ask many questions across a session, add session docs, cite sources)
that warrants its own surface, navigation, and session state; burying it in Library would
make it a one-shot afterthought and couple its lifecycle to the Library list. Library /
Job Details may **later** gain an "Open in Ask Your Guide" deep-link as an *additive*
shortcut, but the workspace remains the primary entry point. The design ships **no code**
in Slice 1 (docs-only); the workspace is built later (Slices 5–6) on top of the
backend-first slices (2–4).

## Ask Your Guide v1 is local-only with no hosted fallback (2026-06-05, DESIGN)
Ask Your Guide v1 uses the **`local` provider only** and is **status-gated** on Local
Model Manager Phase 1 (`GET /api/local-model/status`): if the local server is
`reachable:false`, chat is **unavailable** and the workspace shows a first-class offline
state reusing the `local_offline` category + the LMM **command helper** ("start it from
Local Models"). **There is no DeepSeek/Qwen/cloud fallback by default** — Ask resolves
`local`, reads **no** cloud key, and has **no** code path that silently falls through to a
paid provider. **Why:** the feature's whole point is a cost-free, private "chat with my
material" mode; silently spending on a hosted API (or leaking the user's coursework to a
cloud provider) when the local server is down would betray that intent and the app's
keys-stay-server-side posture. A hosted **"ask any provider"** mode can be designed later
as an **explicit, separate opt-in toggle** — never the v1 default and never a silent
fallback. The design stays **model-agnostic** (any OpenAI-compatible local server; no
single model hardcoded as required) and only *opportunistically* uses extra capability
the server advertises — larger retrieval pool for long-context models, a thinking pass
for thinking-capable models (reusing the existing `thinking` plumbing), multimodal
**deferred** — degrading silently when a capability is absent. Ask **reads** LMM status;
it **never** starts/stops `llama-server` (process control stays owned by the LMM / a
future host companion). Consistent with the LMM design §10 ("Ask Your Guide" note) and the
"Soft `model_hint`, not a hard pin" posture.

## Ask Your Guide requires a context manager + retrieval — never dump everything into every turn (2026-06-05, DESIGN)
Ask Your Guide must **not** be built as "send the whole guide + all attachments + all chat
history on every turn." Each turn is assembled by a **context manager** that does
**budgeted retrieval**: chunk `clean.md` (the generated guide) and `extracted.txt` (the
source, carrying `## Page N` anchors) on heading/paragraph boundaries — each chunk keeps
its nearest heading / `## Page N` as a **citation label** — build a **dependency-free
lexical index** (keyword/BM25-style scoring in pure Python; **no** embedding model, vector
DB, or tokenizer dependency added) **cached per `(job_id, content_hash)`**, then per
question select the top-ranked chunks across guide/source/extra-uploads up to a
**configurable token budget that reserves room for the answer, the system/answer-rules
block, and the recent conversation** before filling the remainder with retrieved chunks.
Older chat turns are compacted into a **rolling summary** with a recent-turn verbatim
window + pinned facts. **Why:** local models have finite (often modest) context windows
and are slow on local hardware, and — critically — **flooding the prompt with the whole
corpus *degrades* accuracy** (the relevant passage drowns in irrelevant text) and gets
monotonically worse as the chat grows; a stressed-student audience makes a confident wrong
answer the worst outcome. Budgeted retrieval keeps each turn small, fast, on-topic, and
**citable** (the model is instructed to cite **only** in-context labels; a later accuracy
slice **validates** emitted page/section references against the labels actually in context
and strips/flags any that were not — turning "no hallucinated page numbers" from a prompt
request into a checked invariant). Token counting is **approximate** (chars/4) to avoid a
tokenizer dependency; the budget is derived from the local model's advertised window when
available but defaults conservatively, and an over-budget guide **fails gracefully** ("too
large for this model — use a longer-context model or ask a narrower question") rather than
silently truncating away the cited passage.

## Ask Slice 2: `/api/ask/jobs` lists only eligible guides; context is whitelist-redacted and 404s only on a missing job (2026-06-05)
The Ask context-inventory endpoints make three deliberate contract choices that later
slices and the frontend will rely on. **(1) Eligibility filters, it does not flag.**
`GET /api/ask/jobs` returns **only** jobs that have a generated `clean.md` — a guide-less
/ failed / incomplete job is **omitted from the list**, not returned with an
`eligible:false` marker. The design ("list eligible guides") and the product framing (a
guide *picker*) both want a clean pickable set, and a future "why can't I ask this job?"
affordance belongs on the per-job context endpoint, not as noise in the picker.
**(2) The per-job `…/context` endpoint 404s only when the *job* does not exist** (via the
existing `_get_job` guard); an existing-but-guide-less job returns **200 with
`readiness.ready=false`** + a human reason, never a 404 — so the frontend can show "this
job has no generated guide yet" instead of treating it like a missing route. **(3)
Redaction is by construction, via the existing job-listing helpers + an explicit field
whitelist.** Both routes run the manifest through the same `_safe_manifest` /
`_safe_attachment_metadata` / `_attachment_summary` / `_safe_page_selections` helpers the
job listing already uses, and then emit only a hand-listed set of display fields —
**nothing from the manifest is passed through verbatim.** A thin read-only reader
`pipeline/ask_inventory.py` supplies counts only (guide/source char + heading + `## Page N`
anchor counts) and **never returns a guide/source body**. **Why:** this keeps the leak
surface closed even if a manifest later gains a new secret-ish field (it simply won't be in
the whitelist), avoids inventing a second jobs registry, and matches the LMM/provider
redaction posture. Slice 2 stays strictly read-only — it never writes, never calls
`save_clean_md`, never creates a job, makes no model/local-model call, and does no
chunking/retrieval (those are Slice 3+).

## Ask Slice 3: cache at `jobs/<id>/ask/cache/`, content-hash key, paragraph-boundary chunks (no overlap) (2026-06-05)
Ask context preparation (`POST /api/ask/jobs/{id}/prepare`, `pipeline/ask_context.py`)
makes four deliberate, non-obvious choices that Slice 4 retrieval will rely on. **(1)
Cache lives at `jobs/<job_id>/ask/cache/context_index.json`** — co-located with the job
(so the existing trash/purge model removes it with the parent job), fenced inside the job
dir (`_ensure_fenced`), and written atomically (temp file + `os.replace`, mirroring
`provider_settings_store`/`library_store`). It is **safe to delete/rebuild** and is the
on-disk layout the design §7 left open. **(2) The cache key is a sha256 over the actual
`clean.md` + `extracted.txt` *content* (length-delimited, `None`-source distinct from
empty), never timestamps** — so an edited guide/source re-prepares and an unchanged one is
a `hit` that rewrites nothing; a *format* bump is handled by a separate `version` field
(kept OUT of the content hash) and a corrupt/stale cache rebuilds safely instead of
crashing. **(3) Chunking is deterministic with NO overlap in v1** — split on markdown
heading boundaries (guide) / `## Page N` anchors (source), then greedily pack paragraphs up
to a ~650-token target (`chars/4`, no tokenizer dep) with an ~800-token hard ceiling; a
single oversized paragraph hard-splits at the ceiling. The design permits "small overlap
when useful," but v1 omits it because paragraph/heading boundaries already give clean,
**exact** citation labels (nearest heading / `Page N`) and predictable chunk counts;
overlap can be added later without changing the contract. **(4) The cache *file* may hold
chunk `text` + per-chunk term frequencies + `doc_freq` (Slice 4 retrieval needs them), but
the *prepare response* never does** — it returns an explicit whitelist (counts +
content_hash + a bounded citation summary + a *job-relative* `cache_relpath`), and the
cache is built **only** from the two plain-text artifacts (never the manifest), so no key /
full URL / host path / unrelated manifest field can enter either surface. **Why:** keeps
the leak surface closed by construction, keeps retrieval cheap and deterministic, and keeps
re-opening a guide a cache hit rather than a re-chunk. Slice 3 stays strictly backend +
read-only over originals — no model/local-model call, no key read, no sessions, no UI, no
new dependency, and it never writes `clean.md`/`extracted.txt`/`job.json` or calls
`save_clean_md`.

## Ask workspace shell is inserted before backend chat/session complexity (2026-06-05)
After Ask Slice 3, the original plan pointed directly at backend local chat. We
intentionally inserted a frontend/product shell slice first: top-level `Ask Guide`
navigation, guide picker, context inventory, prepare-context readiness, local-model
status, and a disabled chat placeholder — **without** sessions, message endpoints, or
model calls. **Why:** seeing the real workflow before committing to the session/message
API prevents awkward API/UX coupling. The shell makes the product sequence explicit
(select guide → inspect readiness → prepare context → verify local model → chat later),
surfaces the exact empty/offline/not-ready states the backend must support, and lets the
next backend slice target the UI's real needs instead of a speculative route contract.
The security posture also becomes visible early: the UI only renders summary fields,
defensively basenames attachment/page-selection names, and never displays raw guide/source
text, chunk text, keys, full URLs, or host paths. After this inserted slice, NEXT returns
to the backend local chat endpoint.

## Ask backend chat synchronously prepares context and stores sessions under the job (2026-06-05)
The backend local chat API uses `jobs/<job_id>/ask/sessions/<session_id>/` with
`session.json` (atomic write) and `history.jsonl` (append-only) for v1 chat sessions.
Session ids are opaque `ask_<uuidhex>` values, lookup scans only the job-local Ask
session areas, and path checks fence every resolved session under its parent job.
**Why:** co-locating chat with the parent job means trash/purge lifecycle remains simple,
no global session index is needed for a single-operator tool, and existing exports do not
include chat files unless a future explicit export-chat feature is built.

For `POST /api/ask/sessions/{id}/message`, the backend synchronously calls
`ask_context.prepare_context(job)` before loading the index. **Why:** this keeps the
message endpoint self-contained and resilient to a missing/stale/corrupt cache while only
writing the already-designed Ask cache area; it never rewrites `clean.md`,
`extracted.txt`, or `job.json`. Returning `not_prepared` instead would require extra UI
state handling for the common "first message after opening a prepared-looking guide"
case. If preparation becomes slow for very large guides, a later slice can move this to
an explicit async preparation state without changing the session storage contract.

The chat slice also masks obvious `sk-*` keys, Authorization bearer headers, and full
`http(s)://` URLs before Ask cache/session persistence and Ask responses. **Why:** Slice
3 intentionally stored chunk text for retrieval, but the stronger project-wide rule is
that raw keys and provider base URLs must not appear in cache/index/history files. This is
a defensive boundary mask, not semantic source editing; citation labels, counts, and term
frequencies still come from the redacted text. Full emitted-citation validation is
deferred: v1 returns the machine-readable list of citation labels actually provided to the
model and never fabricates labels server-side, while a later accuracy/polish slice can
parse model-emitted citations and flag or strip labels outside that allowed set.

## Ask chat UI uses explicit prepare and lazy session creation (2026-06-05)
The frontend chat wiring keeps **Prepare Context** as an explicit prerequisite before the
composer enables, even though the backend message endpoint can synchronously prepare/reuse
the cache. **Why:** explicit preparation makes the readiness/cost boundary visible in the
three-region Ask workspace, keeps the first chat send predictable, and preserves the
existing context panel flow rather than hiding a potentially slow cache build behind a
message submit. If a stale/missing cache still appears at send time, the backend remains
self-healing and the UI shows a prepare action.

Sessions are created **lazily on first send** instead of immediately when a guide is
selected. After `POST /api/ask/jobs/{id}/sessions`, the UI immediately loads the session
with `GET /api/ask/sessions/{session_id}` and stores only safe session metadata plus
bounded message history in React state. **Why:** guide selection remains a read-only
inspection action, switching guides does not create empty session directories, and the
chat state starts only when the user actually asks a question. No chat is persisted to
browser storage; session/history persistence remains server-side under the parent job.

## Ask emitted citations are sanitized, not fabricated or rejected (2026-06-05)
The Ask chat polish slice validates only bracket-style citations that look like the
backend's Ask labels (`Guide ...` / `Source ...`) against the exact labels retrieved for
that turn. If the model emits an unsupported Ask-looking label, the backend strips that
citation from the returned/stored answer and reports it in `citations_unsupported` plus
`citation_validation`; normal bracketed prose that does not look like an Ask citation is
left untouched. **Why:** rejecting an otherwise useful local answer is too disruptive,
but turning a hallucinated page/section into a trusted chip would violate the accuracy
contract. Stripping + reporting keeps the answer readable, prevents fabricated source
chips, and gives the UI a subtle warning without pretending the backend can repair the
model's citation. This is intentionally a small deterministic matcher, not a broad
citation parser.

The frontend also uses a tiny inert answer renderer for the subset the local model
commonly emits: headings, bold, lists, line breaks, and fenced blocks. It returns React
text nodes from normalized helper data, never `dangerouslySetInnerHTML`, and adds no
markdown dependency. **Why:** the Ask UI needs readable answers now, but a full markdown
pipeline would widen dependency/security surface for a narrow chat-polish slice.

## Ask session clear/delete semantics are conservative and job-local (2026-06-05)
Ask session management keeps the same job-local storage model:
`jobs/<job_id>/ask/sessions/<session_id>/`. Listing sessions is scoped to one selected
guide and sorted by `updated_at` / `created_at` newest first, with only safe summaries
(ids, timestamps, message count, and a redacted bounded last-message snippet). **Why:**
this gives the UI enough context to switch chats without returning full answers, prompts,
chunk text, paths, provider URLs, or secrets.

`DELETE /api/ask/sessions/{id}/history` clears only `history.jsonl`, keeps
`session.json` and the same session id, updates `updated_at`, and leaves
`jobs/<job_id>/ask/cache/context_index.json` untouched. `DELETE /api/ask/sessions/{id}`
removes only the fenced session directory under that job's `ask/sessions` root; it never
deletes guide/source artifacts, the shared context cache, other sessions, or anything
outside the job tree. **Why:** clear history is a reversible-feeling reset of the chat
conversation, while delete is the explicit removal of one chat container. Keeping the
prepared context cache avoids making session cleanup unexpectedly expensive and preserves
the existing "prepare once, reuse" workflow.

## LMM Phase 2 process control uses a host companion; scanning is approved-root only (2026-06-06, DESIGN)
Local Model Manager Phase 2A (`docs/LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md`) makes the
host companion the only acceptable path for future in-app local model process control.
The Docker backend must **never** directly spawn, stop, or manage host processes, and
must not gain host powers through the Docker socket, `--privileged`, host PID namespace,
or other container escape mechanisms. **Why:** the backend runs inside a hardened
non-root Docker container; direct host process control crosses the container-host
boundary, breaks the deployed security model, and would require unsafe privileges or
unreliable filesystem/PID assumptions.

The future architecture is React UI -> Docker FastAPI backend -> Unix-socket-first,
token-authenticated host companion -> approved model directory scan -> host
`llama-server` process lifecycle. The React UI never talks directly to the companion.
The backend reads the companion connection config and token from server-side config
only and never returns the token, socket path, or raw connection details to the
frontend. For Linux Docker, Phase 2 control transport is Unix domain socket first:
the companion listens on a socket file under a user-owned runtime directory, and
Docker Compose later mounts only that socket file or containing runtime directory
into the backend container. Socket permissions restrict access; token auth remains
defense-in-depth unless deliberately dropped by a later accepted design.

Host-gateway TCP is an explicit alternative requiring operator sign-off: the
companion must bind only to a Docker-reachable host interface or Docker bridge
gateway, never public `0.0.0.0`; firewall rules must restrict access to Docker bridge
subnets; and token auth is required. Host networking is another explicit alternative
where container `127.0.0.1` reaches the host listener, but it is not the default
because it changes Docker deployment/security. Pure host desktop/native packaging is
a later option where backend and companion run under the same host user. A
`127.0.0.1`-only companion control API is therefore **not** assumed reachable from
Docker unless host networking/native packaging is used.

`llama-server` may still bind `--host 0.0.0.0` for the model `/v1` API so Docker can
reach it; that is separate from the companion control API, which must never be
exposed publicly. Direct Docker-to-host process spawn remains rejected, as do Docker
socket access, privileged containers, host PID namespace, and whole-PC scanning.

Model scanning is limited to one or more explicit user-approved model roots. There is
no whole-PC scan, no home-directory scan by default, and no arbitrary path search from
Docker. The companion canonicalizes approved roots and candidate files, accepts only
`.gguf` candidates, rejects traversal outside approved roots, and must document/test a
safe symlink policy: reject symlinks, or resolve them and require the resolved path to
remain inside an approved root. The frontend should receive safe model records with an
opaque model id or root-relative display path, not unnecessary absolute host paths.

Start/stop uses whitelisted `llama-server` profiles: selected model id plus profile id
plus typed bounded parameters such as context size, GPU layers, port, and maybe threads.
There are no free-form args in v1, no shell string execution, and no `shell=True`; the
companion builds an argv array from fixed profile rules. The companion may stop only the
tracked process it started and must not kill unrelated manually-started
`llama-server` instances. Logs are bounded and redacted. Phase 2B, if pursued, should
prototype approved-folder scanning only using the chosen transport contract;
start/stop comes later after the companion boundary is accepted.

## LMM Phase 2F start/stop/restart is companion-owned, typed, tracked, and redacted (2026-06-06, DESIGN)
Local Model Manager Phase 2F (`docs/LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md`) fixes the
safe contract for future `llama-server` process control before implementation. Future
start/stop/restart remains **host-companion-owned**: the Docker backend must never
become a host process manager, must never use the Docker socket, `--privileged`, host
PID namespace, direct Docker-to-host spawn, or a frontend-supplied executable/model
path to control host processes. The React UI still never talks directly to the
companion and never receives the companion token, socket path, Authorization header,
raw companion connection details, or raw absolute host model paths. Linux Docker
control remains Unix-socket-first and token-authenticated.

Start requests may contain only a selected companion `model_id`, a whitelisted
`profile_id`, and typed bounded parameters such as `port`, `ctx_size`, `gpu_layers`,
`threads`, and optional `batch_size`. They must not contain shell commands,
free-form flags, arbitrary executable paths, raw model paths, environment blocks, or
anything that can be appended to a command line. The companion resolves `model_id`
against the approved-root GGUF library, canonicalizes the configured executable,
checks execute permission, converts the profile and parameters into an argv array,
and never uses `shell=True`. Initial profiles are `gpu_default` and `cpu`, with
`low_memory` deferred until validated.

Stop requests may only target the process the companion started and still tracks.
The companion records restricted process state: PID, process start time, executable
identity/path, model id/root id, profile id, port, typed params, started timestamp,
last health check/error, log path, and redacted argv metadata. Before reporting
running or sending a signal, Linux-first implementation must verify identity through
PID existence, executable/command match where possible, recorded process start time
via `/proc` where available, and expected port health. If the PID is stale, reused,
foreign, or uncertain, the companion must not kill it; state becomes `unknown` or is
cleared safely. Manually started `llama-server` processes are never adopted or
killed in v1. Restart is stop-then-start and accepts either a full validated start
payload or `reuse_last: true` only when stored launch metadata still validates.

Port conflicts fail safely with `port_in_use`; a manually started server on `8080`
may make the local provider reachable, but it is not a companion-managed process.
Logs are companion-owned, bounded, non-world-readable, and redacted for tokens,
Authorization headers, credentialed URLs, socket paths, and absolute model paths;
no unbounded log streaming ships in the first process-control implementation.
Companion health checks poll the host model API, for example
`http://127.0.0.1:<port>/v1/models`, to mark the companion-managed process running.
This operational state is not a Provider Settings source of truth, and no future
start/stop slice may write Provider Settings or change Ask unless a later explicit
decision and implementation slice says so.

## LMM Phase 2G5 real launch is explicit-config only and readiness-gated (2026-06-07)
Real Linux `llama-server` lifecycle support remains opt-in through explicit host
companion config. The app ships no default runnable real executable path. A
frontend/backend request can name only a whitelisted configured profile id, an
approved-library model id, and typed bounded parameters; it can never provide an
executable path, raw model path, shell command, free-form args, or environment block.
**Why:** this preserves the Phase 2 host-process boundary while allowing real runtime
validation on an operator machine.

`running` now means the companion's host-side readiness probe succeeded against
`http://127.0.0.1:<port>/v1/models`; successful `Popen` alone is only `starting`.
Readiness timeout, early process exit, load failure, OOM-like logs, permission
failure, missing executable, and port conflict become stable safe error/crash states
with no automatic restart loop. Launch uses a new Linux process session/group, and
stop signals only the verified process group the companion started after PID identity
checks. **Why:** real model loads can fail slowly or crash after spawn, and reporting
them as running would mislead the UI/backend; process-group tracking is needed to
clean up real child processes without killing manually-started or reused-PID
processes.

## LMM Phase 2G7 `.ini` profile presets import defaults only into the whitelist schema (2026-06-07)
Profile preset files are optional companion-side inputs, never frontend-provided.
The companion JSON names preset files with `profile_preset_files` and supplies the
shared `llama_server_executable`; preset files cannot provide executable paths,
model paths, commands, args, shell fragments, environment expansion, or free-form
flags. Imported sections become normal `llama_server` profiles through the same
typed whitelist/profile schema used by JSON-backed profiles.

Unknown preset keys are rejected rather than ignored. Integers, booleans, enums,
ranges, duplicate ids, `DEFAULT` values, and shell/path-like text are rejected at
config load. **Why:** rejecting unknown keys makes an operator typo or malicious
preset obvious and keeps every imported value from becoming anything other than a
typed bounded profile default. The slice also adds Linux-first operator setup docs;
it does not add app-suggested settings, Provider Settings writes, Ask changes,
permanent Docker changes, host-gateway TCP, Docker socket, privileged containers,
host PID namespace, or token/socket/path/raw argv exposure.

## UI reskin: replace the Claude-style baseline with the new dark design system (2026-06-08)
The visual baseline is moving off the Claude-style UI to a new dark design system
("GuideForge"), captured as a token block (`:root`) plus component classes
(`.panel`, `.stat-card`, `.item-card`, `.pill-*`, `.nav-item`, `.hero`, `.btn`,
`.chip`, `.field`, …) in `frontend/src/design-system.css` (renamed from the former
`src/styles.css`, which previously held the Claude-style global stylesheet).
**This is a visual-only reskin: no route, API, state, or component-logic changes.**
**Why:** a single owned design system in one file keeps colors/type/geometry
consistent and makes `:root` the single source of truth — `tailwind.config.js`
references `var(--…)` rather than re-typing hex, so Tailwind utilities and the
component CSS can never drift.

Slice 1 (this commit) is **foundation only**: install the fonts
(`@fontsource-variable/newsreader`, `@fontsource-variable/inter`,
`@fontsource/geist-mono`) and wire them + `design-system.css` into the entry
(`main.jsx`); the `:root` `--serif`/`--sans` tokens lead with the
`"… Variable"` family names the fontsource-variable packages actually register,
keeping the plain/system names as fallbacks. `theme.extend` **adds** var-backed
`colors`/`fontFamily`/`borderRadius` tokens but **retains** the legacy
`navy`/`ember` palette and ember/navy shadows for now — removing them would inert
~160 existing component class usages. The legacy palette is removed per-component
in later reskin slices, not here. The app is expected to look **partially
restyled** at this stage. No second/global Claude stylesheet remained to remove —
its former file (`src/styles.css`) was already overwritten by the design system
before this slice and is renamed here to `src/design-system.css`.

## Shell deviates from the reference: bigger nav labels + collapsible sidebar (Slice 3.5)
Two intentional departures from the pixel-faithful reskin reference image, both
shell-only (no route/API/workspace-logic change):

- **Nav label size bumped** one step up the type scale — `.nav-item` font-size
  `14.5px → 15.5px` (uppercase section labels `GENERAL`/`TOOLS · RESOURCES`/
  `SETTINGS` deliberately left at 11px). **Why:** at 14.5px the primary nav read
  slightly small against the new serif headings and topbar; 15.5px balances the
  hierarchy without touching row height or icon gap.
- **Collapsible sidebar added** — a chevron toggle in the brand row collapses the
  rail to an icon-only `~72px` (`.app.is-collapsed` swaps `--sidebar-w`
  `272px → 72px`, animated via a `grid-template-columns` transition). State lives
  in `DesktopDashboard` (`useState`) and is persisted to `localStorage`
  (`gf:sidebar-collapsed`, default expanded). Collapsed mode hides the wordmark
  (logo kept), hides section labels (hairline divider instead), centers nav icons,
  drops the dark-mode switch + profile text, and reduces Sign Out to its icon.
  **Why:** the reference has no collapse affordance, but an icon rail is a standard
  desktop-shell expectation and reclaims width for the workspaces. **Accessibility:**
  collapsed labels stay in the DOM as visually-hidden (`sr-only`) text so each
  control keeps its accessible name; a native `title` adds a hover tooltip; the
  toggle carries `aria-label` + `aria-expanded`; the active item stays highlighted.

## Larger default UI density baseline (Slice 5b)
GuideForge intentionally ships a **larger default UI density / type scale**: at
browser **100%** zoom the app now visually matches what it previously felt like at
**125%** zoom. The base type scale in `design-system.css` was raised ~1.2× and the
load-bearing control dimensions (sidebar width, nav/brand/toggle/avatar sizes,
icon buttons, the Generate/progress button, and the collapsed icon rail) were
bumped proportionally so nothing looks under-scaled against the larger text.

**Why this mechanism (real values), not `transform: scale()` or CSS `zoom`:** the
app shell is a full-bleed `100vw/100vh` grid. `transform: scale()` would blur
text, leave the original (unscaled) box occupying layout space, and throw off
hit-target/click coordinates. CSS `zoom` magnifies a `100vw/100vh` root past the
viewport (horizontal/vertical overflow), breaks `position: fixed` overlays
(modals/drawers), and distorts `vh`-based max-heights. Scaling the actual
design-system font/control/spacing tokens keeps layout, overflow, fixed overlays,
and hit targets correct.

**Forward rule:** future reskin slices build **against this larger baseline** —
do not shrink components back down to the pre-5b sizes to "fit" a reference image;
re-derive spacing from the current density instead.

## Tailwind utilities are inert in the built app — use real semantic CSS (Slice 5b)
**Finding:** Tailwind utility classes (`flex`, `grid`, `h-12`, `object-contain`,
`bg-[#…]`, etc.) produce **no CSS** in the running app. `design-system.css` is the
only imported stylesheet and it contains **no `@tailwind base/components/utilities`
directives**, so PostCSS/Tailwind never emit a utility layer into the built
bundle (verified: the built `index-*.css` has zero `.flex`/`.grid`/`.object-contain`
rules). Components authored purely in Tailwind utilities therefore render as raw,
unstyled HTML (this is what made the pre-5b Job Details drawer / Customize
Shortcuts modal / preset-logo `<img>` sizing look broken).

**Why it matters:** the whole reskin runs on the semantic `sg-*`/component classes
in `design-system.css`; leftover Tailwind utilities are dead weight, not styling.

**Forward rule:** reskin work must use **real semantic CSS classes** in
`design-system.css` (layout included — `display:flex/grid`, gaps, sizing), and must
not assume any Tailwind utility "just works." Do **not** rely on Tailwind for new
visual work unless the Tailwind pipeline is **deliberately restored** (add the
`@tailwind` directives to an imported stylesheet + confirm the utility layer is
emitted) as its own explicit, separately-reviewed slice.

## Eval harness uses JSON golden specs and a deterministic-only scoring spine (Slice 20)
The first guide-quality eval harness (`test_scripts/eval/`) is deliberately a
**deterministic measurement spine**, not a generation improvement. It scores guide
Markdown using only the pure Slice 18 math verifier, the Slice 19 linter, and
simple normalized string checks (concept coverage, must-not-claim) — **no**
LLM-judge, **no** embeddings/LanceDB, **no** retrieval/OCR. Establishing a stable,
reproducible baseline first gives every later (fuzzier, model-based) metric a fixed
reference to compare against, and keeps the harness runnable offline with no
provider keys, no Docker, and no network.

**Spec format = JSON, not YAML.** PyYAML is importable in the host env, but JSON is
in the standard library, so JSON specs run identically on the host and inside the
non-root Docker image with zero added dependency — the same dependency-free stance
that led Slice 18 to decline SymPy. A `.yaml`/`.yml` loader is offered only when
PyYAML happens to be present; the committed golden specs stay `.json`.

**Scope guardrails (must hold for this phase):** the harness must not touch
generation prompts, provider behavior, `/api/jobs/llm` fields, the Builder/
JobDetails UI, or job artifacts, and must not integrate the math verifier / guide
lint into `validation.json`. Offline mode never calls the API; the optional live
mode uses only the existing **no-provider** `/api/jobs/paste` endpoint, records only
the API host (never a full URL), and writes results solely under its output dir.
Every result is scanned for credential-looking field names/values and the write is
**blocked** on a suspected secret. Generated result `*.json`/`*.csv` are git-ignored
(only fixtures/specs/READMEs are tracked); large eval inputs go under the git-ignored
`test_scripts/eval/inputs/`.

**Regression comparison is keyed on `(spec_id, mode, guide)`** so a run is compared
against the last time *that same guide* was scored — never a different guide that
shares the spec — and it is **non-blocking** in this phase (a regression reports a
delta, it never fails the run).

## Source page citations use compact `p.` / `pp.` form when `## Page N` anchors exist
Slice 23B adds an automatic source page-citation directive only when source text
contains extraction-style `## Page N` anchors. The directive prefers compact
citations such as `(p. 3)` and `(pp. 3-5)`, tells the model to cite source pages
for factual claims/examples/formulas/definitions where possible, and tells it to
cite only pages that appear as anchors.

**Why this replaces the older `(page N)` prompt style:** the previous optional
`slide_page_references` include-section fragment explicitly banned `p.` / `pp.`
forms to reduce inconsistent page references in PDFs. Slice 23B makes compact
citations the product-level source-citation style, so leaving the old fragment in
place would create contradictory instructions whenever that toggle and anchored
source text were both present. The fragment is therefore aligned to the compact
style. The source-driven directive remains conditional so the no-anchor default
prompt baseline is unchanged.

**Checker scope:** page-citation plausibility is advisory and offline/test-only.
`pipeline.guide_lint` can warn when supplied available source pages are missing
from a cited `p.` / `pp.` / `page` reference, but it is not wired into live
generation, job artifacts, UI, `validation.json`, or `math_verification.json`.

## Ask retrieval baseline measures the full ranking, weaknesses stay non-blocking
Slice 25A adds an offline relevance harness (`test_scripts/test_ask_retrieval_relevance.py`)
that measures the *current* local-only lexical (tf-idf) Ask retrieval before any
embedding/reranking work. It reuses the real boundary —
`ask_context.prepare_context`/`load_index` to build the index and
`ask_sessions._score_chunks`/`retrieve_chunks` to rank — over a synthetic fixture
written into a temp job dir, so no `jobs/`/`library/`/`config/` is touched and no
server/model/provider is needed.

**Why rank/MRR are computed from `_score_chunks` (the full ranking) rather than only
the budgeted `retrieve_chunks` output:** the budgeted public retrieval truncates by
token budget + `MAX_RETRIEVED_CHUNKS`, which would make `rank`/`mrr` depend on budget
tuning instead of the underlying relevance ordering. The baseline reads the full
deterministic ranking for `rank`/`reciprocal_rank`/`mrr`, and *additionally* runs the
real budgeted `retrieve_chunks` to record what production would actually hand the
model — both are reported.

**Why the paraphrase case is `known_weakness: true` and non-blocking:** a query with no
shared keywords ("model memorizes the training data…") is exactly where lexical tf-idf
is weakest. The harness records its real rank honestly (it drops to rank 5, behind
unrelated sections, vs rank 1 for keyword queries) instead of engineering the fixture
to force a pass or a miss. Blocking pass/fail covers only the keyword/source-marker
cases; the weakness is reported as the motivation for future semantic retrieval, not a
regression. The harness adds no LanceDB/embeddings/vector-DB/reranking/new dependency
and changes no Ask runtime, prompt, route, UI, or artifact behavior.

## Ask index version bump on lexical-hygiene change (Slice 25B)
Slice 25B introduced stopword filtering + conservative plural folding into Ask
retrieval via a shared `pipeline/ask_lexical.py::lexical_terms`, used by **both** the
index build (`ask_context`) and the query scorer (`ask_sessions`). The cached index
shape is unchanged (still `terms` + `doc_freq`), but the *contents* of those maps are
now normalised differently than a Slice-25A (v1) cache.

**Why `INDEX_VERSION` is bumped `1 → 2` rather than left alone:** an index built with the
old tokeniser stores un-normalised, stopword-laden terms; a query scored with the new
tokeniser produces stopword-filtered, plural-folded terms. Scoring a new-style query
against an old-style index would silently mismatch (e.g. query `weight` never matching
indexed `weights`), degrading retrieval without any error. Bumping the version makes
`_cache_valid` reject any v1 cache so `prepare_context` rebuilds it automatically on the
next call — no user action, no manual cache deletion, and no possibility of mixing the
two tokenisations. The version lives outside `content_hash` (which still reflects only
guide/source content), so the bump invalidates caches purely on format, as intended.

**Why a single shared `lexical_terms` for index *and* query:** the index/query tokeniser
must be identical or retrieval breaks; centralising it in one module (instead of the
previous duplicated per-module `_TERM_RE`) makes that invariant structural, and a focused
test asserts `ask_context._term_freqs == ask_sessions._terms == lexical_terms`.

**Why plural folding is single trailing `-s` only (no `-es`, no `-ing`/`-ed` stemming):**
the goal is for a singular and its regular plural to fold to the *same* stem so a query
matches the index. A single `-s` strip does that for the common `word + s` case
(`example`/`examples`); an `-es` rule would map `examples → exampl` while `example →
example`, breaking the symmetry it was meant to create. Verb-tense stemming was rejected
because it mangles technical tokens (`string → str`, `based → bas`) for little gain. The
result stays deterministic and explainable, and the recorded paraphrase weakness improved
rank 5 → 1 on the fixture purely from removing function-word noise — but it is kept
`known_weakness: true` because that win is still lexical overlap, not semantics.

## guide_lint.json lints clean.md without expected_sections / source pages (Slice 27)
Slice 27 persists a per-job `guide_lint.json` advisory artifact, mirroring the Slice 21
`math_verification.json` contract (advisory-only, never fails/changes job status, never
blocks render, downloadable by exact name, not surfaced in generic artifact lists/UI).
The lint runs in `run_raw_markdown_pipeline._write_guide_lint`, against the final
sanitized `clean.md`, immediately after `_write_math_verification`.

**Why `expected_sections` is not passed:** `guide_lint`'s `expected_sections` matches
against the document's emitted headings, but the only section information persisted on a
job is the manifest's `include_sections` — canonical *toggle keys* (e.g. `key_concepts`,
`practice_questions`), not the heading text the LLM actually writes. Normalising those
keys and matching them against headings would produce unreliable, mostly-false
`missing_section` warnings. Surfacing real expected headings is left to a later slice
rather than shipping a noisy check now.

**Why `available_source_pages` is not passed:** the optional page-citation plausibility
check needs the source page anchors (`## Page N`) from the extracted source text, which
is not reliably reachable at this pipeline point without invasive source-text plumbing
and does not exist at all for paste / Markdown-upload jobs. To keep the slice small and
non-invasive the check stays disabled; all other rules plus the existing Node/KaTeX
render bridge still run (the bridge already degrades to an info finding when Node/KaTeX
is unavailable, so it never crashes the helper). Both omissions are recorded in
`CURRENT_TASK.md` so the next slice knows what to wire.

## Hybrid OCR architecture designed before any OCR code (Slice 29)
Slice 29 is a **docs-only** architecture decision for hybrid OCR / scan-aware
extraction, captured in `docs/HYBRID_OCR_DESIGN.md`. It deliberately decides the
shape before adding Mistral OCR, an OCR provider boundary, or any extraction
behaviour change, so the follow-on slices (30–36) stay small and verifiable.

**Why design-first:** OCR touches the load-bearing extraction path
(`pipeline/extract.py`), the Slice 24A `extraction_metadata.json` contract, the
large-PDF preflight, and (for cloud OCR) the security/privacy boundary. Each is a
place where a casual change regresses behaviour or leaks secrets, so the sequencing
and invariants are fixed up front rather than discovered mid-implementation.

**Why page classification is additive/advisory, not a `method` replacement:** the
Slice 24A artifact already ships a per-page `method` ∈ `{embedded_text, ocr, none}`
with `_safe_method` whitelisting `{embedded_text, ocr, none, unknown}`. The richer
classification (`embedded_text`, `ocr_fallback`, `likely_scanned`,
`blank_or_low_text`, `mixed`, `error`) is layered **next to** `method` so existing
consumers keep working; classification is never required and unknown values coerce
safely. The schema bump to `version: 2` happens only when a new field actually
ships, and `version: 1` keys keep their meaning forever.

**Why cloud OCR is opt-in and off by default:** cloud OCR sends page images
off-box and costs money. Defaulting to local-first (Tesseract or skip-and-warn)
preserves the app's local-first posture (cf. Ask Your Guide staying local-only),
and the routing order is embedded-text → local OCR → cloud OCR (cloud last), with
page-budget caps via the existing preflight + page-range model. OCR stays
degrade-not-fail: it can never fail a job, block render, or change job status —
the same advisory posture as `extraction_metadata.json`, `math_verification.json`,
and `guide_lint.json`.

**Why Mistral OCR is prerequisites-only here:** its current API endpoint/format,
supported file types, page limits, pricing, output shape (Markdown/text/layout?),
rate limits, privacy/retention terms, and error behaviour must be verified against
official docs at implementation time, not assumed. A dedicated docs-only
verification slice (Slice 35) gates the actual provider implementation (Slice 36).

**Open decision deferred to implementation:** whether OCR provider keys reuse the
existing provider registry/secret store or get a dedicated `ocr_provider_settings`
store — either way they follow the established server-side-only, write-only,
key-less-DTO invariant (only `configured`/`key_source`/`key_hint`/`base_url_host`).

## Slice 30 — `extraction_metadata.json` bumped to `version: 2` for additive PDF visual signals
Slice 30 adds optional, advisory-only per-PDF-page visual/object signals
(`image_object_count`, `drawing_object_count`, `has_images`, `has_drawings`,
`page_width`, `page_height`, and an optional `visual_warnings` list) and bumps the
artifact from `version: 1` to `version: 2`. **Why bump now and not stay on v1:** the
Slice 29 design fixed the rule "keep `version: 1` readable forever; bump to
`version: 2` the moment the *first* new field actually ships." Slice 30 is that
moment, so the writer now emits `version: 2`. The bump applies to **both** the
`completed` and `skipped` payloads so a single writer version describes the whole
artifact; the `skipped` shape itself gained no fields. **Why this is safe for v1
readers:** the new fields are purely additive and optional — all v1 keys remain
present with identical meaning, and a reader that ignores unknown keys (or treats
missing new keys as "not measured") is unaffected. **Why the fields live behind
`_safe_page` / `_pdf_visual_signals`:** the sanitiser still whitelists fields, so
the new keys are individually coerced (non-negative int counts, finite
non-negative float dimensions, `None` for unknown) and smuggled keys (paths, image
bytes, auth-like names) are still stripped. Collection is **degrade-not-fail**:
each PyMuPDF probe (`get_images` / `get_drawings` / `rect`) is independently
guarded and falls back to `None` plus a safe `visual_warnings` category, never an
exception, never extraction-text/mode/method/job-status change. This slice
**only collects data** — page classification (Slice 31) and any OCR routing remain
deferred; no classification field is emitted yet.

---

## Slice 31 — advisory page classification stays on `version: 2` and is computed at the sanitiser, not the extractor
Slice 31 adds three advisory per-PDF-page fields — `classification` (closed enum),
`classification_reasons` (whitelisted tokens), and `ocr_recommended` (bool hint) —
derived from the Slice 24A text/word/method signals plus the Slice 30 visual
signals. Two non-obvious choices:

**(1) No version bump — stays `version: 2`.** The Slice 29 rule is "bump once when
the *first* new field ships, then keep all prior keys present and meaning the
same." Slice 30 already performed that single bump (1 → 2). Slice 31's fields are
again purely additive/optional, so re-bumping to `version: 3` would churn the
version for no compatibility benefit and wrongly imply a breaking change. A reader
that treats missing/unknown keys as "not measured / unknown" is unaffected, which
is exactly the contract `_safe_classification` (unknown fallback, mirroring
`_safe_method`) preserves. So the rule is read as "bump on the first additive
field, not on every additive field."

**(2) Classification is computed in `extraction_metadata._safe_page` (the
sanitiser), not in `extract.py` at extraction time.** It reads only the
*already-sanitized* numeric/method/visual fields and **never** any upstream
`classification`/`classification_reasons`/`ocr_recommended` key on the incoming
page record. **Why:** this makes a smuggled or hostile classification value
impossible to persist by construction — the value is always recomputed from
clean, bounded inputs and re-whitelisted (`_safe_classification` +
`_safe_reasons`). Computing it in the extractor would mean the value flows through
the artifact path and would have to be re-validated anyway; doing it once at the
normalisation boundary keeps a single deterministic source of truth and keeps the
extractor's hot loop unchanged. `_classify_pdf_page` is **degrade-not-fail**: any
unexpected input returns `classification: "unknown"` +
`["classification_unavailable"]`, and the persisted value is *always* in the
closed vocabulary.

**Thresholds (conservative, documented):** "meaningful text" mirrors
`extract._is_meaningful_page_text` (≥40 chars **OR** ≥5 word tokens) so the
advisory label agrees with the extractor's own per-page text/OCR decision;
"near-zero" is stricter (<10 chars **AND** <3 words) to separate a genuinely blank
page from a sparse one. A low/zero-text page is only `likely_scanned` when an
image/drawing object is positively present, only `blank_or_low_text` when visuals
were positively measured-absent, and otherwise `unknown` (missing visual signal →
cannot distinguish a scan from a blank). This is deliberately **not** a precise
scanned-page detector — it is an advisory hint, never a router or a gate.
**Scope:** no OCR call/routing, prompt, provider, request-field, frontend, Ask,
export, render, or generation-gating change; extraction text output is byte-for-byte
unchanged.

---

## OCR provider boundary added; local behaviour kept byte-identical (Slice 32)
Slice 32 introduced a backend-only OCR provider boundary
(`pipeline/ocr_provider.py`: `OcrRequest` / `OcrResult` / `OcrProvider` /
`TesseractLocalOcrProvider` + `get_default_ocr_provider()`) and rewired
`pipeline/extract.py::_extract_pdf` to OCR through the default provider instead of
the in-line `_ocr_page`. Several non-obvious choices:

**(1) Pure refactor — no exception that previously propagated is newly swallowed.**
The design doc (§4.3) ultimately wants OCR failures to return a safe
`error_category` and never raise into the extraction loop (degrade-not-fail). The
old in-line `_ocr_page` did **not** catch raster/recognise exceptions — they
propagated. To keep this slice behaviour-identical, `TesseractLocalOcrProvider.
ocr_page` deliberately does **not** add new exception handling: the same code runs
in the same order with the same propagation. The `error_category` field exists on
`OcrResult` as part of the boundary *shape* for future (cloud) providers, but is
unused by the local provider. The existing degrade paths are fully preserved: OCR
unavailable (`is_available()` false) → empty text → embedded-text fallback or page
drop with the same per-page warnings; OCR returns empty → same fallback. The
provider id-strings for the two unavailable reasons are unchanged.

**(2) `extraction_metadata.json` is NOT changed in this slice (no `ocr_provider`
field, no version bump — stays `version: 2`).** The design doc lists a future
per-page `ocr_provider` field, but adding it now would change the artifact bytes
for OCR'd pages. This slice is scoped to "local behaviour unchanged", so the
artifact stays byte-identical; surfacing the provider id in metadata is deferred to
the routing slice (Slice 34) where it carries real routing meaning. The existing
`test_extraction_metadata.py` asserts exact per-page values and passes unchanged,
which is the byte-identical proof.

**(3) `_ocr_available()` kept as a thin backward-compatible shim in `extract.py`.**
It now delegates to `get_default_ocr_provider().is_available()` (same `(ready,
reason)` shape, same strings) so `preflight_pdf` and the existing tests
(`test_mixed_pdf_ocr.py`, `test_pdf_page_selection_extract.py`) that import it keep
working without change. `_ocr_page` / `_preprocess_ocr_image` moved into the
provider module (`_preprocess_ocr_image` is OCR-only and had no external callers).

**Scope:** no Mistral/cloud OCR, no OCR routing change, no page-classification
change, no prompt/provider-settings change, no `/api/jobs/llm` request-field
change, no frontend/UI, no Ask/retrieval, no LanceDB/embeddings, no generic
`ARTIFACTS`/export-bundle change, no `validation.json` / `math_verification.json` /
`guide_lint.json` schema change, no PDF/Chromium render-pipeline change, no
generation gating. Extraction text output is byte-for-byte unchanged.


## Slice 33 — OCR routing policy is a pure core, not wired into extraction
The hybrid OCR router (`pipeline/ocr_routing.py`) is implemented and tested as a
**pure, deterministic, dependency-free** function and is **deliberately not called
from `pipeline/extract.py`** in this slice (mirrors the Slice 18/19 "pure core,
then integrate" pattern; see `HYBRID_OCR_DESIGN.md` §9 Slice 33 → 34). **Why:**
keeping the policy decisions provable in isolation — with no `fitz`/Tesseract/cloud
imports, no I/O, no clock, no randomness — lets us lock down the action/reason
vocabulary and the leak-safety guarantees before any behaviour change. Wiring it
into the live local path (and recording `ocr_recommended`/`ocr_attempted`/
`skipped_reason`) is the separate, integration-only Slice 34.

Three non-obvious policy choices, recorded so they are not relitigated:

**(1) `ocr_fallback` classification → `use_embedded_text`, not `use_local_ocr`.**
`ocr_fallback` means OCR *already ran* for that page during extraction and its text
is what was captured (method `ocr`). Routing it back to `use_local_ocr` would
re-OCR an already-OCR'd page — duplicate work that changes nothing. So the policy
treats already-OCR'd pages as "use the text we have" (reason `ocr_already_applied`).
Only `likely_scanned` (weak/empty text + visual content, OCR not yet run) routes to
local OCR.

**(2) Cloud is opt-in, last-resort, and only volunteered when local can't serve the
page.** `cloud_ocr_candidate` is returned **only** when `allow_cloud_ocr` is an
explicit `True` **and** local OCR is unavailable; with local OCR available, cloud
is never volunteered even when allowed (local-first cost/privacy rule, §5.1/§5.2).
The candidate's `provider` stays `null` — it is an advisory future option, and no
cloud provider is implemented or configured here, so naming one would be misleading
(and a leak risk). Default config is `allow_cloud_ocr: False` / `local_ocr_available:
True` so default routing is exactly today's local-first posture.

**(3) Config flags require a real boolean; counts coerce to non-negative int or
None; failure is impossible.** `_safe_bool` ignores truthy non-booleans so a
smuggled non-empty string can't silently flip cloud OCR on — a flag must be an
explicit `True`/`False`. The router reads only `page_metadata["classification"]`
and never echoes any other input field, and any malformed/hostile input degrades to
a fixed safe decision (`action:"unknown"`, `reason:"routing_unavailable"`,
`warnings:["routing_input_unrecognized"]`). Every output field is a fixed
closed-vocab token, an int, `None`, or the literal `"tesseract_local"` id — so no
path, key, image blob, URL, or free text from the input can ever reach a decision.

**Scope:** no `pipeline/extract.py` change, no Mistral/cloud OCR implementation, no
provider settings, no prompt/`/api/jobs/llm`-field/frontend/Ask/retrieval/embeddings
change, no generic `ARTIFACTS`/export-bundle change, no `extraction_metadata.json` /
`validation.json` / `math_verification.json` / `guide_lint.json` schema change, no
render-pipeline change, no generation gating. Extraction output is unchanged.


## Slice 34 — routing wired into extraction as an advisory *recorder*, not a behaviour-changing router
Slice 34 makes the first **live** call to the Slice 33 policy from
`pipeline/extract.py` and records a per-page routing decision
(`ocr_route_action` / `_provider` / `_reason` / `_confidence` / `_warnings`) in
`extraction_metadata.json`. It stays **local-only and behaviour-compatible**. Four
non-obvious choices, recorded so they are not relitigated:

**(1) Recorder, not a router — behaviour compatibility wins over the policy's
`blank_or_low_text → skip_ocr` mapping.** The route is computed *after* a page's
method/text/visual signals are known and is written as advisory metadata only; it
**does not decide whether OCR runs.** The unchanged per-page text-vs-OCR logic in
`_extract_pdf` still makes that call, so extracted text and `## Page N` anchors are
byte-for-byte identical and the existing OCR-availability/empty behaviour is
preserved. **Why:** the pure policy would `skip_ocr` a positively-blank page, but
current extraction *attempts* OCR on such a page (then drops it if empty). Per the
slice's "prefer behaviour compatibility in live extraction" rule, we keep the
historical attempt and let the route be an advisory hint of what a future router
*would* do — "advisory route metadata, not yet a behaviour-changing router." No
fixture's extracted text changes.

**(2) Routing is computed in `extract.py` (carry-and-sanitise), unlike
classification which is recomputed in `_safe_page` (Slice 31).** Classification is
derived purely from sanitized numeric/method/visual fields, so Slice 31 recomputes
it at the sanitiser and ignores any upstream value. Routing additionally needs
`local_ocr_available`, which is **only authoritatively known in `extract.py`** (the
`ocr_ready` probe the extractor already ran) — `_safe_page` cannot know it without
guessing. So the truthful locus is the extractor: `_pdf_route_decision(record, *,
ocr_ready)` consults the policy with `local_ocr_available = ocr_ready` and
`allow_cloud_ocr = False`. To keep Slice 31's leak-safety, `_safe_page` then treats
the route fields exactly like the other upstream-computed fields (`method`,
`warnings`): it **carries them through a closed-vocabulary whitelist**
(`_safe_route_*`, vocab imported from `ocr_routing`), coercing any out-of-vocab /
smuggled value to a fixed safe token. A hostile `ocr_route_*` (URL, host path,
secret, image blob) therefore still cannot survive — the guarantee is identical to
recomputation, just enforced by whitelist instead of re-derivation. The advisory
`classification` fed to the policy reuses the same classifier via the new public
`classify_pdf_page_record`, so live routing and the persisted `classification` field
agree (single source of truth).

**(3) `extraction_metadata.json` stays `version: 2`.** The route fields are purely
additive/optional page fields under the established rule "bump once on the first new
field (Slice 30 did 1 → 2), not on every additive field" (see the Slice 31 entry).
Readers that treat missing/unknown keys as "not measured" are unaffected. Route
fields are emitted **only when the extractor supplied them**, so legacy / hand-built
/ non-PDF page records stay byte-identical.

**(4) Local-only and degrade-not-fail.** `allow_cloud_ocr` is hard-`False` at the
call site, so `ocr_route_provider` is only ever `"tesseract_local"` or `null` —
never a cloud id, and no cloud/Mistral path exists. The whole adapter is wrapped:
the policy itself never raises, but any unexpected error (e.g. in the classifier)
records a fixed safe route (`action:"unknown"`, `reason:"routing_unavailable"`,
`warnings:["routing_input_unrecognized"]`) and never propagates — routing can never
fail a generation. OCR still runs through the Slice 32 local provider boundary
unchanged.

**Scope:** no Mistral/cloud OCR, provider settings, prompt, `/api/jobs/llm`
request-field, frontend/UI, Ask/retrieval, LanceDB/embeddings, generic
`ARTIFACTS`/export-bundle, render-pipeline, generation-gating, or `validation.json`
/ `math_verification.json` / `guide_lint.json` schema change. `extraction_metadata.
json` gains additive page fields only (no version bump). Extraction text output is
byte-for-byte unchanged.

## Cloud OCR (Mistral) is a conditional-go gated on operator pricing + privacy confirmation (2026-06-11, Slice 35)
A docs-only verification (`docs/MISTRAL_OCR_VERIFICATION.md`) evaluated **Mistral
OCR / Document AI** as a future cloud OCR provider. Decision: **it is approved
*architecturally* but not yet *operationally*** — proceed to implementation **only
after the operator confirms (a) the live per-page price** (original ~$1/1,000 pages
vs Mistral OCR 3 `mistral-ocr-2512` ~$2/1,000) **and (b) acceptance of the privacy
posture** (third-party processing of student notes, default 30-day abuse-retention
unless ZDR on the Scale plan / stateless calls), and then **only behind an explicit,
off-by-default opt-in.** **Why:** the product is a clean structural fit (per-page
Markdown output; ≤50 MB / ≤1,000 pages; plugs straight into the Slice 32
`OcrProvider` boundary and the Slice 33/34 `allow_cloud_ocr` + page-budget routing
seams) with **no technical blockers** — so the real gate is *policy*, not code.
Local-first stays the default; cloud OCR must be opt-in, page-budgeted, fall back to
local Tesseract on any error, use base64/file-upload (never a public `document_url`
for operator documents), pin a dated model id (not the `-latest` alias), and keep the
API key / `Authorization` / raw provider errors / URLs / document paths
**server-side only** (provider-settings DTO posture). This entry records the gate so
a later slice does not silently start routing student documents to a third party.
Next slice (36) should be a *disabled-by-default* provider skeleton + OCR
provider-settings/key-storage design, not a live integration.

## Visual/cost roadmap: provider-agnostic manifest first; Mistral provider resequenced behind it (2026-06-11, Slice 36)
A docs-only planning slice added `docs/VISION_ROADMAP.md` (the operator's revised
*Capture → Explain → Show → Trust → Retain* vision). Two load-bearing decisions are
recorded here so a later implementer does not invert the order. **(1) The planned
`visual_assets_manifest.json` is a provider-agnostic *normalization boundary*, not a
raw `fitz` dump** — it is designed from day one to absorb richer providers
(`fitz_local`, `chandra_local`, `mistral_ocr`, future `vlm_*`) into one closed-vocab
asset record (`asset_id`, `source_page`, `asset_type`, `bbox`, `caption`,
`source_provider`, `recommended_action`, `dedupe_group`, `scores`) with no raw
paths/keys/URLs/payloads, so adding a provider never reshapes the schema or its
consumers. **(2) The old `HYBRID_OCR_DESIGN.md` §9 "Slice 36 = Mistral provider" item
is resequenced, not cancelled** — the Mistral cloud provider skeleton is now
**proposed Slice 43 (disabled/unwired)** so the provider-agnostic mode/budget
skeleton (proposed Slice 37) and the advisory visual manifest (proposed Slice 38)
land first. **Why:** wiring a single cloud provider before the mode/consent/budget
framework and the normalization boundary exist would bake provider-specific shape
into extraction and force a later rewrite; advisory-first + provider-agnostic-first
keeps every step inside the existing guarantees (byte-identical when unused,
degrade-not-fail, local/private default, server-side keys). **Chandra** is captured
as a near-roadmap high-quality *local* provider that could make Local/Private mode
genuinely strong for GPU users, but is **gated** (docs-verification slice + a later
RTX 5070 Ti hands-on spike + a Datalab license review for any multi-user use) and is
**not** production-approved. **Privacy** is framed as a disclosure/consent + budget
layer (once-per-session cloud disclaimer, dollar + page caps), not a hard blocker;
Local/Private needs no disclaimer. **Scope:** docs only — no code, dependency,
provider setting, key, prompt, routing, extraction, schema, or render change; no
external OCR/vision API called. Slices 37–43 are **proposed**, not existing.

## OCR mode/cost is a pure skeleton that gates cloud behind explicit opt-in, not mode name (2026-06-11, Slice 37)
`pipeline/ocr_modes.py` adds the provider-agnostic mode + cost/budget framework
(modes `local_private`/`smart_cloud_assist`/`maximum_fidelity`; provider
roles/ids; `OcrModeSettings`/`OcrBudget`/`OcrProviderPricing`/`OcrCostEstimate`).
Two decisions are load-bearing. **(1) Cloud is gated by an explicit
`cloud_opt_in=True` real-bool, never by the mode name.**
`resolve_ocr_mode_config()` sets `allow_cloud_ocr=True` **only** when the mode is
cloud-capable AND `cloud_opt_in is True`; the default `local_private` and any
cloud-capable mode without opt-in both resolve to `allow_cloud_ocr=False`, and a
truthy non-bool (e.g. `"yes"`) is rejected. **Why:** a selecting a "Smart Cloud
Assist" mode in a future UI must not, by itself, start sending student documents
to a third party — consent is a separate, explicit, auditable flag. The resolved
config is intentionally the exact Slice 33 `ocr_routing.default_config()` shape so
the existing local-first, page-budgeted, advisory-`cloud_ocr_candidate` policy is
the *only* thing that ever acts on it, and **nothing is wired into extraction in
this slice**. **(2) Cloud pricing is a static, documented snapshot — never a live
lookup or billing truth.** `estimate_ocr_cost()` is pure and makes no network
call; the Mistral figure (~$2/1,000 pages standard, ~$1/1,000 batch) is marked
`is_estimate:true` with `price_source:"docs/MISTRAL_OCR_VERIFICATION.md"` (June
2026), local providers are free/exact, and an unknown/unconfigured provider
returns a safe `unavailable`/`unknown` status rather than guessing. **Why:**
estimates are for *planning* (page/dollar caps surface as advisory warnings, never
hard failures); treating them as authoritative or fetching them live would couple
a pure module to a provider account and let a vendor price change silently alter
behavior — pricing must be re-verified in this one table before any billing UI.
Every output field is closed-vocab / number / `None` / `"USD"` / the repo doc
`price_source`, and hostile input keys (api_key, base_url, authorization, host/
socket path, argv) are dropped, so no secret/URL/path can leak through a settings
or estimate DTO. **Scope:** new pure module + focused test only — no API route, no
frontend, no extraction/routing/prompt/request-field/Ask/render/artifact/schema/
export change.

## visual_assets_manifest.json is a provider-agnostic normalization boundary built from existing signals only (2026-06-11, Slice 38)
`pipeline/visual_assets_manifest.py` adds the first `visual_assets_manifest.json`
advisory artifact — the provider-agnostic normalization boundary Slice 36's roadmap
specified, so that every present/future visual provider (`fitz_local` today;
`chandra_local`/`mistral_ocr`/`vlm_*` later) maps into one safe shape rather than a
raw `fitz` dump. Three decisions are load-bearing. **(1) The manifest is populated
ONLY from page-level signals already collected for `extraction_metadata.json`
(Slice 30/31/34)** — image/drawing object counts, `has_images`/`has_drawings`, page
dimensions, advisory `classification`, and the local `ocr_route_action`. It opens no
PDF, inspects no image, crops/rasterizes nothing, writes no image file or raw byte,
embeds nothing into guides, and calls no provider/network. **Why:** this slice
establishes the *schema and boundary* cheaply and risk-free; actual local figure
extraction / cropping / dedup / candidate scoring / Chandra verification / Mistral
skeleton are explicitly later slices, and keeping them out means guide text and
`clean.md` stay byte-identical when the feature is unused (only one sibling JSON is
written). **(2) Because nothing is cropped, each asset is a page-level visual
*candidate*, not a real extracted figure** (`asset_type:"page_visual_signal"`,
`bbox:null`, one candidate per page that carries a positive image-OR-drawing signal;
a page with both yields exactly one). The record is deliberately shaped for the rich
future case (`recommended_action`, `dedupe_group`, `scores`, `caption`, `bbox`) with
those fields null/empty/`"unknown"` today, so later slices add data without a schema
break. **Why:** designing the durable shape now avoids a churn later; making the
"candidate, not figure" distinction explicit in the artifact, docs, and tests
prevents a future reader from mistaking a page signal for a cropped image.
**(3) Persistence mirrors the other advisory siblings and uses the smallest
convention.** The builder is a pure function of the already-sanitized
extraction-metadata source records (closed-vocab coercion field-by-field, never
echoing input — `source_provider` only `fitz_local`, `classification`/`ocr_route_action`
coerced to the closed Slice 31/34 vocab, dims/counts coerced numerically), so no raw
path, host path, image byte, raw PDF object, provider payload, OCR error,
key/token/header, URL, socket, or argv can survive even a smuggled record. The
wrapped writer never raises and degrades to a `skipped` artifact on failure; it is
written exactly when extraction-metadata PDF sources exist (right after
`write_extraction_metadata`), and non-PDF / unavailable-metadata jobs OMIT it
entirely — matching how non-applicable artifacts are handled. It is reached only by
its exact filename via `_artifact_path` (`Job.visual_assets_manifest_json`), and is
deliberately NOT added to the generic `ARTIFACTS` list, `_artifact_urls` /
`_artifact_details`, export bundles, or any frontend tab — identical posture to
`math_verification.json` / `guide_lint.json` / `extraction_metadata.json`. **Scope:**
new pure module + focused test + one exact-name route entry + one Job property + one
wrapped writer call — no new API endpoint, no extraction/text/OCR/routing/prompt/
request-field/Ask/render/schema/export/UI change, no external API call.

## Chandra is a verified-but-gated future LOCAL provider: spike, don't implement (2026-06-11, Slice 39)
`docs/CHANDRA_OCR_VERIFICATION.md` is the docs-only prerequisite gate for
`chandra_local` — the Chandra (Datalab) equivalent of Slice 35's Mistral gate —
gathered from official Datalab sources (GitHub repo, HF model cards, `MODEL_LICENSE`)
in June 2026. **Nothing was installed, run, downloaded, or wired; no code, dependency,
provider, route, setting, key, prompt, routing, extraction, render, or manifest-schema
change.** Four decisions are load-bearing. **(1) The target is Chandra 2
(`datalab-to/chandra-ocr-2`, ~4B, released 3/2026), NOT Chandra 1 (9B,
`datalab-to/chandra`).** The 9B→4B shrink is the single most feasibility-relevant fact:
Chandra 1's own HF discussion has the maintainer state **18 GB+ unquantized and 16 GB
insufficient**, so v1 is off the table for the RTX 5070 Ti 16 GB; only v2 is viable.
**Why:** conflating the two cards produces wrong VRAM/license conclusions.
**(2) Hardware feasibility at 16 GB — REVISED from `uncertain-but-promising` to
"GGUF-quantized Chandra OCR 2 likely feasible on the RTX 5070 Ti 16 GB; VRAM is likely
NOT the main blocker."** The original verdict predated GGUF evidence. A community
**`prithivMLmods/chandra-ocr-2-GGUF`** conversion (third-party, **not** the official
`datalab-to` distribution) reports **5B params / `qwen35`** and a quant ladder —
**Q4_K_M ≈ 3.07 GB · Q5_K_M ≈ 3.51 GB · Q6_K ≈ 3.99 GB · Q8_0 ≈ 5.16 GB · BF16/F16 ≈
9.7 GB** — plus separate **`mmproj` ≈ 367–676 MB**; every quant + `mmproj` fits 16 GB
with headroom (Q4/Q5/Q8 comfortably). So **VRAM moves off the critical path** and the
real blockers become **multimodal `llama.cpp`/`llama-server` support, `mmproj` loading,
OCR quality of the quant, throughput, long-document behavior, and integration
stability.** The **throughput caveat stands** (official 1.44 pages/s is H100-at-96-
concurrency; a consumer GPU does materially less; a 500–2,000-page deck may still be
slow). **Integration is now framed as two paths:** the **official vLLM/HF/Transformers**
path (the **likely accuracy/reference baseline**) and the **practical first-spike GGUF
path** through the **existing `llama.cpp`/`llama-server`/LMM** machinery — which **may
avoid building a new heavy vLLM service** if multimodal support works (must not be
assumed until tested; a community quant may degrade quality or lag the official model).
This is **only resolvable by a hands-on spike**, so the recommendation is **REVISED to
`Proceed to hands-on GGUF spike after manifest schema`** (Slice 38 manifest is the
spike's output target) — **still a conditional go to *spike*, NOT approval to
*implement*.** The spike's **first checkpoint** is: *can current `llama-server` load
Chandra GGUF + `mmproj` and OCR a page image?*, and it must **validate GGUF quality
against a known-good/reference baseline, not only quant-vs-quant.** **Why:** docs cannot
settle multimodal-`llama.cpp` support, quant quality, or throughput on a specific
consumer card; committing to build Local mode around Chandra before measuring would be
speculative. **Sequencing:** run the spike **shortly *after* Slice 40, NOT in parallel
with Slice 40's validation**, so a GPU/`llama-server` workload doesn't add noise to the
fresh extraction smoke test. **(3) The rich-capability claims
in roadmap §6 are softened to "reported/implied, confirm against the real JSON."** The
official card confirms MD/HTML/**JSON-with-layout** output, image+diagram extraction
**with captions + structured data**, tables/math/forms/handwriting/multi-column, 90+
languages, and **olmOCR 85.9** — but per-block **bboxes**, the **typed-block
vocabulary**, **Mermaid**, **chart data**, and **merged-cell** specifics are **not
itemized** on the README and must be verified from the actual JSON output in the spike.
**Why:** the `visual_assets_manifest.json` (Slice 38) mapping depends on the exact
schema, so it must not be assumed from secondary write-ups. **(4) License is fine for
personal use, gated for commercial.** Code is **Apache 2.0**; weights are the **"AI PUBS
OPEN RAIL-M LICENSE (MODIFIED)"** — free for research/personal use and entities under
**$2M revenue OR funding**, and explicitly **may not be used to compete with Datalab's
own OCR/document-AI API**. → Acceptable for the **personal/single-operator** tool; a
**multi-user/commercial "help all students" product needs Datalab license review**
(both the $2M thresholds and, more sharply, the competitive-use clause). Marked
**non-legal guidance.** **Integration shape recorded (design only, not built):**
Chandra is simultaneously an OCR + document-extraction + visual-asset provider; it
should start behind the **Slice 32 `OcrProvider` contract** as a richer-than-Tesseract
**local** OCR engine, then grow a **manifest-feeding extraction path** populating the
**Slice 38** boundary with `source_provider:"chandra_local"` (already a reserved token)
+ real `bbox`/`caption`/typed `asset_type`; it powers the **Slice 37 `local_private`**
mode with **no `allow_cloud_ocr`/consent/cost** (nothing leaves the box); it coexists
with `tesseract_local` (always-available fallback) / `fitz_local` (cheap CPU baseline) /
`mistral_ocr` (the cloud counterpart); and operationally it is a **heavy CUDA/vLLM GPU
service** best run via a **dedicated host-companion service capability** (LMM pattern is
precedent but heavier than the GGUF `llama-server` case — downstream of the paused LMM +
deferred approve-root/packaging work), always degrading to Tesseract/fitz on
unavailable/timeout/OOM and reusing the Slice 33 page budget for large docs. **Scope:**
one new doc + the three live-doc updates — docs only, no code/test/fixture/dependency/
model-download/API-call change.

## Local figure extraction is gated, advisory, and the manifest re-sanitises it (2026-06-12, Slice 40)
Slice 40 is the **first real extractor-output change** in the visual stack: a new
`pipeline/visual_asset_extractor.py` uses PyMuPDF (`fitz`) to **crop embedded image
regions out of the PDF** into real `extracted_figure` assets (real `bbox`, a saved PNG
under the new `Job.assets_dir`, and a safe relative `image_ref` `assets/<slug>.png`),
which `run_llm_job` merges into `visual_assets_manifest.json`. Five decisions are
load-bearing. **(1) It is gated off by default** via
`GUIDEFORGE_LOCAL_FIGURE_EXTRACTION`; when unset/false the extractor is never invoked and
the manifest is **byte-identical to Slice 38** (verified: `smoke_release.py` 29/0/0
unchanged). **Why:** this touches the extraction/job-artifact path, so the default must
stay provably inert until the visual pillar is ready to consume it. **(2) The manifest —
not the fitz extractor — remains the security boundary.** `build_visual_assets_manifest`
gained an optional `extracted_assets` param and **re-sanitises every record field-by-field**
(asset-id slug `[A-Za-z0-9_]`, fixed `extracted_figure` type, finite/ordered/positive-area
`bbox` else `None`, strict `^assets/[A-Za-z0-9_]+\.png$` `image_ref` else the record is
dropped, whitelisted numeric `signals` only). The manifest module stays **fitz-free and
pure**. **Why:** a changed or hostile extractor must not be able to smuggle an absolute/
host/traversal path, raw image byte, URL, or free text into the persisted artifact —
defence in depth on top of the extractor's own safe emission. **(3) Explosion prevention
is mandatory, not optional.** The extractor skips tiny/decorative regions
(`MIN_SIDE_POINTS=24pt`, `MIN_AREA_FRACTION=0.004`), collapses duplicate placements of the
same region, and caps `MAX_FIGURES_PER_PAGE=12` / `MAX_FIGURES_PER_JOB=200`. **Why:** a
2,000-page scanned/video-frame deck (each page often one image) would otherwise produce an
unbounded pile of full-page crops — the roadmap's explicit local-fitz limitation. **(4)
Degrade-not-fail.** Missing PyMuPDF, a corrupt PDF, or a single bad image yields fewer/zero
assets and a logged exception *type* only — never a job failure, never raw error text.
Mirrors every advisory slice (extraction-metadata / manifest writers). **(5) Assets do NOT
reach the guide this slice.** Slice 40 writes only the manifest + PNGs; `Job.assets_dir`
is not in exports / `ARTIFACTS` / DTOs, and there is no prompt/render/UI change.
Asset-aware prompt assembly (V4) and the render-embed path (V5) are separate later slices,
where orphan-`{{figure}}`/coverage tests belong. **Determinism:** ids/filenames are
`s{src:02d}_page_{NNNN}_figure_{MM}`, stable for a given PDF+inputs (crop DPI 150).
**Scope:** new `visual_asset_extractor.py` + `test_local_figure_extraction.py`; edits to
`visual_assets_manifest.py` (`extracted_assets` merge + `extracted_figure_count` summary +
`extracted_figure`/`image_ref` schema), `job_manager.py` (`assets_dir`), `run_llm_job.py`
(track PDF path/pages + gated `_extract_local_figures`). No Chandra/Mistral/Gemini, no
network, no OCR, no dependency change. Validated green: 59/0/0 focused test in Docker,
65/0 manifest backward-compat, fresh build + smoke 29/0/0, flag-on glue verified live.

## Chandra OCR 2 GGUF is hands-on feasible on the local llama-server path; gate it behind a self-built mmproj + pinned llama.cpp (2026-06-12, Slice 41)
Slice 41 ran the **hands-on** spike Slice 39 deferred: it downloaded the official
`datalab-to/chandra-ocr-2` (~10.6 GB, arch `Qwen3_5ForConditionalGeneration`), built a
GGUF `mmproj` + text quants with `llama.cpp` build 9307's convert tooling, and ran real
OCR on the local **RTX 5070 Ti 16 GB** via both `llama-mtmd-cli` and `llama-server`'s
OpenAI-compatible `image_url` path. **Verdict: proceed to provider design (strong pass),
gated.** Four durable findings. **(1) It runs on the path the LMM already drives — no new
service.** Chandra OCR 2 loads as a standard text GGUF + `--mmproj` on `llama-server`;
image input works over `/v1/chat/completions`. **Why it matters:** a future `chandra_local`
provider is a *configuration + normalisation* problem, not a new host companion/service —
the LMM boundary is unchanged. **(2) The mmproj must be self-built; public GGUFs are
text-only.** The only public conversion (`hyojk2001/chandra-ocr-2-Q4_K_M-GGUF`,
`gguf-my-repo`) ships **no `mmproj`**, so it cannot OCR. The working `mmproj` (~676 MB) was
generated from the **official** weights because the convert tooling's `MMPROJ_MODEL_MAP`
routes `Qwen3_5ForConditionalGeneration → qwen3vl`. **Why:** the app cannot just "point at
an HF GGUF" — a one-time mmproj/quant build (host-companion side, pinned `llama.cpp` with
`qwen35`+`qwen3vl` support) is a prerequisite, and that build-pin is **version-sensitive**
(older `llama.cpp` cannot export/load it). **(3) VRAM is not the blocker; quality is high
even small.** Q4_K_M/Q5_K_M/Q8_0 all gave near-perfect output on hand-checked synthetic
pages (~5.4/5.8/7.2 GB VRAM at 8K ctx, 256K train ctx). Native output is **layout-HTML with
`data-bbox` + `data-label`** (Section-Header/Text/Table/Equation-Block/Diagram) + HTML
tables + LaTeX math — which maps to `clean.md` source text **and** to
`visual_assets_manifest.json` asset candidates, complementing Slice 40's `fitz` crops. **Why:**
this is the high-value fit — Chandra gives text *and* bbox/label structure in one pass. **(4)
Throughput is batch-only and the fallback contract is non-negotiable.** ~8–20 pages/min warm
(long decks not run) → keep it off-by-default, local-only, behind the deferred async/batch
large-PDF handling, and **always degrade, never fail**: Chandra unavailable → Tesseract/`fitz`;
Chandra bad/timeout → drop to embedded-text + `fitz` so the guide still builds. **Scope:**
docs-only — `docs/CHANDRA_GGUF_SPIKE_REPORT.md` + handoff logs; **no app/provider/routing/
extraction/prompt/render/UI/manifest-schema change, and no model files/weights/mmproj/quants
committed** (kept in a throwaway workspace outside the repo). Recommended next slices (design):
host-companion mmproj/quant build (pinned `llama.cpp`); pure output→`clean.md`+manifest
normaliser (reusing the Slice 38/40 schema); prompt/template lock (`--image-min-tokens 1024`
for bbox grounding).

## The Chandra normalizer is a pure, model-free core that is its own safety boundary (2026-06-12, Slice 42)
Slice 41 recommended a "pure output→`clean.md`+manifest normaliser" as a prerequisite to any
`chandra_local` provider. Slice 42 builds exactly that — `pipeline/chandra_normalizer.py` —
and the durable choice is to make it a **stand-alone pure function of one raw string**, fully
decoupled from any model/provider/extraction code. **Why this shape.** (1) **Decouple the hard,
testable part from the flaky, expensive part.** Parsing Chandra's `data-bbox`/`data-label`
layout output into `source_text` + asset candidates is deterministic and unit-testable; running
the model on `llama-server` is not. Splitting them lets the normalizer land, get hardened, and
be regression-tested (68/0) *before* any integration slice, and lets a later provider slice be a
thin "run model → hand raw string to this function" wrapper. (2) **The normalizer is the security
boundary, mirroring the Slice 40 manifest decision.** Model output is *untrusted input* (the OCR'd
document, or a hostile PDF, can smuggle paths/URLs/keys/`<script>`/base64). So every captured/raw
string is scrubbed field-by-field and every emitted field is a closed-vocab token / coerced
number / `null` — the normalizer cannot be poisoned into leaking an abs/host path, URL,
`Authorization`/`Bearer`, key-like token, `.sock`, `--flag` argv, base64/image bytes, or raw
script/style, even if the upstream model changes. It is **total** (never raises) and degrades to
an empty-but-valid `completed` output on malformed input, matching the "advisory artifact never
breaks a job / always degrade, never fail" posture from Slices 38/40/41. (3) **Match the existing
manifest asset shape; do not widen the schema.** Assets reuse the Slice 38/40 fields
(`asset_id`/`source_page`/`asset_type`/`bbox`/`caption`/`source_provider`/`recommended_action`/
`dedupe_group`/`scores`/`signals`/`warnings`) so a future integration can merge Chandra candidates
beside `fitz_local` ones with no manifest change; the only addition is a per-asset `asset_ref`
held at **`null`** (Chandra writes no files this slice) and `recommended_action` pinned to
`"unknown"` (no scoring yet) — both reserved for later slices, deliberately not emitted now.
(4) **Don't surface text as visual assets.** Text/caption blocks feed `source_text` only;
only table/equation/diagram/figure/image/`unknown_region` become asset candidates — keeping the
manifest about *visuals* and `clean.md` about *prose*. **Scope:** new
`pipeline/chandra_normalizer.py` + `test_scripts/test_chandra_normalizer.py` only; **no app
integration, no Chandra/`llama-server` call, no model files, no extraction/OCR/prompt/render/UI/
export change, no manifest schema change.** Validated green (focused battery incl. manifest
backward-compat, eval offline, frontend build/test, smoke 29/0/0).

## The Chandra local provider lands as a disabled, unwired skeleton split from integration (2026-06-12, Slice 43)
Slice 42 left the Chandra chain one boundary short of a usable provider: the pure normalizer
turns a *raw string* into safe `source_text` + asset candidates, but nothing yet shapes the
`llama-server` request or extracts the model's reply. Slice 43 adds exactly that seam —
`pipeline/chandra_local_provider.py` — and the durable choice is to ship it **disabled and
unwired** (a request-builder + response-parser + a thin normalizer bridge, `ChandraLocalProvider.
enabled = False`), fully decoupled from extraction/OCR routing and from any real model call.
**Why this shape.** (1) **Split the deterministic boundary from the flaky integration, again.**
Building an OpenAI-compatible multimodal payload (`messages=[text, image_url]`) and parsing
`{"choices":[{"message":{"content":...}}]}` are pure, unit-testable transforms; running the model
on the LMM `llama-server` path (process lifecycle, sockets, VRAM, latency, fallback) is not.
Landing the transforms first — hardened and regression-tested (68/0) with **injected fake
responses only** — lets a later integration slice be a thin "run model → hand raw string to
`normalize_chandra_chat_response`" wrapper behind an explicit, off-by-default route. (2)
**Disabled-by-construction is the safety posture, not a TODO.** `enabled = False` and the absence
of any production constructor mean this slice cannot change a single generated guide, extraction
result, or artifact even by accident; it is provable by reading the diff (no import touches
`extract.py`/routing/`api`). (3) **Keep the leak boundary in one place.** The provider does *not*
re-implement scrubbing — `normalize_chandra_chat_response` delegates all path/URL/key/`.sock`/argv/
base64/`<script>` scrubbing to the Slice 42 normalizer, which owns that boundary. The provider's
only added hygiene is local to its two new responsibilities: the parser is **total** and emits
closed-vocab warnings without ever echoing the raw provider payload, and image bytes are encoded to
a base64 data URI **only inside the request builder** (never logged, never returned by
parse/normalize). The request shape deliberately embeds **no** model id, base URL, host path, argv,
or `--image-min-tokens` flag — those are integration concerns, and a `mime_type` whitelist stops a
caller smuggling an arbitrary string into the data-URI prefix. (4) **Stdlib-only, no new
dependency.** It imports only `base64`/`typing` + the Slice 42 normalizer; notably **not** `openai`/
`urllib`/`socket`/`subprocess` — the OpenAI-compatible *shape* is a plain dict, so proving the
boundary needs no client and no transport. **Scope:** new `pipeline/chandra_local_provider.py` +
`test_scripts/test_chandra_local_provider.py` only; **no app integration, no real Chandra/
`llama-server`/network call, no model files, no extraction/OCR-routing/`clean.md`/prompt/render/UI/
export change, no manifest or `extraction_metadata.json` schema change.** Validated green
(`test_chandra_local_provider` 68/0, `test_chandra_normalizer` 68/0, OCR + manifest battery, eval
offline no-regression, frontend build/test, `git diff --check` clean); `smoke_release.py` not
required since no production-wired behavior is touched.

## Chandra live validation is a manual, opt-in harness — not a release-smoke step
The Chandra local provider's first contact with a *real* model (Slice 44) is a
standalone `test_scripts/validate_chandra_local_provider_live.py`, run by hand
with an operator-supplied `--endpoint` and `--image`; it is deliberately **not**
added to `smoke_release.py`. **Why:** (1) **Real-server proof must be opt-in, not
ambient.** A live `llama-server` page-image round-trip depends on hardware, VRAM,
model files, and a process the operator started — none of which exist in CI or a
fresh checkout. Wiring it into smoke would make release validation flaky and
machine-dependent for no production benefit, since nothing in the app calls the
provider yet. Importing the harness therefore triggers no network/file/model/
subprocess/Docker/server access, and every automated test injects a fake
transport — the real `urllib` transport runs **only** when the operator invokes
the CLI. (2) **The harness reports safe summaries, never raw output.** It returns
and prints a closed-vocabulary summary (booleans, counts, fixed status/category
tokens, a redacted `scheme://host:<port>/...` endpoint label); the OCR source
text is surfaced **only as a character count**, never echoed. It never emits the
raw provider payload, image path/bytes, a base64/data URI, a full URL/query/
headers, `Authorization`/`Bearer` fragments, raw argv, or model/mmproj/exec/
socket paths. Endpoint redaction uses `urlsplit().hostname` so a token in
userinfo/path/query cannot survive, and the printer whitelists keys so no stray
field can leak. All model-*content* scrubbing stays delegated to the Slice 42
normalizer — the harness adds only failure-category mapping and the count-only
projection. (3) **No production surface is touched.** It supports **no** auth
header, starts/stops **no** `llama-server`, uses **no** subprocess/shell/Docker,
and changes nothing in `pipeline/extract.py`, OCR routing, `extraction_metadata.json`,
the `visual_assets_manifest.json` schema, `clean.md`, prompts, renderers, exports,
the API, the frontend, Provider Settings, or the Local Model Manager. **Scope:**
new `test_scripts/validate_chandra_local_provider_live.py` +
`test_scripts/test_chandra_live_harness.py` (96/0, fake transport only) + docs.
Validated green across the chandra/normalizer/manifest/figure/OCR/pdf/math/lint/
eval/ask battery, frontend build+test, and `git diff --check`; `smoke_release.py`
not required since no production-wired behavior is touched. **Deferred:** only
after this harness proves stable on real hardware does a later slice decide
whether to add a still-**disabled**, off-by-default extraction-side adapter (with
Tesseract/`fitz` fallback and degrade-not-fail) — no extraction wiring before then.

## The Chandra extraction-adapter is gated behind a real, sanitized live-harness pass (2026-06-12, Slice 45)
Before any Chandra **extraction-side** code is written, the Slice 44 live harness
must first **pass on real hardware**, and that pass is recorded as a sanitized
result in `docs/CHANDRA_LIVE_HARNESS_VALIDATION.md`. Slice 45 is the docs-only
**gate/report** that establishes this rule and the operator runbook; it records
the current result honestly as `status: not_run` /
`reason: operator_input_not_supplied` (no live endpoint or non-private image was
supplied, so no live HTTP request was made and no result was fabricated).
**Why:** (1) **A gate must exist between "the boundary parses" and "wire it into
extraction."** The skeleton (Slice 43) and harness (Slice 44) prove the
request/response/normalizer *shape*, but nothing has yet proven a real local
`llama-server` produces usable output through that shape on this hardware. Writing
an extraction adapter before that proof would be building on an unverified
assumption. So the decision rule is explicit: live pass ⇒ proceed to a still-
**disabled**, off-by-default extraction-side adapter (with Tesseract/`fitz`
fallback, degrade-not-fail); `not_run`/fail ⇒ the adapter stays **blocked**, fix
or rerun first. Current gate state is `not_run`, so the adapter is blocked. (2)
**The runbook keeps the proof leak-safe by construction.** The run-command
template uses **placeholders only** (`<local-openai-compatible-endpoint>`,
`<non-private-test-image>`) and the safe-output policy permits recording **only**
the harness's closed-vocabulary summary fields (booleans, counts, fixed
status/category tokens) — never raw OCR text, the raw provider response, the image
path/basename/bytes, a base64/`data:` URI, a full URL/port/query, headers/tokens,
or a socket/model/`mmproj`/executable path. Operator-specific facts (real paths,
endpoints, launch commands) are explicitly forbidden from the doc. (3) **It stays
honest about what was not done.** A `not_run` result is recorded as such rather
than fabricating a green run; the harness remains proven only by its fake-transport
suite (`test_chandra_live_harness` 96/0). **Scope:** docs-only — new
`docs/CHANDRA_LIVE_HARNESS_VALIDATION.md` + `CURRENT_TASK.md` +
`NEXT_CHAT_HANDOFF.md` + this entry; no code/test/extraction/`ocr_routing`/
`extraction_metadata.json`/`visual_assets_manifest.json`/API/frontend/Provider
Settings/LMM/render/export/`clean.md` change, no `llama-server` management, no
subprocess/Docker, and no model/mmproj/quant or raw OCR/provider output committed.
Validated by `git diff --check` (clean) + `git diff --name-only` (docs-only); no
build/smoke needed.

## Visual asset scoring is a separate pure core that never mutates the manifest and keeps `recommended_action:"unknown"` (2026-06-12, Slice 46)
The V3 "candidate scoring" step (`docs/VISION_ROADMAP.md` §8) is implemented as a
new **pure, stdlib-only, unwired** module `pipeline/visual_asset_scoring.py` that
*reads* `visual_assets_manifest.json`-shaped assets and returns a **brand-new,
separate** `visual_asset_scoring` report (`scores[]` with `priority` /
`include_score` / closed-vocab `reasons` + a `summary` of priority counts). It does
**not** mutate the manifest or any asset dict, write any artifact, or wire into
extraction/generation/render/UI/exports. **Why:** (1) **Scoring must be a distinct
artifact from the manifest, not an in-place field.** The manifest
(`pipeline.visual_assets_manifest`) is the provider-agnostic *inventory* boundary;
folding mutable scores into it would blur "what visuals exist" with "which belong
in the guide" — the exact separation `VISION_ROADMAP.md` §8 insists on (page
*classification* ≠ asset *scoring*). Keeping scoring a pure function
`manifest → report` means the manifest stays a stable input, the scorer has no
side effects, and a later slice can choose to persist the report (or fold a chosen
action back) deliberately rather than by accident. So this slice writes **no**
artifact and changes **no** manifest schema. (2) **`recommended_action` stays
`"unknown"` for every score.** This core only assigns *priority* + a numeric
*include_score* from cheap deterministic signals (asset type, valid bbox, presence
of a caption, large-region ratio, page image/drawing signals); the actual
`include_as_figure | convert_to_table | summarize_as_text | omit` decision (the V3
"text-replacement test") and any guide wiring are later, separately-designed slices
(V4+). Emitting a real action now would imply an inclusion decision the pipeline is
not ready to honor. (3) **The scorer is the security boundary, like the manifest
and the Chandra normalizer before it.** Every output field is a fixed closed-vocab
token, an int/float, `None`, or a deterministic slug-safe id; ids/page/provider/
type are coerced field-by-field; a bad bbox/id/page/provider/type yields a closed
warning, not an echo; **captions are used only as a boolean `has_caption` signal
and are never emitted**; and the function never raises and **never mutates** its
input. No raw path, URL, header, token, data URI, base64, image byte, raw
caption/OCR text, socket/model/`mmproj`/executable path, or argv can survive even
if a hostile asset smuggles one in (covered by a dedicated leak test). (4)
**Stdlib-only and unwired keeps it safe to land now.** It imports nothing from
`fitz`/Tesseract/llama.cpp/Chandra/Mistral/Gemini/LMM/renderers/server/job-manager/
extraction, makes no model/network/file/image call, and is not imported by
`run_llm_job.py` — so it changes zero production behavior and `smoke_release.py` is
not required. **Chandra independence:** this is a provider-agnostic visual-stack
slice, **not** Chandra integration; it merely understands the asset *shape* the
Slice 42 Chandra normalizer would emit. Chandra *extraction* integration remains
**blocked** by the Slice 45 gate (`status:not_run`,
`operator_input_not_supplied`) until a live harness pass is recorded. **Scope:** new
`pipeline/visual_asset_scoring.py` + new `test_scripts/test_visual_asset_scoring.py`
(146/0) + this entry + `CURRENT_TASK.md` / `NEXT_CHAT_HANDOFF.md`; no
manifest-schema/extraction/`ocr_routing`/API/frontend/Provider-Settings/LMM/render/
export/`clean.md`/artifact change. Validated by the full pure-test battery
(scoring 146/0; manifest/figure/chandra/ocr suites green; offline eval no
regression; frontend build+test green) + `git diff --check` clean.

## Slice 47 — `visual_asset_scoring.json` persisted as an exact-name advisory artifact
Slice 47 persists the Slice 46 scoring report as the sibling artifact
`visual_asset_scoring.json`, **derived from** the already-written
`visual_assets_manifest.json`. It is written in `run_llm_job._attach_sources`
immediately after `write_visual_assets_manifest(...)`, by reading the just-written
manifest back off disk (`_read_visual_manifest_for_scoring`, total/`None`-on-error)
and passing that sanitized dict to `visual_asset_scoring.write_visual_asset_scoring_report`.
It is reachable **only by exact name** at
`/api/jobs/{id}/artifacts/visual_asset_scoring.json` (a dedicated branch in
`_artifact_path`); it is deliberately **not** added to `ARTIFACTS`,
`EXPORT_ARTIFACTS`, `_artifact_urls`, `_artifact_details`, export bundles, or any
frontend/UI row. **Why this posture, identical to `extraction_metadata.json` /
`math_verification.json` / `guide_lint.json` / `visual_assets_manifest.json`:**
(1) **Advisory, degrade-not-fail.** The writer never raises into job generation —
a non-scorable/unavailable manifest yields a closed-vocab *skipped* report
(`visual_manifest_unavailable`), and any write error degrades to a `write_failed`
skipped report; it never gates/fails the job, never touches job status/validation/
`clean.md`, and **never mutates** the source manifest. The skipped writer uses
**closed `reason` tokens only** (`visual_manifest_unavailable`,
`visual_scoring_unavailable`, `write_failed`) plus a fixed constant `safe_message`;
it never echoes a raw exception, path, or manifest payload (stderr, if reached,
carries an exception **class name** only). (2) **Written exactly when the manifest
is.** Only the PDF-attachment branch that writes `visual_assets_manifest.json`
calls the scoring writer; non-PDF / no-extraction jobs omit **both** artifacts and
see zero behavior change. (3) **Exact-name only, never generic.** Keeping it out of
`ARTIFACTS`/exports/UI means it cannot appear in download lists, ZIP bundles, or the
Library/Exports surface, and never ships in a guide — it is an inspector-only,
operator-facing advisory. (4) **No new capability.** The slice writes/serves a file
and changes nothing else: no guide output, prompt, render, extraction, OCR routing,
visual embedding, or include/omit decision (`recommended_action` stays `unknown`),
and no model/`llama-server`/Chandra/Mistral/Gemini/network/image-file access.
**Chandra independence:** Chandra *extraction* integration remains **blocked** by
the Slice 45 gate (`status:not_run`, `operator_input_not_supplied`); this slice only
persists a report derived from whatever manifest the existing `fitz_local` path
produced. **Scope:** `pipeline/job_manager.py` (`Job.visual_asset_scoring_json`
property), `api/server.py` (exact-name `_artifact_path` branch),
`pipeline/visual_asset_scoring.py` (writer + closed skip reasons),
`pipeline/run_llm_job.py` (wiring + manifest read-back helper),
`test_scripts/test_visual_asset_scoring.py` (allow stdlib `json`/`sys`), new
`test_scripts/test_visual_asset_scoring_artifact.py`, + these docs. Validated by the
full test battery (scoring core 146/0; scoring artifact 58/0; manifest 65/0;
figure 50/0+2skip; chandra-normalizer/provider/live-harness green; ocr suites green;
extraction-metadata 9/9; offline eval no regression; frontend build+test green) plus
a fresh Docker build + `/api/health` + `smoke_release.py` and `git diff --check`
clean.

## Slice 48 — Visual replacement planner is a separate pure core, advisory only
Slice 48 adds `pipeline/visual_replacement_planner.py`, a pure, deterministic,
stdlib-only core that consumes a `visual_asset_scoring.json`-shaped scoring report
(and optionally a `visual_assets_manifest.json`-shaped manifest, **presence-only**)
and returns a brand-new `visual_replacement_plan` report — a per-asset
`candidate_action` / `placement` / `priority` with closed-vocab `reasons`/`warnings`.
**Why a separate core, kept advisory and unwired (mirroring the Slice 46 scoring
core):** (1) **Advisory candidate, not a decision.** The `candidate_action`
(`candidate_include_as_figure` / `candidate_convert_to_table` /
`candidate_summarize_as_text` / `review_only` / `unknown`) is a *candidate* the
operator/later slice reviews — never a binding include/omit and never something that
embeds a visual or changes generated guide text. Keeping the planner pure and unwired
means the V3 stack can mature (manifest → scoring → plan) before any V4+ slice makes a
production include/omit decision, so each layer stays independently testable and
reversible. (2) **Closed vocabulary + no echo, by construction.** Every emitted field
is a fixed token, an int, `None`, an empty list, or a slug-safe `asset_id`; captions,
raw source/OCR text, and provider payloads are never read into output, and a manifest
cross-check contributes **presence only** (`has_manifest_match` / `missing_manifest_match`)
— no manifest field is echoed. A recognized-but-unmapped or coerced-unrecognized type
at actionable priority falls back to `review_only` + `candidate_action_unresolved`
rather than guessing an embedding. This keeps the same no-leak guarantee the manifest
and scoring cores hold (no path/URL/token/header/socket/model/`mmproj`/argv/base64/
data-URI/image-byte can survive a hostile record). (3) **No persistence/wiring this
slice.** It writes no `visual_replacement_plan.json`, adds no route/UI/export, imports
nothing from `fitz`/Tesseract/llama.cpp/Chandra/Mistral/Gemini/LMM/renderers/server/
job-manager/extraction/run-job/`visual_asset_scoring`/`visual_assets_manifest`, makes no
model/network/file/image call, and is not imported by `run_llm_job.py` — so it changes
zero production behavior and `smoke_release.py`/Docker are not required. **Chandra
independence:** a `chandra_local` item is planned only as advisory and always carries
the closed reason `chandra_blocked`; Chandra *extraction* integration remains **blocked**
by the Slice 45 gate (`status:not_run`, `operator_input_not_supplied`) until a live
harness pass is recorded — this core merely understands the asset *shape*. **Scope:**
new `pipeline/visual_replacement_planner.py` + new
`test_scripts/test_visual_replacement_planner.py` (186/0) + this entry +
`CURRENT_TASK.md` / `NEXT_CHAT_HANDOFF.md`; no manifest/scoring-schema/extraction/
`ocr_routing`/API/frontend/Provider-Settings/LMM/render/export/`clean.md`/artifact
change. Validated by the full pure-test battery (planner 186/0; scoring 146/0;
scoring-artifact 58/0; manifest/figure/chandra/ocr suites green; offline eval no
regression; frontend build+test green) + `git diff --check` clean.

## Slice 49 — `visual_replacement_plan.json` persisted as a second-level exact-name advisory artifact
Slice 49 wires the Slice 48 planner core into the job artifact flow as a new
exact-name advisory artifact `visual_replacement_plan.json`, **derived from** the
already-written `visual_asset_scoring.json` report (with the manifest passed only for
a **presence-only** asset-id cross-check). It is written in
`run_llm_job._attach_sources` immediately after `write_visual_asset_scoring_report(...)`,
reusing the returned scoring report and the already-read manifest object (no re-read).
**Why this shape (mirroring the Slice 47 scoring-artifact decision):** (1) **Second-level
advisory, derived not authoritative.** The visual stack is now manifest (V1 source) →
scoring (Slice 47 advisory) → replacement plan (Slice 49 advisory, derived from
scoring). The plan is a *candidate* layer the operator/later slice reviews — it makes
**no** production include/omit/render/prompt decision and embeds **no** visual, so
generated guides are byte-unaffected. (2) **Exact-name route only, no generic
exposure.** A dedicated `_artifact_path` branch maps
`/api/jobs/{id}/artifacts/visual_replacement_plan.json` → the new
`Job.visual_replacement_plan_json`; it is deliberately **not** added to `ARTIFACTS`,
`EXPORT_ARTIFACTS`, `_artifact_urls`, `_artifact_details`, export bundles, or any UI
row — so no new artifact appears in generic lists/exports/frontend, and an absent file
returns the standard graceful 404. This keeps the advisory boundary the manifest and
scoring artifacts already established. (3) **Degrade-not-fail, never mutates inputs.**
The writers (`write_visual_replacement_plan_report` /
`write_skipped_visual_replacement_plan_report`, added to
`pipeline/visual_replacement_planner.py` with stdlib `json`+`sys`, taking a duck-typed
`job` — no `job_manager` import) never raise into job generation, never gate/fail the
job, never touch job status / validation / `clean.md`, and **never mutate**
`visual_asset_scoring.json` or `visual_assets_manifest.json`. When scoring is
skipped/unavailable a safe `skipped` plan (`visual_scoring_unavailable`) is written for
consistency with the Slice 47 posture; a write error degrades to `write_failed`. Closed
skip-reason vocabulary only; short `safe_message`; stderr (if reached) carries an
exception class name only. (4) **No-leak preserved.** The plan never carries
`image_ref`/`caption`/`source_text`, image bytes, data URIs, base64, paths, URLs,
headers, tokens, socket/model/`mmproj`/executable paths, raw argv, or raw
provider/OCR payloads; reasons/warnings stay closed vocabulary. **Chandra independence:**
a `chandra_local` item is planned only as advisory and carries `chandra_blocked`;
Chandra *extraction* integration remains **blocked** by the Slice 45 gate
(`status:not_run`, `operator_input_not_supplied`). **Scope:**
`pipeline/visual_replacement_planner.py` (+writers), `pipeline/job_manager.py`
(+`visual_replacement_plan_json` property), `api/server.py` (+exact-name branch),
`pipeline/run_llm_job.py` (+wiring/import), new
`test_scripts/test_visual_replacement_plan_artifact.py` (68/0), updated
`test_scripts/test_visual_replacement_planner.py` (186/0, import hygiene now allows
`json`/`sys`) + this entry + `CURRENT_TASK.md` / `NEXT_CHAT_HANDOFF.md`; no
manifest/scoring-schema/extraction/`ocr_routing`/prompt/render/guide-output/frontend/
export-bundle/`clean.md` change. Because it touches `api/server.py` + `job_manager.py`
+ `run_llm_job.py`, full validation (Docker rebuild/recreate + `/api/health` +
`smoke_release.py`) is required in addition to the pure-test battery.

## Visual advisory artifacts are surfaced in Job Details by exact-name fetch only — read-only, count-only, no generic/export exposure (Slice 50)

The advisory visual artifact chain — `visual_assets_manifest.json` (Slice 40) →
`visual_asset_scoring.json` (Slice 47) → `visual_replacement_plan.json` (Slice 49) —
is now visible to the operator through a read-only **Job Details "Visual Advisory"**
drawer tab, but **only** as safe COUNTS and closed-vocab status, fetched **by exact
artifact name**.

**Why this shape:** (1) **Inspection without promotion.** The three artifacts were
deliberately kept out of `ARTIFACTS` / `EXPORT_ARTIFACTS` / `_artifact_urls` /
`_artifact_details` / export bundles / generic artifact rows (Slices 40/47/49) so the
advisory boundary stays the manifest and its derived siblings. Surfacing them must not
undo that: this slice adds a **dedicated read-only panel** that fetches each artifact
by its exact name via the existing `getJobArtifact` / `artifactUrl` client helpers, and
adds **no** backend route and **no** entry to any generic artifact list, export bundle,
or existing artifact UI row. (2) **Count-only, closed-vocab, no-leak.** The pure helper
`frontend/src/visualAdvisoryArtifacts.js` (`summarizeVisualManifest` /
`summarizeVisualScoring` / `summarizeVisualReplacementPlan`, plus `isArtifactMissing`
and `safeToken`) returns **only** non-negative integer counts and `state`/`tone`/`label`
tokens; it never passes through captions, OCR/source text, provider payloads, image
refs/bytes, data URIs, base64, paths, URLs, or tokens, and even closed-vocab reason
strings go through `safeToken` (`^[a-z0-9_]+$`, ≤48 chars, else `unavailable`) before
display. Helpers are pure/total — never mutate input, never throw — and node-tested by
`frontend/scripts/verify-job-details-visual-advisory.mjs` (incl. a serialized no-leak
sweep). (3) **Missing is normal.** A 404 is treated as "not generated for this job"
(non-PDF / older jobs) and rendered as a calm "Not available", never a scary error; the
three fetches are independent so one missing/malformed artifact never blocks the others.
(4) **Advisory stays advisory.** The panel makes **no** production include/omit decision,
embeds **no** visuals, and changes nothing about guide generation, prompts, extraction,
OCR routing, rendering, exports, or artifact schemas; the artifacts are read-only fetched
and **never mutated**. `chandra_blocked` presence is summarized as an advisory/blocked
notice with no raw detail — Chandra *extraction* integration remains **blocked** by the
Slice 45 gate (`status:not_run`, `operator_input_not_supplied`). **Scope:** new
`frontend/src/visualAdvisoryArtifacts.js`, `frontend/src/components/VisualAdvisoryPanel.jsx`,
`frontend/scripts/verify-job-details-visual-advisory.mjs`; edited
`frontend/src/components/RecentJobsPanel.jsx` (tab + wiring + `Images` import),
`frontend/src/design-system.css` (`.sg-artifact-link`), `frontend/package.json`
(test scripts) + this entry + `CURRENT_TASK.md` / `NEXT_CHAT_HANDOFF.md`. No backend,
schema, extraction, `ocr_routing`, prompt, render, guide-output, or export change.
Because it changes frontend UI / artifact-inspection behavior, full validation (Docker
rebuild/recreate + `/api/health` + `smoke_release.py`) was run in addition to the
frontend build/test and backend pure-test battery.

## Visual advisory JSON artifacts ride along in export bundles, but never become a generic artifact type (Slice 51)
The three advisory visual **JSON diagnostics** — `visual_assets_manifest.json` (Slice
40), `visual_asset_scoring.json` (Slice 47), `visual_replacement_plan.json` (Slice 49)
— are now included in multi-job export bundles (`POST /api/exports/bundle`) **alongside**
the user-requested exports, **only when they exist** for a job. **Why:** exported bundles
are the portable copy of a job; omitting these sibling diagnostics made the bundle a
less complete record of what the pipeline observed. **How, and the boundary that must
hold:** a dedicated narrow constant `VISUAL_ADVISORY_EXPORT_ARTIFACTS` drives a small
ride-along loop after the existing selector loop in `export_bundle`. The three names are
**deliberately NOT** added to `EXPORT_ARTIFACTS`, `EXPORT_ARTIFACT_ALIASES`, or
`ARTIFACTS` — so they are **never** export-UI artifact *types/selectors*, **never**
generic artifact UI rows, **never** part of `_artifact_urls` / `_artifact_details`, and
`artifact_types` is unchanged. They remain reachable for direct download only by their
exact filename (the existing exact-name route). Ride-along files do **not** count toward
`total_included`, so they can **never** by themselves satisfy the bundle's "at least one
requested artifact" gate — an all-absent requested bundle still returns the same 404, and
an absent advisory file is skipped calmly (never an error, never fails the export). The
bundle index (`manifest.json`) records only a `visual_advisory_included` list of bundled
**filenames** (presence/safe-metadata only) — **no** raw artifact JSON content is inlined
into the index, logs, or terminal output. **JSON diagnostics only:** cropped image files
(`jobs/<id>/assets/*.png`) and image bytes are **never** bundled by this slice; the
artifacts are read **read-only** and **never mutated**. This slice makes **no** production
include/omit decision, embeds **no** visuals, and changes nothing about guide output,
prompts, rendering, extraction, OCR routing, or artifact schemas. Chandra *extraction*
integration remains **blocked** by the Slice 45 gate (`status:not_run`,
`operator_input_not_supplied`). **Scope:** edited `api/server.py` (constant + ride-along
loop + index `visual_advisory_included` field + corrected `_artifact_path` comments) and
`pipeline/job_manager.py` (corrected the now-inaccurate "never in export bundles" comments
on the scoring/plan properties; the `assets_dir` PNG comment is unchanged — image bytes
are still never exported); new `test_scripts/test_visual_advisory_export_bundle.py` + this
entry + `CURRENT_TASK.md` / `NEXT_CHAT_HANDOFF.md`. Because it changes export behavior,
full validation (Docker rebuild/recreate + `/api/health` + `smoke_release.py`) was run in
addition to the backend pure-test battery and frontend build/test.

## The visual insertion planner is a pure, anchor-presence-only core that never embeds and stays advisory (Slice 52)
The visual stack now has a fourth pure planning core — `pipeline/visual_insertion_planner.py`
— sitting after the replacement planner on the `docs/VISION_ROADMAP.md` §8 path: advisory
manifest (Slice 40) → scoring (Slice 46/47) → replacement plan (Slice 48/49) → **insertion
position** (this slice) → an eventual guide embedding (later, separately designed). Given a
`visual_replacement_plan.json`-shaped plan (and, optionally, a safe-only source-page anchor
inventory) it returns a **separate advisory `visual_insertion_plan` dict** — per-asset
`insertion_mode` / `placement` / `anchor_status` with closed-vocab `reasons`. **Why a
separate pure core (mirroring the scoring/replacement cores):** keeping insertion-position
*planning* deterministic, total, stdlib-only (`re`, `typing`), and free of any provider/model/
network/filesystem/image access lets it be exhaustively unit-tested in host Python and reused
by a later wiring/artifact slice without re-deriving the boundary — and, critically, it makes
**no** production decision and embeds **no** visuals, so it cannot change generated guides.
**The boundary that must hold:** (1) **Advisory only** — `insertion_mode` is a *candidate
position* (`figure_reference` / `table_reference` / `text_summary_reference` / `review_only` /
`unknown`), never a binding insert/embed decision; the real guide embedding is a later slice.
(2) **Anchors are presence-only and safe-only** — a source-page *anchor* is a slug-safe
reference id (e.g. `source_page_0001`), never a coordinate, raw layout, or raw text; the
optional inventory (list of `{source_page, anchor_id}`, dict keyed by page, or None) yields
only a sanitized `anchor_id`. A reference mode with a matching anchor → `anchor_status:"matched"`
+ placement `source_page_reference`; any miss (no inventory, uncovered page, or
dropped/invalid anchor id) → `anchor_status:"missing"` + placement `unknown` +
`anchor_lookup_missing`, and the item stays advisory — it must not be placed without an anchor.
An invalid/empty anchor id is **dropped, never emitted**. (3) **Chandra stays blocked** — a
`chandra_local` item (or one carrying a `chandra_blocked` marker on its input reasons) is
**never** mapped to a direct figure/table/text reference; it degrades to `review_only` +
`review_appendix` and always carries the closed reason `chandra_blocked`, because Chandra
*extraction* integration remains gated by Slice 45 `status:not_run`
(`operator_input_not_supplied`). (4) **No leak** — every emitted field is a closed-vocab token,
an int, `None`, an empty list, or a deterministic slug-safe `asset_id`/`anchor_id`; input
fields are coerced field-by-field and never echoed, so no caption, source/OCR text,
provider/model payload, image byte, data URI, base64, path, URL, header, token, socket path,
model/`mmproj` path, executable path, or raw argv can survive into the plan even from a hostile
record. (5) **Pure / unwired / no production change** — not imported by `run_llm_job.py` or
anything else; **no artifact written** (no `visual_insertion_plan.json` this slice); no API
route; no frontend/UI; no export-bundle/generic artifact-list exposure; the manifest / scoring
/ replacement-plan schemas are unchanged and **never mutated**, and the input replacement plan
and anchors are **never mutated**; no prompt/render/extraction/OCR-routing/guide-output change;
no `clean.md` write; no model/llama-server/cloud/network call; no image files/bytes. **Scope:**
new `pipeline/visual_insertion_planner.py` + `test_scripts/test_visual_insertion_planner.py`
(**243/0**) + this entry + `CURRENT_TASK.md` / `NEXT_CHAT_HANDOFF.md`. Because the slice is
pure/unwired and touches no server/extraction/render/artifact/export/UI behavior,
`smoke_release.py` / Docker were **not required**; validation was the full backend pure-test
battery (insertion-planner 243/0; replacement-planner 186/0; plan-artifact 68/0; scoring
146/0 + 58/0; manifest 65/0; figure 50/0+2skip; chandra 68/68/96; ocr 121/120/56), the offline
eval (3 guides, no regression), the frontend build + `npm run test` + advisory mjs, and
`git diff --check` clean.

## Slice 53 — True Anki `.apkg` export is built from stdlib (no `genanki`), reuses the existing export route, and embeds only user study text (Slice 53)

**Decision.** Add a real, importable Anki `.apkg` export for the *already generated* quiz /
flashcard items (`jobs/<id>/quizzes/<n>.json`) — `pipeline/anki_export.py` plus an `apkg` branch on
the **existing** `GET /api/jobs/{job_id}/quizzes/{quiz_n}/export` route and a one-line frontend button.
This delivers **direct user-visible study value** (import generated material straight into Anki)
without touching the high-risk visual render path, Chandra, OCR routing, extraction, or guide prompts.

**Why stdlib, not `genanki`.** An `.apkg` is just a ZIP containing a SQLite `collection.anki2` (Anki
**schema 11** — the long-stable, universally importable format) plus an empty `media` map, so the whole
package is built with `sqlite3` + `zipfile` + `json` + `hashlib` only. This (a) **adds zero
dependencies** (requirements.txt unchanged) — matching the repo's stdlib-only visual-advisory ethos and
avoiding `genanki`'s transitive deps and a Docker-image surface change; (b) keeps the focused test
**runnable on host Python** (no third-party install needed for `test_anki_export.py`), which `genanki`
would have prevented; and (c) keeps full control over **determinism**. The trade-off accepted: we own
schema-11 correctness rather than leaning on `genanki`'s battle-tested writer — mitigated by modelling
the `col`/`models`/`decks`/`dconf`/`conf` JSON on the known-good schema-11 layout and asserting
structure (tables, schema ver, note/card rows, field separator) in the test. Re-evaluate if a future
slice needs cloze/media/LaTeX, where `genanki` would carry more weight.

**Determinism / no-churn.** The note **model id is a fixed app-level constant** reused across every
export (Anki re-uses one model instead of accumulating one per import). The **deck id is a stable
SHA-256** of `"deck"+job_id+quiz_n` folded into a safe Anki id range (per-job deck under a
`GuideForge::<title>` subdeck). Note **GUIDs are index-based** (derived from internal ids — **never**
from private card text), and creation/mod **timestamps are fixed constants** (never the wall clock), so
re-exporting the same quiz is **byte-stable** and Anki **updates** rather than duplicates on re-import.
The Anki `csum` column is the format's required internal one-way duplicate checksum of the first field —
intrinsic to the format, not an externally meaningful id, so it is kept as the schema demands while the
deck/model/note/card ids themselves are never hashes of private text.

**No-leak / scope guards.** The package embeds only the user's own `Front`/`Back` study text
(**HTML-escaped**, newlines → `<br>`) plus a sanitized deck name from the guide title; `job_id` only
*seeds* derived numeric ids/guids/filename and is **never** written into the package. It never embeds
provider keys, headers, tokens, socket paths, local/host paths, executable paths, model/`mmproj` paths,
raw argv, raw OCR dumps, raw provider/model payloads, image bytes, data URIs, base64, artifact URLs, or
internal job-directory metadata. **No images/audio/media or LaTeX** in the deck this slice; **no FSRS /
in-app spaced repetition**. Malformed/empty cards are skipped with a closed-vocab count
(`skipped_empty` / `skipped_malformed`); **zero surviving cards → a valid empty-deck `.apkg`** (no
exception), matching the existing route's "empty export, not an error" behaviour. **CSV / anki_tsv /
quizlet exports are unchanged.** No guide-generation prompt, PDF/HTML/DOCX render, OCR-routing, or
extraction change; **Chandra extraction integration remains blocked by Slice 45 `status:not_run`**, and
visual render insertion remains a separate decision. **Scope:** new `pipeline/anki_export.py` +
`test_scripts/test_anki_export.py` (**46/0** host; route section runs in Docker) + one `apkg` branch in
`api/server.py` + one button in `frontend/src/components/RecentJobsPanel.jsx` + this entry +
`CURRENT_TASK.md` / `NEXT_CHAT_HANDOFF.md`. Because this touches the export route + frontend, full
validation (Docker rebuild/recreate + `/api/health` + `smoke_release.py`) is required.

## Slice 54 — the visual pilot inserts a *standard Markdown image*, behind an off-by-default flag, through the existing render path
After a long advisory-only build-up (manifest → scoring → replacement plan → insertion plan, none of
which ever touched a guide), Slice 54 takes the **smallest possible** real step: when
`GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT` is set, it inserts **at most one** existing `fitz_local`
`extracted_figure` (already cropped to `assets/<slug>.png` by Slice 40) into the guide as an ordinary
Markdown image `![safe caption](assets/<slug>.png)` and lets the **existing** machinery render it.
**Why a Markdown image and not a new visual subsystem:** the cheapest thing that could possibly prove
the path is the thing the renderers already understand. The investigation confirmed the existing
renderers already resolve a **job-local relative** `assets/<slug>.png` ref — PDF/HTML render from a
`file://` URI rooted at the job dir (so `final.html` resolves `assets/…` beside it) and the DOCX
renderer's `_resolve_image_path` already resolves the same relative ref against the job dir, degrading
to its existing `[image missing: …]` marker. So **no renderer was rewritten**; the pilot is purely an
insertion concern.

**Why off by default + degrade-never-fail.** Render risk is accepted only for this narrow pilot. With
the flag unset the helper is a no-op that returns the sanitized clean Markdown **byte-identical** without
reading any artifact, so default output is unchanged. With the flag on, *any* problem (no candidate,
unsafe ref, missing file, malformed artifact, insertion error) returns the original Markdown plus a
closed-vocab reason — a job can never fail because of the pilot. Reasons are stderr-only; nothing is
written to `job.json` and no generic artifact list changes.

**Why this exact integration point.** The helper is wired in `run_markdown_job.run_raw_markdown_pipeline`
immediately **before** `job.save_clean_md(...)` (`clean = sanitize(raw)` → `apply_visual_markdown_pilot`
→ `save_clean_md`). That keeps the **single `save_clean_md` chokepoint** intact — the figure is
snapshotted into version history like any other clean.md write — and means the same path is exercised by
generate / paste / markdown-upload jobs (the latter two simply have no manifest, so the pilot no-ops).

**Why the candidate/path rules are this strict.** `fitz_local` + `extracted_figure` only, ≤1; prefer a
replacement-plan `candidate_include_as_figure` item resolved in the manifest, else the first safe
manifest figure. The ref must be exactly `^assets/[A-Za-z0-9_]+\.png$` **and** a real file *inside* the
job dir (realpath-containment rejects symlink escapes); absolute / `..` / backslash / URL / `data:` /
base64 / subdir / non-PNG refs are rejected. The caption is a generic, length-limited, escaped,
page-only string — manifest captions are `None` in practice, so no raw caption / OCR text / provider
payload / path / URL / token / image byte / data URI can ever reach the guide. **Never Chandra**
(`chandra_local` or a `chandra_blocked` marker), **never** `mistral_ocr`, **never** `page_visual_signal`.
**Chandra extraction integration remains blocked by Slice 45 `status:not_run`.**

**Scope:** new `pipeline/visual_markdown_insertion.py` + one surgical wire-in in
`pipeline/run_markdown_job.py` + `test_scripts/test_visual_markdown_insertion.py` (flag-off **26/0**,
flag-on **50/0**) + `test_scripts/test_visual_markdown_render.py` (host-skippable HTML/PDF/DOCX) + this
entry + `CURRENT_TASK.md` / `NEXT_CHAT_HANDOFF.md`. **No** frontend toggle, export-bundle change, generic
artifact-list change, prompt change, OCR-routing change, extraction-behavior change, model/network call,
or renderer rewrite. Because this changes clean-markdown/render-output behavior behind a flag, full
validation (Docker rebuild/recreate + `/api/health` + `smoke_release.py` + a flag-on focused check) is
required.

## Slice 55 — the visual pilot is gated by TWO keys (env master switch AND per-job opt-in), default off
Slice 54 shipped the visual markdown image pilot behind a single global env flag. Slice 55 makes it
**user-controllable per job** without weakening the default-off safety, by requiring **both** gates,
AND-ed: the global env master switch `GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT` **and** an explicit
per-job opt-in (persisted manifest key `visual_markdown_image_pilot`, set from the new
`LLMJobRequest.enable_visual_references`). Truth table: only **(global on, job on)** may insert; (off,*)
⇒ `visual_pilot_disabled`; (on, job off) ⇒ `visual_pilot_job_opt_out`. Insertion is otherwise the
unchanged Slice 54 path (≤1 `fitz_local` `extracted_figure`, safe `assets/<slug>.png`, existing
renderers, degrade-never-fail, no Chandra, no renderer rewrite).

**Why the env switch is checked first and can never be bypassed.** `apply_visual_markdown_pilot` returns
on `is_visual_markdown_pilot_enabled()` being false **before** it ever reads the per-job option or any
artifact. So a hostile/eager request setting `enable_visual_references:true` is inert unless the operator
has *also* turned on the server-side master switch — the per-job control can only ever be the *second*
gate, never an escalation path. The request field is a strict `bool` (pydantic) and the stored option is
re-coerced to a strict bool on read (`true`/truthy-token only; missing key on a pre-Slice-55 job, or any
non-bool/malformed value, ⇒ false), so neither an old job nor a malformed payload can accidentally enable
it.

**Why only the LLM request carries the field.** Only LLM jobs with PDF attachments ever produce a
`fitz_local` `extracted_figure` (the manifest/`assets/` come from Slice 40 extraction). Paste and
markdown-upload jobs have no manifest, so adding the opt-in there would be a dead toggle — avoided per the
"no dead toggle" rule. The field is wired into **both** `_parse_llm_request` branches (JSON and multipart
via `_form_bool(..., False)`) per the standing `LLMJobRequest` dual-path rule.

**Why a non-secret capability flag + a disabled-with-note toggle.** `/api/options` now returns
`capabilities.visual_markdown_image_pilot` = the master-switch state (a single experimental on/off bit —
no key/token/path/URL). The Builder shows one experimental toggle **"Add one visual reference
(experimental)"**, default unchecked, **disabled with a short note when the capability is off**, so the
control is honest about when the server could honour it instead of silently no-op'ing. The payload/toggle
logic lives in a pure React-free helper `frontend/src/visualPilotOptIn.js` (`visualPilotPayloadFields`
sends `enable_visual_references` **only when on**, never serialises `false`, so a default/opted-out
request stays byte-equivalent) so it is node-testable without a DOM. Label avoids "AI images"/"visuals"
wording that would imply image *generation* — it adds at most one *extracted* figure.

**Scope:** `pipeline/visual_markdown_insertion.py` (+`is_job_visual_pilot_opt_in`, dual gate, new
`visual_pilot_job_opt_out` reason), `pipeline/run_llm_job.py` (+param, persists the manifest option),
`api/server.py` (request field + multipart parse + pass-through + capability flag),
`frontend/src/components/BuilderWorkspace.jsx` (state, capability fetch, one toggle, payload wiring),
`frontend/src/visualPilotOptIn.js` (new pure helper), tests
(`test_visual_markdown_insertion.py` truth-table + opt-in coercion → flag-off **53/0**, flag-on **77/0**;
`test_visual_markdown_render.py` negative-gate → **6/0,1skip**; new
`frontend/scripts/verify-visual-pilot-opt-in.mjs`), and the live docs. **No** image generation, broad
visual settings page, export-bundle/artifact-list/advisory-schema change, Chandra/Mistral/Gemini/cloud
image, prompt/OCR-routing/extraction/broad-render rewrite, model/network call, or `clean.md` write outside
`save_clean_md`. The env master flag stays required (not made optional) and the default stays off. Because
this touches backend request/UI/render-output behavior behind gates, full validation (Docker
rebuild/recreate + `/api/health` + `smoke_release.py` + a flag-on focused check) was run.
**Chandra extraction integration remains blocked by Slice 45 `status:not_run`.**

## Export bundles include only the single *referenced* visual-pilot PNG (Slice 56)
When a guide's `clean.md` contains the Slice 54 pilot's safe markdown image
reference `![caption](assets/<slug>.png)`, the export bundle includes **that one
referenced job-local PNG** (ZIP entry `<base_dir>/assets/<slug>.png`) so exported
Markdown/HTML stays portable. **Why include it at all:** a relative `assets/…`
image ref is dangling once the markdown leaves the app; shipping the one file it
points at is the minimal fix that makes the bundle self-contained. **Why only the
referenced one, by detection rather than by globbing `assets/`:** the `assets/`
directory can hold many cropped figures the guide never used; bundling the whole
directory would export unrelated image bytes and break the pilot's deliberate
one-figure boundary. Detection reuses the exact Slice 54 safety gate
(`validate_visual_asset_ref` → fixed `assets/<slug>.png` shape, then
`_asset_file_ok` realpath containment) so absolute paths, `..`, backslashes, URLs,
`data:`/base64, non-PNG, nested subdirs, and symlink escapes are all rejected, and
**at most one** PNG is ever added (the pilot inserts at most one).

**Boundary choices:** (1) the ride-along does **not** count toward
`files_included`/`total_included` — exactly like the Slice 51 advisory JSON
ride-alongs — so a job whose only "content" is the pilot PNG and which has **none**
of the requested artifacts still 404s (the PNG can never by itself satisfy the
"at least one requested artifact" gate). (2) The bundle index records only the
**safe relative ref** (`visual_pilot_asset: "assets/<slug>.png"` or `null`) — never
an absolute/local filesystem path and never image bytes. (3) Detection keys on the
**clean Markdown reference**, not on the presence of a file on disk, so unreferenced
or extra cropped images are never bundled. (4) Any problem (missing/unsafe file,
read error) is caught and the bundle still succeeds — degrade-never-fail, matching
the rest of the pilot.

**Scope:** `api/server.py` `export_bundle` only (plus two read-only helpers
`extract_visual_pilot_asset_refs` / `find_exportable_visual_pilot_asset` and a
`_read_text` reader in `pipeline/visual_markdown_insertion.py`) and a focused test
`test_scripts/test_visual_pilot_export_asset.py`. **No** frontend/UI, new API route,
generic artifact row, backend artifact-schema change, renderer/prompt/extraction/
OCR-routing change, Chandra/Mistral/Gemini/cloud, model/llama-server/network call,
image processing, image fixtures, or `clean.md` write. Existing Slice 51 advisory
JSON ride-alongs, Slice 53 Anki `.apkg`, and CSV/TSV quiz exports are unchanged, and
the default-off Slice 54/55 pilot gate is untouched. Because this changes
export-bundle/image-packaging behavior, full validation (Docker rebuild/recreate +
`/api/health` + `smoke_release.py` + the bundle-section focused test) was run.
**Chandra extraction integration remains blocked by Slice 45 `status:not_run`.**

## Visual-pilot readiness needs BOTH server switches; the Builder toggle is a UI affordance, not a gate (Slice 57)
The Builder's per-job visual opt-in (Slice 55) was previously enabled whenever the
**single** `visual_markdown_image_pilot` master flag was on. That is **misleading**:
the pilot inserts a `fitz_local` `extracted_figure`, and **new** jobs only produce
those figures when local figure extraction (`GUIDEFORGE_LOCAL_FIGURE_EXTRACTION`) is
**also** on. With the master flag on but extraction off, the toggle was an actionable
control that could never actually insert anything for a fresh job. **Decision:**
introduce a derived **readiness** signal = master flag **AND** local figure
extraction, surfaced as `/api/options.capabilities.visual_references_ready`, and let
the Builder enable its opt-in **only** when readiness is true, with a calm note
explaining which server switch is missing otherwise.

**Capability shape (non-secret booleans only):** `visual_markdown_image_pilot` is
**kept unchanged** (same meaning — master flag only — so existing consumers/tests
stay backward-compatible); `local_figure_extraction` and the derived
`visual_references_ready` are **added**. **Why only booleans / no env names:** the
public `/api/options` must never leak env-var names, paths, tokens, or raw config —
readiness is a UX hint, so it carries only fixed on/off state and (frontend-side)
fixed safe copy.

**Why readiness is a UI affordance, NOT a new backend gate:** the actual security
boundary stays exactly the Slice 55 dual gate — `apply_visual_markdown_pilot`
independently re-checks the master flag **and** the per-job opt-in just before
`save_clean_md`, and remains degrade-never-fail (it inserts nothing if no safe
`fitz_local` candidate exists, regardless of what `/api/options` reported). So a
stale/absent capability can only ever make the **toggle** wrong, never bypass a gate
or force insertion. The master env flag still **cannot be bypassed** from the
frontend, the per-job opt-in still defaults false, and the readiness flag is **not**
itself consulted by the insertion helper. Local figure extraction is **never**
auto-enabled and extraction is **never** run because the toggle is shown/checked.

**Frontend fallback:** `isVisualReferencesReady` trusts the backend's derived
`visual_references_ready` when present, else falls back to AND-ing the two component
booleans, so an older/partial `/api/options` payload degrades safely (a missing
component ⇒ not ready).

**Scope:** `/api/options` capability refinement (`api/server.py`) + two pure helpers
(`isVisualReferencesReady` / `visualPilotReadinessNote` in
`frontend/src/visualPilotOptIn.js`) + Builder wiring (`BuilderWorkspace.jsx`) +
focused tests (`test_scripts/test_visual_pilot_options.py`, updated
`frontend/scripts/verify-visual-pilot-opt-in.mjs`). **No** new page/route, broad
visual settings, export-bundle change, generic artifact-row change, advisory schema
change, renderer/prompt/extraction/OCR-routing change, Chandra/Mistral/Gemini/cloud,
model/llama-server/network call, image processing, image fixtures, or `clean.md`
write; the request still carries `enable_visual_references` **only** when the user
opts in (default/not-ready ⇒ byte-identical request). Because this touches
`/api/options` and Builder UI behavior, full validation (Docker rebuild/recreate +
`/api/health` + `smoke_release.py` + an `/api/options` readiness spot-check) was run.
**Chandra extraction integration remains blocked by Slice 45 `status:not_run`.**

## Validate the stitched single-figure pilot before expanding visuals (Slice 58)
The visual pilot was built as a chain of small slices (planner core 52, off-by-default
insertion 54, per-job opt-in 55, export ride-along 56, readiness guard 57), each with
its own focused test — but nothing proved the **whole chain** holds end-to-end. Slice 58
adds a **validation/harness-only** slice (`test_scripts/test_visual_pilot_e2e_validation.py`
+ `docs/VISUAL_PILOT_E2E_VALIDATION.md`) that stitches every stage so the output of each
feeds the next: safe job-local `assets/<slug>.png` → manifest/replacement-plan shape →
master flag ON → per-job opt-in ON → exactly one markdown image → HTML/PDF/DOCX render →
export ZIP carrying the single referenced PNG. **Why before expansion:** multi-figure,
Chandra, and richer visual work all build on this exact plumbing; proving the
single-figure path is clean first means an expansion regression shows up as a failing
stitch rather than a silent downstream surprise, and it pins the safety contract (one
figure, `fitz_local` only, safe relative ref, generic caption, no over-export, no leak)
as an executable spec.

**Why synthetic non-private temp data and no provider/model calls:** the harness must be
runnable anywhere (host or container) with zero network, zero secrets, and zero private
documents, so it builds its test PNG at runtime with a tiny stdlib `zlib`+`struct`
generator, writes every PNG/PDF/DOCX/HTML/ZIP under a temp dir, and imports only existing
pipeline helpers plus `api.server.export_bundle` (driven against temp-dir jobs with
`_get_job` monkeypatched). **No committed binary/image/PDF/DOCX/ZIP fixture, no base64, no
data URI**, and a final sweep scans every serialized output for paths/keys/tokens/headers/
sockets/data-URIs/model markers/argv/URLs. The harness adds **no** production code and
changes **no** behavior; it degrades cleanly (SKIP) when host deps (Chromium / python-docx
/ FastAPI) are absent, mirroring the repo's other host-skippable checks.

**Why multi-figure and Chandra stay deferred:** they are explicitly out of scope until the
single-figure path has a clean validation pass — which this slice establishes (host
**16/0/2**, in-container **29/0/0**). Manual operator PDF review is recorded honestly as
`manual_operator_pdf_validation: not_run` (reason `non_private_operator_sample_not_supplied`),
not asserted as done. **Chandra extraction integration remains blocked by Slice 45
`status:not_run`.**

## Add a manual operator validation harness before expanding visuals (Slice 59)
Slice 58 validated the stitched single-figure path with **synthetic** temp data. The next
gate before any visual expansion is a **real** non-private operator sample run through the
same path — so Slice 59 adds a manual, opt-in harness
(`test_scripts/validate_visual_pilot_operator_sample.py` + runbook
`docs/VISUAL_PILOT_OPERATOR_VALIDATION.md`) that drives the **genuine** pipeline
(`extract_local_figures` `fitz_local` → `write_visual_assets_manifest` →
`write_visual_asset_scoring_report` → `write_visual_replacement_plan_report` →
`apply_visual_markdown_pilot` via `save_clean_md` → HTML/PDF/DOCX render →
`export_bundle`). It adds **no** production code and changes **no** behavior. **Why a
separate harness rather than folding it into smoke:** a real operator PDF is private by
default and may be unavailable, so this must be **manual and opt-in** — it refuses to run
without `--pdf`, and ships a synthetic `--self-test` mode so CI/host can exercise the
harness (schema + no-leak) without any operator document.

**Why the real sample must be opt-in and non-private only:** the harness reads a real
user-supplied PDF, which is exactly the kind of material the project's no-leak rules
protect. It therefore (a) prints a non-private warning on every operator run, (b) **never**
prints or records the PDF path, basename, filename, document text, OCR text, image bytes,
base64, data URIs, full URLs, tokens, model/mmproj/executable paths, or raw argv, and
(c) writes all working files under a temp/output directory so nothing lands in the repo.

**Why the recorded output is sanitized closed-vocabulary:** validation results must be
safe to paste into a handoff, so the harness emits only a fixed ten-field summary
(`status`, `pilot_inserted`, `safe_asset_ref_present`, `html_render_ok`, `pdf_render_ok`,
`docx_render_ok`, `export_zip_ok`, `export_png_included`, `warnings`, `failure_category`)
plus closed-vocab step markers, with tri-state booleans (`true`/`false`/`null`=skipped).
**Exceptions are sanitized to closed `failure_category` tokens** — only an exception
*type name* is surfaced, never a message that could carry a path or private text — and a
final sweep scans every pipeline-derived string (incl. the summary) for forbidden shapes.
Missing host deps (PyMuPDF / Chromium / python-docx / FastAPI) **skip calmly** with
closed-vocab tokens rather than failing.

**Why multi-figure and Chandra stay deferred:** they build on this exact single-figure
plumbing, so they remain out of scope until a **real** operator validation pass is
recorded. This slice supplies the tool, and the harness's real extraction→insertion→
render→export path was first exercised in-container against a **throwaway synthetic** PDF
(proving the tool works). **Chandra extraction integration remains blocked by Slice 45
`status:not_run`.**

## Slice 59 real operator validation — RUN, successful (single-figure operator gate cleared)
The Slice 59 manual harness was subsequently run on **one real, non-private,
operator-supplied PDF**, and the result is recorded (sanitized) as
`manual_operator_pdf_validation: run` / `status: ok`, with `pilot_inserted: true`,
`safe_asset_ref_present: true`, `html_render_ok: true`, `pdf_render_ok: true`,
`docx_render_ok: true`, `export_zip_ok: true`, `export_png_included: true`,
`warnings: [multiple_figures_present_one_inserted]`, `failure_category: none`,
`no_leak_sweep: clean`. **Why this matters:** the `fitz_local` single-figure pilot found
**one or more** candidate figures in a genuine document and inserted **exactly one**,
proving the one-figure rule holds on real material; the `multiple_figures_present_one_inserted`
warning is **expected** and confirms the design rule was obeyed rather than indicating a
fault. **This clears the current single-figure visual-pilot operator-validation gate.**

**Why only sanitized fields are recorded:** the source was a real user document, so only
the fixed closed-vocabulary summary is written to the docs — no real PDF path, filename,
document text, OCR text, image bytes, base64, data URIs, full URLs, raw argv, tokens, or
raw exceptions. **Why this does NOT open multi-figure or Chandra:** clearing the
single-figure operator gate authorizes nothing beyond the existing one-figure pilot.
Multi-figure insertion is still **not** approved and stays out of scope until separately
designed, and **Chandra extraction integration remains blocked by its own live-validation
gate (Slice 45 `status:not_run`).**

## Visual pilot ranks for content quality, and "PDF ok" must mean a visible image (Slice 60)
The single-figure visual pilot originally inserted the **first** safe `fitz_local`
`extracted_figure` it found (replacement-plan preferred, else manifest order). Manual
operator review of one real, non-private sample showed two problems: extraction itself
was **mostly fine** (multiple usable table/figure crops), but the pilot picked a
**low-value chapter-title / title-page crop**, and the harness reported `pdf_render_ok:
true` even though the rendered PDF showed a **broken/missing image marker**, not a visible
embedded image. An earlier Slice 60 attempt added a *selection trace artifact*; that was
the wrong fix and was **parked (stashed, never committed)**.

**Decision A — rank, don't just take the first.** Before insertion, the already-safe
candidates are scored by a conservative **deterministic** quality gate
(`score_visual_markdown_candidate_for_pilot` / `rank_visual_markdown_candidates` /
`is_decorative_visual_candidate`) that uses **only already-available manifest metadata** —
`source_page`, `bbox`, and the `signals` page/crop dimensions. It prefers content-sized
figures and **drops confident decorative chrome** (title-page full crops, header/footer
banner strips, tiny logos/icons), while **preserving replacement-plan / manifest priority
order on ties and near-ties** (a rival displaces it only when clearly better, by a margin).
**Why metadata-only:** the gate must not read private document text, OCR text, captions,
source contents, or image bytes, and must not call any model/provider — so it can only use
fields the manifest already sanitized. **Why degrade-not-reject on sparse metadata:** a
genuine figure can lack page/crop dimensions; with metadata absent the gate returns a
neutral, non-decorative score so a good figure is never over-rejected. When **every** safe
candidate is decorative it **omits** rather than inserting junk (new closed reason
`visual_candidate_low_quality`, byte-identical guide). The **one-figure maximum**, the
default-off env master switch + per-job opt-in, all hard safety gates, and the
never-Chandra/Mistral/`page_visual_signal` rules are **unchanged**.

**Decision B — `pdf_render_ok` ≠ `pdf_image_visible`.** A non-empty rendered PDF does not
prove the inserted figure is visible; a broken/missing relative ref renders a **tiny
~14×16 broken-image placeholder icon** (or only alt text), not the figure. The operator
harness now reports a separate `pdf_image_visible` field, computed with PyMuPDF
`page.get_images(full=True)` and counting **only images ≥ 32 px on both sides** (True only
when a real, figure-sized image is embedded — the placeholder icon is filtered out), `null`
when PyMuPDF is unavailable. **Why a separate field, not a stricter `pdf_render_ok`:** the
two answer different questions ("did a PDF render" vs "is the figure actually embedded"),
and conflating them would have hidden exactly the failure manual review caught.

**Decision B-root-cause — the "broken PDF marker" was a harness layout artifact, not a
production bug.** `pdf_renderer.render_pdf` writes its intermediate HTML next to the
**output PDF** (`pdf.with_suffix(".html")`), and Chromium resolves the relative
`assets/<slug>.png` ref against **that** directory. **Production always renders to
`job.final_pdf`, a sibling of `clean.md` and `assets/`**, so the figure embeds correctly.
The Slice 59 manual harness wrote `operator_final.pdf` to the temp **base** dir (outside
the job dir), so `assets/` resolved to a non-existent path and Chromium embedded only the
placeholder icon — which is what manual review saw and recorded as `pdf_image_visible:
false`. **Fix:** the harness now renders **inside the job dir** (a sibling of `assets/`),
mirroring production. **Why not touch the renderer:** it is correct for the production
layout (and is load-bearing/tuned); the bug was purely the harness's output location.
Post-fix in-container `--self-test` reports `pdf_image_visible: true`.

**Why this does NOT open multi-figure or Chandra:** still **one figure maximum**; no
Chandra/Mistral/Gemini/cloud/model/provider/llama-server call; **Chandra remains blocked by
its own live-validation gate**. Only sanitized closed-vocabulary review fields are recorded
— pre-fix: `selected_figure_quality: decorative_or_low_information`, `pdf_image_visible:
false`, `docx_image_visible: true`, `failure_category: selection_quality_insufficient`,
`no_leak_sweep: clean`; post-fix (`--self-test`, same code path a real run uses):
`status: ok`, `pilot_inserted: true`, `pdf_image_visible: true`, `warnings: []`,
`failure_category: none`, `no_leak_sweep: clean` — no real PDF path/filename/text/OCR/image
bytes/base64/data URI. **Slice 60 is not committed.**

## Slice 61 — the post-fix operator visual-quality review is the decision gate for the next visual step
After Slice 60 fixed the quality gate and the PDF image-visibility check and reran the
real, non-private operator validation green (`status: ok`, `pilot_inserted: true`,
`pdf_render_ok: true`, `pdf_image_visible: true`, `docx_render_ok: true`, `export_zip_ok:
true`, `export_png_included: true`, `warnings: [multiple_figures_present_one_inserted]`,
`failure_category: none`, `no_leak_sweep: clean`), the one open question was **human**: is
the figure the gated pilot now selects actually worth showing? Slice 61 records that verdict
as a **docs/validation-record-only** slice — **no production code, frontend, export,
extraction/OCR routing, prompt, render, or route change; no multi-figure; no Chandra/model/
provider/cloud call; no committed binary/image/PDF/DOCX/ZIP/runtime output.**

**Why a separate review slice instead of folding the verdict into Slice 60.** Slice 60
deliberately left the human classification out so the code/validation slice could commit on
mechanical evidence alone, and the subjective figure-quality call could be made against the
**rebuilt** post-fix container with the operator inspecting the actually-rendered figure.
Keeping the verdict in its own slice also keeps it as an explicit, auditable **decision
gate** for the next visual step rather than a buried note.

**Recorded result (sanitized, closed vocab):**
`postfix_operator_visual_quality_review: run` · `status: ok` · `pilot_inserted: true` ·
**`selected_figure_quality: useful_diagram_or_table`** · `pdf_render_ok: true` ·
`pdf_image_visible: true` · `docx_render_ok: true` · `export_zip_ok: true` ·
`export_png_included: true` · `warnings: [multiple_figures_present_one_inserted]` ·
`failure_category: none` · `no_leak_sweep: clean`. The pre-fix Slice 60 review
(`decorative_or_low_information`, `extraction_candidate_quality: mostly_usable`,
`crop_quality: mostly_good_some_label_loss`, `pdf_image_visible: false`, `docx_image_visible:
true`, `failure_category: selection_quality_insufficient`) is preserved for comparison.

**Decision rule and outcome.** The closed vocabulary is `useful_diagram_or_table` ·
`acceptable_but_not_best` · `decorative_or_low_information` · `wrong_or_bad_crop` ·
`unclear`. A verdict of `useful_diagram_or_table` / `acceptable_but_not_best` clears the bar
to **cautiously consider multi-figure or improved placement next**; a verdict of
`decorative_or_low_information` / `wrong_or_bad_crop` / `unclear` means **keep improving
selection quality before any multi-figure work**. The recorded verdict is
`useful_diagram_or_table`, so the cautious-next-step branch applies — but only as a
**separately-designed slice**, still **one figure maximum** until that slice is scoped.
**Chandra remains blocked by its own live-validation gate** and is untouched here. Only
sanitized closed-vocabulary fields were recorded — no real PDF path/filename, document text,
OCR text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable
path, or raw exception. **Slice 61 is not committed.**

## Capped multi-figure visual pilot stops at two, default one (Slice 62)
The visual markdown image pilot can now insert **up to a small server-configured cap of
figures, with a hard upper bound of 2** — but the default stays **exactly one** and the
single-figure output is byte-identical to the pre-Slice-62 pilot. The cap is a server-side
env integer (`GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES`): default `1`, min `1`, hard max `2`;
any absent/empty/non-integer/`0`/negative/over-`2`/huge value **degrades to `1`** rather than
clamping upward. **Why a hard cap of 2 and degrade-down semantics:** Slice 61's post-fix
operator verdict (`useful_diagram_or_table`) cleared the decision gate to *cautiously* go
beyond one figure, but multi-figure selection is exactly where decorative/duplicate/same-page
junk can creep back in. Capping at 2 keeps the blast radius tiny and auditable; making a
malformed or over-large env value fail *closed* (to 1) means a fat-fingered or hostile config
can never widen the pilot. There is deliberately **no arbitrary N-figure support and no UI
count selector** — the cap is an operator-only server knob.

**Why the extra figures face a stricter bar than the first.** The first/strongest pick is the
unchanged single-best decision (it stands on its own even if only neutral quality). Every
*additional* figure must clear a **secondary quality floor** (`score ≥ 1.15`, i.e. genuinely
content-bearing under the reused Slice 60 gate), must not duplicate an already-selected
`asset_id` or `asset_ref`, and a **distinct source page is preferred** (a second figure from
the same page is taken only when no better alternative qualifies). So a lone good figure +
a decorative/low-quality runner-up still yields **one** figure, and an all-decorative set
yields **none** with a closed skip reason — the cap is never filled with junk. The strongest
figure always stays first.

**Insertion and export follow the same restraint.** One figure ⇒ the legacy singular
`## Visual Reference` placement, unchanged. More than one ⇒ each figure with a deterministic
`<!-- visual-anchor: source_page_NNNN -->` marker is placed at its anchor, and the rest are
appended together under a single trailing plural `## Visual References` section; captions stay
generic page-only (`Extracted figure from source page N`) — never source captions, OCR text,
document text, or image content. The export bundle rides along **all and only** the referenced
pilot PNGs (capped at 2, each resolved inside the job dir), never the whole `assets/` dir or an
unreferenced crop, and the PNGs **still do not** count toward the requested-artifact gate (a
pilot-PNG-only job with no requested artifact still 404s). The bundle index keeps the original
`visual_pilot_asset` (first ref or null) for backward compatibility and adds
`visual_pilot_assets` (the capped safe list). No Chandra/Mistral/Gemini/model/provider/cloud
call, no OCR-routing/extraction/prompt/renderer change, and no new API route were added.
**Chandra remains blocked by its own live-validation gate.**

## Cap-2 real operator validation confirms the cap-2 output is useful (Slice 63)
Slice 62 shipped the capped multi-figure pilot but validated cap-2 only **synthetically and in
Docker**; the optional **real** operator revalidation was not run there. Slice 63 ran the
existing manual harness against the same already-supplied **non-private** operator sample with
`GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2` inside the rebuilt container, then a human inspected
the rendered PDF/HTML/DOCX. **Recorded verdict: `selected_figures_quality:
all_useful_or_acceptable` with `inserted_visual_count: 2`** — both inserted figures were genuine
content-bearing material from **distinct source pages**, both rendered visibly and rode along in
the export bundle (closed-vocab record only; no path/filename/text/bytes recorded). **Why this
matters:** it closes the last gate Slice 62 left open and confirms the cap-2 *real* output is
worth showing, so future visual work **may cautiously** consider placement/UI polish or cap-2
documentation as a separately-designed slice — still **no arbitrary N-figure support and no UI
count selector**, and the default stays exactly one. A `mixed_quality` verdict would have meant
improve ranking/placement first; `decorative_or_bad_present`/`unclear` would have meant keep
doing selection-quality work before any expansion.

**Why one tiny harness correction was acceptable in a validation slice.** The operator harness
(`validate_visual_pilot_operator_sample.py`) hard-coded the export check to exactly one bundled
PNG (`len(png_entries) == 1`) — correct for the single-figure pilot, but it falsely reported
`export_png_included: false` once cap-2 legitimately bundled two referenced PNGs. The check now
ties the bundled-PNG count to the sanitized `inserted_visual_count` (within `1..2`), each still a
safe relative `assets/<slug>.png` ref. This touches **only the test harness** — no production
pipeline/API/frontend code, no schema, and no closed-vocabulary token changed; `--self-test`
(default cap, one figure) stays green and still records `export_png_included: true`. The
pre-existing `multiple_figures_present_one_inserted` warning token was **deliberately not
renamed**: its trigger (the source held more than one figure candidate) is still literally true,
the actual inserted count is recorded unambiguously in `inserted_visual_count`, and churning a
closed-vocab token is out of scope for a validation slice. **Chandra remains blocked by its own
live-validation gate.**

**The cap-2 pass cleared the *plumbing* but not visual-*type* priority — next slice ranks
diagrams over reconstructable tables (Slice 63 operator-review nuance).** The cap-2 result was
`all_useful_or_acceptable`, but the operator review recorded a load-bearing nuance with safe
closed-vocab tokens: `selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`,
`decision_gate: cap2_plumbing_passed_but_visual_type_priority_incomplete`,
`next_recommended_slice: prefer_diagrams_over_reconstructable_tables`. Both selected visuals were
**important tables**, not diagrams/figures. **Why this matters:** the visual/OCR feature exists
not merely to embed *any* useful crop but **especially to preserve visuals an LLM cannot reliably
recreate from extracted text**. Tables are frequently reconstructable from extracted text into
clean generated tables, so a table-only cap-2 result is genuinely useful yet leaves the
higher-value goal — preserving irreplaceable visuals (diagrams, flowcharts, screenshots, labeled
figures, network maps) — only partially met. **Decision:** the next visual slice is **not
placement/UI polish yet**; it should **improve visual-type ranking** so the pilot prefers
diagrams/figures over reconstructable tables when both are available, while still allowing tables
when they are the best/only useful visual. The constraints stay firm: **do not expand beyond cap
2, no UI count selector, and no Chandra/Mistral/Gemini/model/provider/cloud integration.** The
default remains exactly one figure. This refines (does not reverse) the "cap-2 output is useful"
conclusion above: the plumbing is proven; selection *quality by type* is the remaining work.

**Slice 64 — prefer hard-to-reconstruct diagrams/figures over reconstructable tables, by a
deterministic pixel-only visual-type ranking (ranking only, no expansion).** Acting on the Slice
63 nuance, the off-by-default visual pilot now ranks safe candidates by **visual type first,
existing metadata quality second**, using a closed vocabulary `diagram_or_figure >
reconstructable_table > unknown > decorative_or_low_information`. **Why:** tables are often
reconstructable from extracted text into clean generated tables, whereas diagrams/flowcharts/
screenshots/labeled figures/network maps are exactly the visuals an LLM cannot reliably recreate —
so when both are available the diagram/figure should win, while a good table is still selected when
it is the best/only useful visual. **How (kept conservative on purpose):** only the
**already-safe, already-job-dir-contained** `assets/<slug>.png` crop is opened (ref + realpath
containment re-validated first as defence in depth), read read-only with **Pillow**, converted to
grayscale, bounded-downscaled, and reduced to a handful of **bounded, non-sensitive** summary
features — size, aspect, near-white blank ratio, full horizontal/vertical rule counts, rough edge
density. A strong regular horizontal+vertical rule grid ⇒ `reconstructable_table`; substantial
non-grid graphic content ⇒ `diagram_or_figure`; near-empty / extreme banner with low edges ⇒
`decorative_or_low_information`; anything ambiguous ⇒ `unknown`. **Why this is safe:** the
classifier **never OCRs the crop, calls a model/provider/network, base64/serializes/logs image
bytes, records a path or source text, or adds an artifact** — it returns only a closed-vocab token
and bounded numerics into internal info dicts. **Why it cannot regress existing behavior:** if
Pillow is unavailable, the crop is unreadable/corrupt, or it is below the minimum analyzable size,
the type degrades to `unknown`, which makes the type priority uniform across candidates, so
selection reduces **byte-for-byte** to the prior Slice 60/62 quality-only pick (`_best_typed`
collapses to `_best_within_margin` when one tier is present). All hard invariants are unchanged:
default-off byte-identical output, the two-key gate, **default cap exactly 1**, **hard cap 2**,
`fitz_local`/`extracted_figure`-only, and the unsafe-ref / Chandra / Mistral / `page_visual_signal`
rejections. **Why no over-rejection:** a pixel-decorative candidate is ranked last but never
hard-dropped by pixels — the Slice 60 *metadata* gate remains the only hard decorative drop — so a
lone metadata-accepted candidate is still inserted (we do not try to "solve" computer vision, only
to break the diagram-vs-table tie when it is clear). **Scope discipline:** ranking only — no
arbitrary N-figure support, no UI count selector, no `/api/options` change, no extraction/OCR-
routing/prompt/render/export change, and **no Chandra/Mistral/Gemini/model/provider/cloud
integration**. Chandra remains blocked by its own live-validation gate. The optional **real**
operator revalidation was **not** run in this slice (no non-private sample available); its actual
`selected_visual_type` / `irreplaceable_visual_selected` result must be recorded only if/when the
harness is rerun, not assumed.

**Slice 65 — diagram-first ranking did not change the real-sample outcome; continue visual-type
*detection* before any UI/placement polish (validation record only).** The real operator
revalidation that Slice 64 deferred was run against the same non-private sample inside the rebuilt
Slice 64 container (cap 2, both enable gates), and the result was recorded **honestly as the actual
outcome, not the desired one**: `diagram_first_operator_visual_quality_review: run`, `status: ok`,
`pilot_inserted: true`, `inserted_visual_count: 2`, **`selected_visual_type: tables_only`**,
**`irreplaceable_visual_selected: false`**, `selected_figures_quality: all_useful_or_acceptable`,
all renders/export true, `warnings: [multiple_figures_present_one_inserted]`, `failure_category:
none`, `no_leak_sweep: clean`. **Why diagram-first did not help here:** the Slice 64 ranking only
re-orders candidates when its deterministic pixel classifier can separate a `reconstructable_table`
from a `diagram_or_figure`, and that table signal is a strong regular **horizontal *and* vertical**
rule grid. The visuals the pilot selected on this sample are **lightly-ruled** tables that do not
present a full grid, so the classifier did not tag them `reconstructable_table`; with no table
candidate to deprioritize, every safe candidate sat in the same visual-type tier and selection fell
back **byte-for-byte** to the prior Slice 60/62 quality-and-order pick. This is **not a
regression** — the classifier behaved exactly as designed (degrade-to-`unknown`/uniform-tier when
the signal is unclear); it simply had no clear table-vs-diagram signal to act on, so the
genuinely-irreplaceable visual content present elsewhere in the sample was not preferred.
**Decision:** because the real outcome is still `tables_only`, the next visual slice is **not** UI
or placement/citation polish; it should **continue visual-type work at the *detection* layer** —
strengthen table-vs-diagram classification so the ranking has a real signal (e.g. recognize
borderless / lightly-ruled tables as tables, and/or detect genuine diagrams/figures more strongly).
The constraints stay firm: **no expansion beyond cap 2, no arbitrary-N support, no UI count
selector, no extraction/OCR-routing/prompt/render/export change, and no Chandra/Mistral/Gemini/
model/provider/cloud integration**; the default remains exactly one figure and Chandra remains
blocked by its own live-validation gate. This refines (does not reverse) Slice 64: the ranking is
correct and proven synthetically, but on real material the **detection** that feeds it is the
binding constraint. The validation was **docs-only — no harness correction was needed** — and only
sanitized closed-vocabulary fields were recorded (no real PDF path/filename, document/OCR text,
image bytes, base64, data URI, full URL, raw argv, token, or model/mmproj/executable path), with no
binary/image/PDF/DOCX/ZIP/runtime output committed.

---

## Slice 66 — detect lightly-ruled / text-heavy tables as `reconstructable_table`, by a softer-ink text-band + column-gutter analysis, before any UI polish (Slice 66)

**Decision.** Slice 65 proved (on the real sample) that Slice 64's diagram-first ranking **did not change the
outcome**: the two selected visuals stayed **useful tables only** (`selected_visual_type: tables_only`,
`irreplaceable_visual_selected: false`), because the Slice 64 classifier recognized a table **only** from a
*strong full horizontal+vertical rule grid* — the sample's **lightly-ruled / text-heavy** tables stayed
`unknown`, so every candidate sat in one visual-type tier and the ranking had no signal. Acting on Slice 65's
`next_recommended_slice: improve_visual_type_detection_before_ui_polish`, Slice 66 strengthens the
**deterministic, local, pixel-only** visual-type *detection* (not the ranking, cap, or gates) so a lightly-ruled
/ reconstructable table classifies as `reconstructable_table` rather than `unknown`, giving the existing
diagram-first ranking a real signal to act on.

**How.** One file (`pipeline/visual_markdown_insertion.py`). The bounded grayscale feature summary
(`_summarize_gray_pixels`) gained, alongside the existing near-black rule/edge features, a **softer-ink**
(`_LT_INK`, mid-gray — chosen because downscaled antialiased printed text never reaches the near-black `_VT_DARK`
threshold, which is precisely why the real tables fell to `unknown`) horizontal **text-band rhythm** and a
vertical **column-gutter** structure (pure helpers `_profile_runs`, `_runs_regular`, `_count_col_blocks`). A new
`_looks_like_reconstructable_table(...)` predicate is consulted in `_classify_visual_type_from_features`
**after** the strong-grid table rule and **before** the diagram rule, via two **dual-signal** paths — each
deliberately requires more than one independent table cue so a diagram's incidental banding can never qualify:
(a) **text-grid** — a regular repeated text-band rhythm *and* a multi-column gutter structure (rows arranged in
columns, no drawn rules needed); (b) **lightly-ruled** — multiple full horizontal rules *without* a strong
vertical-rule grid, backed by either the row rhythm or the column structure. A genuine diagram (irregular row
spacing, no clean full-height column gutters, no repeated horizontal rules) satisfies neither and stays
`diagram_or_figure`.

**Why this shape.** It keeps every Slice 64 hard limit: pixel-only over the already-safe, already-job-dir-
contained crop; **no OCR, no model/provider/network/cloud, no `llama-server`, no image generation, no OCR-routing
change**; never base64/serializes/logs image bytes; never records a path or source text; **adds no artifact**; and
**degrades to `unknown`** (byte-identical fallback to the prior Slice 60/62 quality-only selection) whenever
Pillow is absent or the crop is unreadable / too small. The diagram-first **ranking**, the two-key gate, the
**default cap 1 / hard cap 2** (server-side only), the `fitz_local` / `extracted_figure`-only restriction, the
unsafe-ref / Chandra / Mistral / `page_visual_signal` rejection, the decorative-rejection dominance, the
default-off byte-identical output, and the export ride-along are all **unchanged** — Slice 66 only sharpens the
signal that ranking already consumes. **Tables remain allowed when they are the best/only useful visual.**

**Constraints (unchanged and firm):** no expansion beyond cap 2, no arbitrary-N support, no UI count selector, no
frontend/UI change, no `/api/options`/route change, no extraction/prompt/render/export-behavior change, and no
Chandra/Mistral/Gemini/model/provider/cloud integration; Chandra stays blocked by its own live-validation gate.

**Validation.** New `test_scripts/test_visual_pilot_light_table_detection.py` (runtime-built tiny PNG fixtures in
temp dirs, never committed) covers the classifications, ranking outcomes, decorative rejection,
unknown-preserves-prior, analysis-failure degrade, unsafe-ref / blocked-provider exclusion, determinism, the
two-key gate, default-off byte-identical, default-1 / hard-cap-2, export ride-along, and a full no-leak sweep.
Host + **in-container** (Pillow 12, no skips) suites are green and Docker `build`+`up`+`/api/health`+`smoke_release`
pass. **Optional real operator revalidation was NOT run** (the non-private sample is unavailable this session); the
desired flip to `selected_visual_type: diagrams_or_figures_present` / `irreplaceable_visual_selected: true` is
**not assumed** and must be confirmed by re-running the cap-2 operator harness when the sample is available,
recorded only if true. Only sanitized closed-vocabulary tokens + bounded numeric features were recorded (no real
PDF path/filename, document/OCR text, image bytes, base64, data URI, full URL, raw argv, token, or
model/mmproj/executable path), and nothing binary/image/PDF/DOCX/ZIP/runtime was committed.

## Slice 67 — improved-light-table operator validation RAN; real sample still selects tables only, so add a selection trace before more heuristics
The optional real operator revalidation Slice 66 deferred (does the strengthened lightly-ruled-table detector let
diagram-first ranking pick a hard-to-reconstruct diagram/figure on the **real** sample?) was completed in Slice 67.
The non-private operator sample was available again, so the cap-2 operator harness **was** run inside the rebuilt
Slice 66 container (`GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1`, `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION=1`,
`GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`); the rendered PDF/HTML/DOCX were copied to a host folder and inspected by
hand. Recorded result: `light_table_operator_visual_quality_review: run`, `status: ok`, `inserted_visual_count: 2`,
`selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`, `selected_figures_quality:
all_useful_or_acceptable`, all render/export checks `true`, `warnings: [multiple_figures_present_one_inserted]`,
`failure_category: none`, `no_leak_sweep: clean`.

**Why this shape.** Slice 66 improved the synthetic / light-table detection tests, but on the real sample the
strengthened detection did **not** change the selection: the two inserted visuals are still **useful/acceptable but
reconstructable tables**, and the genuinely irreplaceable visual content elsewhere in the sample was **not**
selected. The verdict is recorded honestly as the actual result, not a pass — consistent with the Slice 63/65
honesty rule. Because `selected_visual_type: tables_only` / `irreplaceable_visual_selected: false`, **visual-type
selection is still not solved for the real sample.** `decision_gate:
light_table_detection_did_not_change_real_outcome`.

**Decision — instrument before tuning.** Rather than pile on another detection/ranking heuristic blind, the next
visual slice should **add a sanitized selection trace / candidate audit** so a run can explain *why* diagrams were
not selected (which candidates existed, their classified visual type, and why the chosen tables outranked them) — in
closed-vocab / bounded-numeric form only, no path/text/bytes. `next_recommended_slice:
add_sanitized_selection_trace_before_more_heuristics`. **Do not proceed to UI polish or cap expansion.** **Do not**
expand beyond the existing hard cap 2, add a UI count selector, or add
Chandra/Mistral/Gemini/model/provider/cloud/`llama-server` integration.

**Scope (firm).** Docs-only: `VISUAL_PILOT_OPERATOR_VALIDATION.md`, `CURRENT_TASK.md`, `NEXT_CHAT_HANDOFF.md`, this
file. No production pipeline/API/frontend code, no harness correction, no new visual behavior, no cap change beyond
the existing hard cap 2, no UI count selector, no Chandra/Mistral/Gemini/model/provider/cloud/`llama-server` call,
no extraction/OCR-routing/prompt/render/export change, no new API route. Only the sanitized closed-vocabulary fields
were recorded — no real PDF path/filename, document text, OCR text, image bytes, base64, data URI, full URL, raw
argv, token, model/mmproj/executable path, or provider payload — and nothing binary/image/PDF/DOCX/ZIP/runtime was
committed. **Slice 67 is NOT committed.** Chandra remains blocked by its own live-validation gate.

## Slice 68 — instrument before tuning: add a sanitized visual-pilot selection trace / candidate audit
Slice 67 reran the real post-Slice-66 cap-2 operator sample and it STILL selected two useful-but-reconstructable
tables only (`selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`); no irreplaceable
diagram/figure was chosen. The honest conclusion is that the bottleneck is no longer cap, UI, or another blind
heuristic — it is **visibility**: we cannot tell, on a real run, whether diagrams are being mis-**classified** (the
type detector calls them `unknown`) or correctly classified but mis-**ranked/capped**. So Slice 68 adds a
bounded, sanitized **candidate-audit artifact** instead of tuning another heuristic in the dark.

**What it is.** A single job artifact `visual_markdown_selection_trace.json`, written by
`apply_visual_markdown_pilot` only when BOTH gates are on (global env master switch AND per-job opt-in) AND
candidate selection was attempted — including the no-candidate / low-quality skip, which is exactly the case worth
auditing. It is **diagnostic only**: the selection/ranking core (`_pick_candidates` / `_best_typed`), the cap
reader, the default, and the two-key gate are byte-for-byte unchanged. The trace is built by an independent,
read-only pass (`build_visual_markdown_selection_trace` → `_summarize_trace_candidates`) that re-applies the same
hard safety gates and the existing quality + visual-type classifiers purely to *describe* the decision; it never
influences it. Build and write are wrapped degrade-never-fail — a trace problem can never fail generation and
leaves no partial file.

**Why this shape.** The trace answers, safely: was the pilot skipped or inserted; what effective cap was used; how
many safe vs unsafe candidates existed; how many were selected; what visual types were found; did the selection
include diagrams or only tables; and why each candidate was selected, rejected, or deprioritized. It does this with
a whitelisted top level (`schema_version`, `status`, `reason`, `effective_max_images`, `inserted_visual_count`,
`selected_candidates`, `candidate_summary`, `warnings`), safe per-selected-candidate fields (`asset_id`, safe
`assets/<slug>.png` `asset_ref`, `source_page`, `source_provider`, `visual_type`, `visual_type_score`,
`classification`, `quality_score`, `quality_reasons`, `placement`, `rank`, `selected`, `selection_reason`), and a
counts-only `candidate_summary` (`total_manifest_assets`, `safe_candidate_count`, `unsafe_candidate_count`,
`selected_count`, `type_counts`, `rejection_reason_counts`). Full per-candidate detail is emitted **only** for the
selected candidates; rejected/unsafe candidates contribute to counts only, which keeps the leak surface minimal.
All reasons are closed-vocabulary tokens (`selected_by_diagram_first_ranking` · `selected_by_quality_ranking` ·
`selected_by_priority_order` · `rejected_low_quality` · `rejected_unsafe_ref` · `rejected_wrong_provider` ·
`rejected_wrong_asset_type` · `rejected_duplicate_asset_ref` · `rejected_duplicate_asset_id` ·
`rejected_secondary_below_quality_floor` · `deprioritized_reconstructable_table` · `classified_*`).

**No-leak (firm).** The trace carries ONLY closed-vocabulary tokens, bounded integers / rounded floats, and the
already-safe `assets/<slug>.png` ref. It NEVER carries an absolute path, the source document filename, document /
OCR / caption / extracted-table text, image bytes, base64, a data URI, a raw provider payload, a raw exception, a
raw URL, a token, raw argv, or a model/mmproj/executable path. Chandra / Mistral / page_visual_signal candidates
are counted and rejected with closed tokens, never written raw. Export is unchanged — the ride-along allowlist is
PNG-only and name-based, so the new JSON never bundles.

**Scope (firm).** One production file (`pipeline/visual_markdown_insertion.py`) plus one new test
(`test_scripts/test_visual_pilot_selection_trace_sanitized.py`, 20-point coverage). No frontend/UI, no
`/api/options`, no extraction/OCR routing / prompt / render / export behavior change, no new API route, no cap
change beyond the existing hard cap 2, no UI count selector, and no Chandra/Mistral/Gemini/model/provider/cloud/
`llama-server` call. The old parked Slice 60 trace stash was **not** applied or dropped — this is a clean
reimplementation from current trunk. Validation: `compileall` OK; full visual-pilot suite + operator self-test +
insertion/render/export/anki/options + `eval --offline --all` green host-side; container rebuilt + recreated,
`/api/health` `{"ok":true}`, `smoke_release.py` 29/29, in-container suite green (selection-trace 56/0, light-table
66/0, type-ranking 64/0, multifigure 78/0, quality-gate 54/0, operator self-test PASS); `git diff --check` clean.
Only sanitized closed-vocabulary fields were recorded — no real PDF path/filename, document text, OCR text, image
bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable path, or provider payload — and nothing
binary/image/PDF/DOCX/ZIP/runtime was committed. **Slice 68 is NOT committed.** Chandra remains blocked by its own
live-validation gate.

## Slice 69 — the selection trace localizes the real bottleneck to *classification*, not extraction or ranking
Slice 68 added the sanitized selection trace specifically so a real run could answer the question Slices 63/65/67
could not — *why* the non-private operator sample keeps selecting reconstructable tables instead of irreplaceable
diagrams — without leaking source material. Slice 69 ran that trace on the real sample (cap 2, both enable gates,
inside the rebuilt Slice 68 container) and read it. **This is a validation/docs slice; no heuristic was tuned, and
no production pipeline/API/frontend code, ranking, cap, default, gate, render, export, extraction, or OCR routing
was changed.**

**What the trace showed (sanitized).** `selection_trace_operator_audit: run` · `status: ok` ·
`trace_artifact_present: true` · `trace_no_leak_sweep: clean` · `effective_max_images: 2` ·
`inserted_visual_count: 2` · `safe_candidate_count: 11` · `unsafe_candidate_count: 0` · `selected_count: 2`. The
decisive field is `type_counts`: **all 11 safe candidates were classified `diagram_or_figure`** —
`reconstructable_table: 0`, `unknown: 0`, `decorative_or_low_information: 0`. Manual inspection of the rendered
PDF/HTML/DOCX ground-truths the discrepancy: the two selected visuals are clean two-column definition/glossary
**tables** (`selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`, `selected_figures_quality:
all_useful_or_acceptable`), and at least one genuinely irreplaceable schematic diagram **was present among the safe
candidates but was not selected**.

**Why tables still win — the mechanism, finally explained.** The deterministic pixel visual-type classifier
**over-accepts**: it labels reconstructable definition tables (and decorative banners and code boxes) as
`diagram_or_figure` alongside the genuine schematic. With every candidate carrying the same `visual_type_score: 3`,
Slice 64's diagram-first ranking has **no discriminating signal**, so selection falls back to pure quality score —
and the clean, content-sized definition tables (`quality_score: 1.2`) outrank the real diagram.
`selection_explanation: tables_misclassified_as_diagram_or_figure`. This is the **classification** branch of the
Slice 68 decision tree, not extraction (diagrams are present and extracted) and not a blind ranking/threshold
change (ranking is correct but starved of signal).

**Decision / next work.** The next visual slice is `improve_visual_type_classification_table_vs_diagram_precision`:
strengthen the local, pixel-only classifier so reconstructable tables are separated from genuine diagrams, giving
diagram-first ranking a real signal on the real sample. **Do not** proceed to UI polish or cap expansion until an
irreplaceable diagram/figure is actually selected in real validation, or there is a deliberate product decision to
accept tables. The trace is **sufficient** to localize the bottleneck; its per-candidate rejection-reason coverage
is sparse (only `rejected_secondary_below_quality_floor: 1` for the nine unselected safe candidates), which is a
possible future *trace* refinement but not a reason to guess heuristics. **Do not expand beyond hard cap 2; no UI
count selector; no Chandra/Mistral/Gemini/model/provider/cloud/`llama-server` call.**

**Scope / no-leak (firm).** Docs only — `VISUAL_PILOT_OPERATOR_VALIDATION.md`, `CURRENT_TASK.md`,
`NEXT_CHAT_HANDOFF.md`, and this file; **no harness correction was needed**. The trace was inspected for leaks
**before** any field was transcribed, and only the sanitized closed-vocabulary + bounded-numeric fields above were
recorded — no real PDF path/filename, document text, OCR text, source caption/table text, image bytes, base64, data
URI, full URL, raw argv, token, model/mmproj/executable path, or provider payload. The runtime
`visual_markdown_selection_trace.json` was inspected but **not committed**, and nothing
binary/image/PDF/DOCX/ZIP/runtime was committed. **Slice 69 is NOT committed.** Chandra remains blocked by its own
live-validation gate.

## Slice 70 — fix table-vs-diagram *classification precision*, not ranking, to break the `tables_only` deadlock
Slice 69's selection trace conclusively localized the visual-pilot bottleneck to **classification**: all 11 safe
candidates were classified `diagram_or_figure` while the two selected visuals were, by manual inspection,
reconstructable two-column definition/glossary **tables**, so diagram-first ranking (Slice 64) had no signal and
the clean tables won on quality (`selection_explanation: tables_misclassified_as_diagram_or_figure`). The decision
gate from Slice 69 was explicit — `improve_visual_type_classification_table_vs_diagram_precision`, **not** extraction
(diagrams were present and extracted) and **not** a blind ranking/threshold change (ranking was correct but
signal-starved). Slice 70 implements exactly that and nothing more.

**Root mechanism.** A glossary/definition table has **variable-height rows** (multi-line definitions wrap), so its
horizontal text bands are *not* evenly spaced. Slice 66's text-grid table path requires a *regular* row rhythm
(`row_band_regular`) and therefore missed it; with no drawn rules the lightly-ruled path missed it too; so the crop
fell through to `diagram_or_figure`. The fix had to recognize a two-column table **without** assuming regular row
spacing, while still keeping a labeled diagram a diagram.

**What was added.** One bounded, deterministic, pixel-only feature — **`two_col_split`** — computed from the same
already-safe, already-job-dir-contained crop the Slice 60/64/66 gates already validated. It returns 1.0 only when
ALL hold: (a) exactly **two** substantial text columns (each ≥ a width fraction), (b) separated by a **real gutter**
(whitespace, or a thin drawn divider that leaves the separator band narrow), (c) both columns carry real ink, and
(d) **each** column independently contains several **separated horizontal text bands**. Condition (d) is the
deliberate guard that keeps a labeled diagram a diagram — a diagram's "columns" are continuous shapes (one or two
bands) and its connectors/diagonals smear ink across the middle, so it rarely presents two clean text columns; text
presence alone never flips a diagram. Row-spacing **regularity is intentionally not required**, which is precisely
what now catches variable-height glossary/definition rows. A new third path in
`_looks_like_reconstructable_table` consumes the feature; everything else (strong-grid path, Slice 66 text-grid /
lightly-ruled paths, decorative/low-info guards, diagram fallback, degrade-to-`unknown`) is unchanged.

**Why classification, not ranking/cap.** With tables correctly typed `reconstructable_table` (priority 2) and
diagrams `diagram_or_figure` (priority 3), the existing diagram-first ranking does the rest unchanged: a diagram
beats a reconstructable table at cap 1; at cap 2 one of each selects both with the diagram first; two diagrams plus
a table selects the two diagrams; tables are still selected when best/only. No ranking, cap, default, two-key gate,
`/api/options`, render, export, extraction, OCR routing, prompt, or frontend code was touched, and no
model/provider/cloud/`llama-server` call was added. The Slice 68 selection trace reflects the improved
classification automatically (`type_counts` no longer collapse to one bucket) with **no artifact schema change**.

**Boundaries / no-leak (firm).** Cap stays hard-capped at **2**, default stays **1**; `fitz_local` +
`extracted_figure` only; safe `assets/<slug>.png` only; file-inside-job-dir gate; Chandra/Mistral/
`page_visual_signal` still rejected; degrade-never-fail (no Pillow / unreadable / too-small ⇒ `unknown`, prior
behavior). The classifier never OCRs, never base64/serializes/logs image bytes, never records a path or source text,
and adds no artifact. New focused test `test_scripts/test_visual_pilot_table_diagram_precision.py` (24-point
coverage) builds every PNG at runtime in a temp dir — nothing binary/image/PDF/DOCX/ZIP/runtime is committed, and no
real PDF path/filename, document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token,
model/mmproj/executable path, or provider payload appears anywhere. **Slice 70 is NOT committed.** Chandra remains
blocked by its own live-validation gate.

## Slice 71 — real-sample validation: Slice 70 improved classification but the sample is still `tables_only`
Slice 70 fixed the deterministic table-vs-diagram classifier so two-column/glossary/definition tables type as
`reconstructable_table`, giving diagram-first ranking a signal. Slice 71 reran the existing manual operator harness
on the same real, **non-private** sample (cap 2, both enable gates, inside the rebuilt container) and read the
sanitized selection trace plus a human inspection of the rendered PDF/HTML/DOCX. **This is a validation/docs slice;
no heuristic was tuned and no production pipeline/API/frontend code, ranking, cap, default, gate, render, export,
extraction, or OCR routing was changed.**

**What the trace + manual inspection showed (sanitized).** `table_diagram_precision_operator_validation: run` ·
`status: ok` · `trace_no_leak_sweep: clean` · `effective_max_images: 2` · `inserted_visual_count: 2` ·
`safe_candidate_count: 11` · `unsafe_candidate_count: 0` · `selected_count: 2`. The decisive change vs Slice 69 is
`type_counts`: it is **no longer collapsed** — `diagram_or_figure: 9` **and** `reconstructable_table: 2` (Slice 69
read `diagram_or_figure: 11`, `reconstructable_table: 0`), and the two typed tables were correctly **deprioritized**
(`deprioritized_reconstructable_table: 2`). So Slice 70 was a real, measurable improvement. **But manual inspection
ground-truths that both *selected* visuals are still reconstructable two-column definition tables**
(`selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`, `selected_figures_quality:
all_useful_or_acceptable`), and genuine irreplaceable diagrams/figures **were present and correctly extracted among
the safe candidates but were not selected**.

**Why tables still win — the residual mechanism.** The two selected definition tables are **densely ruled with
wrapped multi-line description cells**. Slice 70's two-column-split guard requires several *separated* horizontal
text bands **per column**; in a wide description column the wrapped lines merge into too few bands, so the guard does
not fire and those specific tables still type as `diagram_or_figure`. Appearing first in priority order within the
(now larger-than-it-should-be) diagram tier, they are selected ahead of the real diagrams.
`selection_explanation: tables_still_misclassified_as_diagram_or_figure`. This is still the **classification** branch
— diagrams are present and extracted (so not `diagrams_absent_from_safe_candidates`), and ranking is correct but the
type signal for these dense ruled tables is still wrong.

**Decision / next work.** The next visual slice is `continue_table_vs_diagram_classification_precision`: keep
improving the deterministic local classifier for densely-ruled / wrapped-text two-column tables, or design a
separate, controlled understanding layer in its own slice. **Do not** proceed to UI polish or cap expansion until an
irreplaceable diagram/figure is actually selected in real validation, or there is a deliberate product decision to
accept tables. **Do not expand beyond hard cap 2; no UI count selector; no
Chandra/Mistral/Gemini/model/provider/cloud/`llama-server` call.** Do not guess heuristics — the trace plus manual
ground-truth localize the exact residual case.

**Scope / no-leak (firm).** Docs only — `VISUAL_PILOT_OPERATOR_VALIDATION.md`, `CURRENT_TASK.md`,
`NEXT_CHAT_HANDOFF.md`, and this file; **no harness correction was needed**. The trace was inspected for leaks
**before** any field was transcribed, and only the sanitized closed-vocabulary + bounded-numeric fields above were
recorded — no real PDF path/filename, document text, OCR text, source caption/table text, image bytes, base64, data
URI, full URL, raw argv, token, model/mmproj/executable path, or provider payload. The runtime
`visual_markdown_selection_trace.json` was inspected but **not committed**, and nothing
binary/image/PDF/DOCX/ZIP/runtime was committed. **Slice 71 is NOT committed.** Chandra remains blocked by its own
live-validation gate.

## Slice 72 — dense ruled / wrapped-cell two-column tables: gutter-persistence + text-richness, not band count
Slice 71's real-sample validation localized the residual failure precisely: Slice 70's `two_col_split` classifier
split the type buckets (`diagram_or_figure: 9`, `reconstructable_table: 2`) but the two *selected* visuals were still
reconstructable **dense ruled / wrapped-cell** two-column definition tables. The mechanism: `two_col_split` requires
≥ `_TT_MIN_COL_ROWS` (3) *separated* horizontal text bands **per column**, and a densely-ruled column of wrapped,
antialiased definition text leaves no clean blank separator rows — its bands merge into one or two, so the guard never
fires and the table falls through to `diagram_or_figure` and leads the diagram tier.

**Decision: add a band-count-independent signal, guarded by structure a diagram cannot fake.** Slice 72 adds one more
bounded, deterministic, pixel-only feature — `dense_wrapped_two_col` — and a fourth `_looks_like_reconstructable_table`
path. Rather than counting bands (the very thing wrapping destroys), it pairs the two-column layout with two strong
discriminators: (1) a **persistent clean vertical gutter** (`_gutter_consistency`: the gutter band must be clear of ink
for ≥ `_DW_GUTTER_CONSISTENCY_MIN` = 0.75 of rows — a diagram's connectors / diagonals / shapes cross the middle and
break it; a thin drawn divider or a few full-width rules are tolerated), and (2) per-column **text richness**
(`_column_text_richness`: average ink-runs per inked row ≥ `_DW_MIN_COL_RICHNESS` = 2.5 — real text has several
short runs (words) per row, while a continuous diagram shape outline contributes only one or two long runs). It fires
only when there are exactly two substantial content columns, both carrying dense ink, separated by a real gutter, with
both columns text-rich. Row-spacing regularity is intentionally not required, so variable-height wrapped rows qualify.

**Why richness rather than the relaxed band count.** An earlier attempt relaxed the per-column band requirement from 3
to 2; that misclassified a *labeled diagram* (two shape clusters either side of a gap, each ~2 bands) as a table. Text
richness is the correct text-vs-shape discriminator and was measured to separate the two cleanly on representative
fixtures (text columns ≈ 3–8 runs/row; diagram-shape columns ≈ 1.0–1.7), so the relaxation does not weaken the diagram
guard. The signal is wired *inside* `_looks_like_reconstructable_table`, so the public closed-vocabulary classification
token and the Slice 68 selection-trace schema are unchanged; the trace reflects the improved classification
automatically.

**Invariants preserved.** Diagrams/figures still outrank reconstructable tables (a diagram wins at cap 1 and ranks
first at cap 2); tables are still selected when best/only; default cap stays 1, hard cap stays 2; the two-key gate,
default-off byte-identical output, render pipeline, export ride-along, extraction/OCR routing, prompts, and
`/api/options` are all unchanged; no model/provider/cloud/`llama-server` call; no UI/frontend change. The classifier
still degrades to `unknown` (prior behavior) whenever the crop cannot be analyzed (no Pillow, unsafe ref, unreadable or
too-small image), and never raises.

**Validation.** `compileall api pipeline test_scripts` clean; new
`test_visual_pilot_dense_wrapped_table_detection.py` (81 PASS, cap-1 + cap-2) plus the full visual-pilot suite,
`validate_visual_pilot_operator_sample.py --self-test`, insertion/render/export/options/anki tests, and the offline
eval all pass on host; the production image was rebuilt + recreated, `/api/health` `{"ok":true}`, `smoke_release.py`
29/0/0, and the visual-pilot suite re-run **inside the container** (Pillow present, no skips) all green;
`git diff --check` clean. **Optional real operator revalidation was NOT run** — the non-private sample is unavailable
this session, so no sanitized operator result was recorded (none invented).

**Scope / no-leak (firm).** Code + test + docs only — `pipeline/visual_markdown_insertion.py`, new
`test_scripts/test_visual_pilot_dense_wrapped_table_detection.py`, and `CURRENT_TASK.md` / `NEXT_CHAT_HANDOFF.md` /
this file. The feature produces only bounded numeric pixel summaries and closed-vocabulary tokens; it never OCRs, never
calls a model/provider/network, never base64/serializes/logs image bytes, records no path or source text, and adds no
new artifact (the Slice 68 trace is the only one). Every test PNG is built at runtime in a temp dir — nothing
binary/image/PDF/DOCX/ZIP/runtime committed; runtime eval result JSONs stay gitignored; no real PDF path/filename,
document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable path, or
provider payload appears anywhere. **Slice 72 is NOT committed.** Chandra remains blocked by its own live-validation
gate.

## Slice 73 — dense-wrapped-table real operator validation flipped the real sample to diagrams (2026-06-13)
Slices 63/65/67/69/71 each recorded the same honest real-sample outcome — the visual pilot selected only
`reconstructable_table` visuals (`selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`) — even as
the synthetic classification work progressed (Slice 69 localized the cause to classification; Slice 70 split the type
buckets; Slice 71 isolated the residual case to dense, ruled, wrapped-multi-line two-column definition tables). Slice 72
added the deterministic, pixel-only `dense_wrapped_two_col` signal to fix that case synthetically. **Slice 73 reran the
existing operator harness on the real, non-private sample with Slice 72 on trunk and recorded — for the first time — a
flipped result: both selected visuals are diagrams/figures.**

**Why a separate validation/docs slice.** Per the established discipline (no heuristic tuning in a validation slice),
Slice 73 changed no production pipeline/API/frontend code, no ranking/cap/default/gate/render/export/extraction-OCR
routing, and added no model/provider/cloud call. It only drove the existing harness (cap 2, both enable gates) inside
the rebuilt container, read Slice 68's sanitized selection trace, and manually inspected the rendered PDF/HTML/DOCX. No
harness correction was needed.

**Recorded result (sanitized, closed vocab).** `dense_wrapped_table_operator_validation: run`, `status: ok`,
`trace_artifact_present: true`, `trace_no_leak_sweep: clean`, `effective_max_images: 2`, `inserted_visual_count: 2`,
`safe_candidate_count: 11`, `unsafe_candidate_count: 0`, `selected_count: 2`,
`type_counts {diagram_or_figure: 9, reconstructable_table: 2, unknown: 0, decorative_or_low_information: 0}`,
`selected_visual_type: diagrams_or_figures_present`, `irreplaceable_visual_selected: true`,
`selected_figures_quality: all_useful_or_acceptable`, `selection_explanation: diagrams_selected_after_dense_table_fix`,
all render/export booleans `true`, `warnings: [multiple_figures_present_one_inserted]`, `failure_category: none`,
`no_leak_sweep: clean`.

**What the trace showed.** `type_counts` still reads `diagram_or_figure: 9` / `reconstructable_table: 2`, but the two
reconstructable definition tables Slice 71 had *selected* are now deprioritized behind the diagram tier
(`rejection_reason_counts.deprioritized_reconstructable_table: 2`), so Slice 64's diagram-first ranking reaches the
genuine schematic figures. Both selected candidates are `classified_diagram_or_figure` with `selection_reason:
selected_by_diagram_first_ranking`; manual ground-truth confirms both are legible, content-bearing, non-decorative
graphics from distinct source pages that render visibly in PDF/DOCX and ride along in the export ZIP.

**Decision / next work.** `decision_gate: irreplaceable_diagram_selected_on_real_sample`. Because an irreplaceable
diagram/figure is finally selected on the real sample, future visual work **may** now consider placement/citation polish
as a separately-designed slice (`next_recommended_slice: visual_placement_or_citation_polish_may_now_be_considered`) —
a *may*, not a mandate; classification precision can be revisited if other samples regress. Had the output stayed
tables-only, the guidance would have been to continue classification precision or design a controlled understanding
layer; had diagrams been absent from the safe candidates, the guidance would have been to inspect extraction/candidate
generation. **Do not** expand beyond cap 2 (default stays 1, hard cap stays 2); no UI count selector; no
Chandra/Mistral/Gemini/model/provider/cloud integration; no OCR-routing/renderer/prompt/export change. Chandra remains
blocked by its own live-validation gate. The `multiple_figures_present_one_inserted` warning is the existing
closed-vocab token (fires whenever the source held more than one figure candidate); its `_one_inserted` suffix is a
known legacy misnomer under cap 2 and renaming it stays out of scope for a validation slice.

**Note on Slice 72 status.** Slice 72 (the entry above, which recorded itself as NOT committed at authoring time) was
committed `5a23852` and fast-forward merged + pushed to trunk `chrome-renderer-v1` before Slice 73 began; that entry is
left unedited per this file's append-only rule.

**Scope / no-leak (firm).** Docs only — `VISUAL_PILOT_OPERATOR_VALIDATION.md`, `CURRENT_TASK.md`,
`NEXT_CHAT_HANDOFF.md`, and this file. Only sanitized closed-vocab + bounded-numeric fields were recorded — no real PDF
path/filename, document text, OCR text, source caption/table text, image bytes, base64, data URI, full URL, raw argv,
token, model/mmproj/executable path, or provider payload. The runtime `visual_markdown_selection_trace.json` was
inspected but not committed; nothing binary/image/PDF/DOCX/ZIP/runtime committed. **Slice 73 commit `76e837b`,
fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

## Slice 74 — visual caption / source-page polish is the final in-lab visual-pilot polish (2026-06-13)
Slice 73 achieved the desired real-operator outcome after the dense wrapped-table fix:
`selected_visual_type: diagrams_or_figures_present`, `irreplaceable_visual_selected: true`, and
`selection_explanation: diagrams_selected_after_dense_table_fix`. That flips the long-running table-vs-diagram
morphology loop from active investigation to **paused after real success**. Slice 74 therefore intentionally adds only
one small user-visible polish and does **not** start another classification, caption, or placement heuristic loop.

**Decision.** Add safe generic source-page captions below inserted visuals, then stop in-lab visual-pilot polish for
now. The status for the next session is `visual_pilot_morphology_loop_status: paused_after_real_success`,
`visual_pilot_polish_scope: final_in_lab_caption_page_polish`, and
`next_recommended_slice: diverse_visual_pilot_exit_validation`. There should be **no separate caption-validation
follow-up slice** and no more table/diagram heuristic work unless diverse validation shows a new regression.

**Implementation.** Inserted visuals now render as the unchanged Markdown image reference followed by a safe italic
caption line. When a positive source page is available, the caption is exactly `*Source visual, page N.*`; otherwise it
falls back to `*Source visual.*`. Both insertion paths use the same helper, so the appended visual-reference section and
source-page-anchor placement behave consistently.

**Safety.** Captions are fixed generic strings plus a bounded page integer only. They never include source
filename/path/title, raw manifest caption, OCR/document/table text, base64/data URI, provider payload, token, URL,
image bytes, or private content. Caption construction degrades-never-fails to the image ref alone. Optional real
operator caption validation was not run: `caption_operator_validation: not_run`, `reason:
non_private_operator_sample_not_available`; no result was invented and no sample path/filename/source contents/image
bytes were recorded.

**Invariants.** No selection, ranking, classification, cap, default, two-key gate, export, renderer,
provider/model/cloud, OCR-routing, prompt, or UI behavior changed. Image refs, selected order/count/ranking, default-off
output, export ref scanning, and the Slice 68 selection trace schema remain unchanged. Default remains 1; cap remains
hard-capped at 2. Chandra remains blocked by its own live-validation gate; no model/provider/cloud call was added.

**Validation.** `test_visual_pilot_caption_page_polish.py` passes on host and container; the full
visual-pilot/insertion/render/export/options/anki/eval checks pass; Docker rebuild/recreate, `/api/health`, and
`smoke_release.py` pass. The host may skip the DOCX render branch when `python-docx` is unavailable; the container run
has the dependency and records no skips.

**Next.** No caption micro-loop. Next recommended slice: `diverse_visual_pilot_exit_validation` across multiple
document types to decide whether visual markdown remains opt-in, becomes more discoverable, or pauses pending a
controlled understanding layer such as Chandra.

## Slice 75 — diverse visual-pilot exit validation recorded insufficient evidence (2026-06-13)
Slice 75 was created as an exit-decision checkpoint for the default-off visual markdown pilot after Slice 73's
real-sample success and Slice 74's final in-lab caption/source-page polish. It was explicitly **not** another
caption-polish slice, not another table/diagram morphology heuristic slice, and not a UI slice. The morphology loop
remains paused, the caption micro-loop is not starting, and Chandra remains blocked by its own live-validation gate.

**Availability result.** `diverse_visual_pilot_exit_validation: not_run`, `reason:
non_private_diverse_samples_not_available`. An operator-local sample count was present, but no safe manual mapping from
samples to the requested closed categories was available in this session. A sample count alone is not a category
assignment, and the slice rules forbid guessing categories from local PDFs. No harness run was performed and no
trace/render/export artifacts were produced.

**Recorded category status.** The target categories `math_heavy_deck`, `mostly_text_only_pdf`,
`low_quality_or_scan_like_pdf`, `mixed_diagrams_tables_deck`, and `no_good_figures_deck` were each recorded as
`status: skipped`, `skip_reason: sample_not_available`, `failure_category: sample_unavailable`, with
`trace_artifact_present: not_applicable`, `trace_no_leak_sweep: not_applicable`, `effective_max_images:
not_applicable`, zero candidate/selected/type counts, render/export fields `not_applicable`, `warnings:
[sample_unavailable]`, and `no_leak_sweep: clean`.

**Aggregate decision.** `validated_category_count: 0`, `available_category_count: 0`, `pilot_inserted_count: 0`,
`graceful_omission_count: 0`, `bad_selection_count: 0`, `caption_safe_count: 0`, `pdf_image_visible_count: 0`,
`docx_render_ok_count: 0`, `export_png_included_count: 0`, `no_leak_sweep: clean`, `exit_recommendation:
insufficient_evidence`, `exit_reason: diverse_validation_insufficient_sample_count`.

**Scope / no-leak.** Docs only — `VISUAL_PILOT_OPERATOR_VALIDATION.md`, `CURRENT_TASK.md`, `NEXT_CHAT_HANDOFF.md`, and
this file. No production pipeline/API/frontend code changed; no harness was added; no selection, classification,
ranking, cap, caption, export, renderer, OCR-routing, prompt, provider/model/cloud, or UI behavior changed. No
Chandra/model/provider/cloud call. No committed binary/image/PDF/DOCX/ZIP/runtime output, eval JSON, or selection
trace. No sample path/filename, document text, OCR text, source caption/table text, image bytes, base64, data URI, full
URL, provider payload, token, raw argv, model/mmproj/executable path, or raw exception was recorded. **Slice 75 commit
`00c3f79`, fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

## Slice 76 — source coverage report starts as a pure no-leak core (2026-06-13)
Slice 76 adds a source coverage report builder as a Trust-pillar measurement primitive after Slice 75 honestly recorded
`diverse_visual_pilot_exit_validation: not_run` / `exit_recommendation: insufficient_evidence`. This is deliberately
not another visual-pilot loop: morphology and caption work remain paused, and Chandra remains blocked by its own
live-validation gate.

**Decision.** Build the report as a separate pure core first:
`pipeline.source_coverage_report.build_source_coverage_report(extraction_metadata, *, visual_manifest=None)`. It
consumes the existing `extraction_metadata.json` shape (`version: 2`, `kind: "extraction_metadata"`, completed/skipped
status, source records with page counts and sanitized page method/count/anchor fields) plus optional
`visual_assets_manifest.json`-shaped dictionaries. It emits only `version: 1`, `kind: "source_coverage_report"`,
summary counts, per-source counts/status, and closed warning tokens.

**Why no filenames/source text.** Coverage is meant to answer whether sources/pages were represented, not what the
private source was. Existing extraction metadata may contain a filename, and hostile input may contain paths, titles,
document text, OCR text, table text, captions, image refs, provider payloads, tokens, URLs, raw argv, socket paths, or
model/mmproj/executable paths. The core never copies those fields. Warnings are closed vocabulary tokens only, and
malformed input degrades to skipped/partial reports without raw exception messages.

**Why defer artifact writing/UI.** Persisting `source_coverage_report.json`, adding JobDetails display, exports, or API
routes would widen the behavioral surface. This slice proves the deterministic report shape and no-leak boundary first.
A future slice may write the artifact after extraction, but this slice changes no job execution, no `clean.md` writes,
no extraction/OCR routing, no renderer, no export, no frontend/UI, and no prompt/provider/model/cloud behavior.

**Why not visual-pilot continuation.** Optional visual-manifest input is counts-only (`source_page` coverage) and never
emits asset ids, image refs, captions, bbox values, provider details, or source text. It is included only so the Trust
report can later summarize whether visual candidates existed; it does not change visual insertion, selection, ranking,
classification, caps, defaults, two-key gates, captions, rendering, or exports. **Slice 76 commit `91e3845`,
fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

## Slice 77 — source coverage report is persisted as the first Full Material Coverage foundation artifact (2026-06-13)
Slice 76 was committed `91e3845`, fast-forward merged, and pushed to trunk. Slice 77 wires that pure core into backend
job artifacts as the exact-name JSON file `source_coverage_report.json`.

**Decision.** Persist source coverage as an exact-name sibling artifact first, not as a generic UI row or export
selector. The writer lives in `pipeline/source_coverage_artifact.py`, uses
`build_source_coverage_report(extraction_metadata, *, visual_manifest=None)`, writes under the job directory through
`Job.source_coverage_report_json`, and is called from `_attach_sources` only after extraction metadata and the optional
visual manifest are available. The exact-name route maps `source_coverage_report.json`; `ARTIFACTS`, generic JobDetails
rows, export selectors, and export ZIP ride-alongs are unchanged.

**Full Material Coverage direction.** `source_coverage_report.json` is the first foundation artifact for future Full
Material Coverage work: page/slide include-exclude controls, all useful non-table figure/diagram/graph inclusion from
included pages, table reconstruction/simplification, and coverage-aware guide generation. Slice 77 implements none of
those behaviors; it only makes safe coverage measurement persist for later consumers.

**Why defer UI/JobDetails/export surfacing.** This artifact is a measurement boundary. Surfacing it in generic
JobDetails, generic artifact lists, or export bundles would create product and privacy decisions before the coverage
model is stable. Exact-name download is enough for tests and future slices while keeping user-visible behavior stable.

**Why filenames/source text are excluded.** Coverage needs counts and statuses, not private source identity or content.
The persisted report intentionally excludes filenames, paths, source titles, source text, OCR text, source captions,
table text, image refs, image bytes, base64/data URI, provider payloads, tokens, raw argv, sockets, model/mmproj/
executable paths, URLs, and raw exception messages. Warnings remain closed vocabulary only.

**Why generation must degrade-never-fail.** Coverage reporting is advisory measurement. A build/write/readback failure
must never block guide generation, extraction, rendering, exports, prompts, or provider calls. The writer catches
failures, emits only safe skipped report shapes when possible, and `_attach_sources` guards the call site as well.

**Out of scope.** No frontend/UI, no `clean.md` write, no extraction/OCR routing change, no render/export/prompt/
provider/model/cloud behavior change, no Chandra/Mistral/Gemini call, and no visual-pilot selection/ranking/
classification/cap/default/two-key-gate/caption behavior change. Chandra remains blocked by its own live-validation
gate. **Slice 77 is NOT committed.**

## Slice 78 — page/slide inclusion-exclusion starts as a pure model (2026-06-14)
Slice 77 was committed `3ebfe54`, fast-forward merged, and pushed to trunk `chrome-renderer-v1`; it persisted
`source_coverage_report.json` as a safe exact-name artifact. Slice 78 adds the pure, deterministic model for
representing user-controlled page/slide inclusion and exclusion per attachment, in stdlib-only
`pipeline/page_selection_model.py` (`normalize_page_selection`, `apply_page_selection`, `summarize_page_selection`).

**Why a pure model first.** Page/slide include-exclude is the user-facing knob behind the revised Full Material Coverage
direction, so its normalization, edge-case handling, and no-leak boundary must be proven in isolation before any
request schema, job manifest, extraction path, visual/table manifest, UI, or render/export depends on it. A pure core
keeps the behavioral surface unchanged while pinning the contract (modes, warnings, determinism) that later wiring
slices will rely on.

**Why 1-based and deterministic.** Users and source documents count pages/slides from 1, and the existing extraction
metadata / visual manifest already speak in 1-based page numbers, so the model matches that vocabulary instead of
introducing a 0-based offset that callers would have to translate. All outputs are deduplicated and sorted so repeated
calls and equivalent inputs produce byte-identical results — a precondition for stable artifacts, tests, and future
diffs.

**Why invalid pages degrade with warnings rather than raising.** This model will eventually sit on the
attachment/request boundary where input is user- and document-derived and may be malformed, hostile, out of range, or
absent. Raising would let an advisory selection knob break extraction or generation, which violates the same
degrade-never-fail rule the source coverage artifact already follows. Instead, malformed input returns a safe normalized
output with closed-vocabulary warning tokens (`selection_missing`, `selection_malformed`, `mode_unknown`,
`page_invalid`, `page_out_of_range`, `page_count_invalid`, `include_empty`, `exclude_overlaps_include`) and never copies
raw exception messages, filenames, paths, document/OCR/table text, captions, image refs/bytes, base64/data URI, provider
payloads, tokens, raw argv, sockets, model/mmproj/executable paths, or URLs.

**Why production wiring/UI are deferred.** Persisting the selection with job requests, surfacing Builder controls, and
applying exclusions to extraction/content planning and visual/table manifests each carry product, privacy, and pipeline
decisions that would widen the surface before the core is stable. Slice 78 therefore changes no API route, no request/
job-manifest schema, no job execution, no extraction/OCR routing, no visual manifest behavior, no render/export, no
prompt, no provider/model/cloud call, and writes no `clean.md`.

**Why this is Full Material Coverage, not a visual-pilot cap expansion.** The model governs which source pages/slides
feed both generated content and extracted visuals/tables — it is upstream of, and independent from, visual-pilot
selection/ranking/classification/caps/defaults/two-key gating/captions. It deliberately does not touch any of that
behavior; it is a coverage-control primitive, not a change to how the existing visual pilot picks or inserts assets.
Chandra remains blocked by its own live-validation gate. **Slice 78 is NOT committed.**

## Slice 79 — persist the page/slide selection with job requests before applying it (2026-06-14)
Slice 78 was committed `ee04f55`, fast-forward merged, and pushed to trunk `chrome-renderer-v1`; it added the pure
page/slide inclusion-exclusion model. Slice 79 persists that normalized model with job requests/manifests via a new
top-level `material_page_selection` field on `LLMJobRequest`, normalized through `normalize_page_selection` and stored in
the job manifest (and round-tripped through retry). It is applied to nothing yet.

**Why persistence comes before applying page exclusions.** Applying exclusions touches extraction, content planning, and
visual/table manifests — each a behavioral and privacy decision. Persisting the normalized intent first gives later
slices (Builder UI load/save, extraction/content application, visual/table application) a stable, tested contract to
build on, while keeping job output byte-identical today. It also lets the Builder round-trip and retry/rerender preserve
user intent before any of that intent changes a guide.

**Why a new field separate from `page_selections`.** There is already a load-bearing, filename-keyed `page_selections`
field (`{filename: [[start, end], ...]}`) that drives PDF page-range extraction, is validated by
`_normalize_page_selections` (which 400s on bad shapes), and is wired through both request paths and retry. Reusing or
re-normalizing it would risk changing current extraction behavior. Slice 79 therefore adds a clearly named,
future-facing `material_page_selection` carrying the Slice 78 normalized shape, leaving `page_selections` entirely
unchanged (verified by the unchanged `test_page_selections.py`). A single top-level model is the smallest safe shape
that can persist include/exclude intent now; a per-attachment `material_page_selections` mapping is deferred and, when
added, will key on safe indices/internal IDs — never filenames or paths.

**Why both JSON and multipart request paths must be wired.** `POST /api/jobs/llm` has two request-construction paths
that do NOT share parsing: a JSON body path and a multipart/form-data path used when the request carries attachments.
Per the standing rule (and prior page_selections experience), a field added to only the JSON path is silently dropped
whenever a generation has an attachment. `material_page_selection` is parsed in the multipart `_parse_llm_request`
branch (as a JSON string, like `page_selections`/`include_sections`) as well as the JSON path, and both are exercised in
`test_page_selection_request_persistence.py`.

**Why the persisted schema avoids filenames/paths and uses normalized safe page integers.** Coverage intent only needs a
mode plus sorted/deduped positive 1-based page integers. The persisted/echoed model is the Slice 78 closed-vocabulary
shape and never carries filenames, paths, document/OCR/table text, captions, image refs/bytes, base64/data URI, provider
payloads, tokens, raw argv, sockets, model/mmproj/executable paths, URLs, or raw exception strings — proven with
hostile-canary tests over both the manifest and the API response. Unlike `_normalize_page_selections`, the material
field degrades-never-fails on malformed *content* (no 400) so an advisory coverage knob can never block job creation.

**Why UI/application is deferred.** Surfacing controls in the Builder and actually applying exclusions to
extraction/content/visuals/tables are separate product decisions with their own validation needs. Slice 79 keeps the
surface minimal: it stores and echoes the normalized model and preserves it across retry, and changes no extraction/OCR
routing, content/guide generation, visual manifest, render, export, prompt, provider/model/cloud behavior, or
visual-pilot selection/ranking/classification/cap/default/two-key-gate/caption behavior, and writes no `clean.md`
directly. Chandra remains blocked by its own live-validation gate. **Slice 79 is NOT committed.**

## Slice 80 — per-attachment material selections, keyed by safe attachment indices (2026-06-14)
Slice 79 was committed `d4d2513`, fast-forward merged, and pushed to trunk `chrome-renderer-v1`; it persisted the
top-level `material_page_selection`. Slice 80 adds a future-facing per-attachment field, `material_page_selections`,
persisted as the deterministic envelope `{version, attachments: {attachment_<index>: <Slice 78 model>}, warnings}`. It
is applied to nothing yet.

**Why per-attachment persistence is needed before Builder UI.** The Builder lets a user attach several files and will
need to express different page/slide include-exclude intent per attachment. Building that UI against a guessed backend
shape risks a rewrite; persisting the correct per-attachment model first gives the UI slice a stable, tested contract to
save into and load from (including across retry), while keeping job output byte-identical today.

**Why an envelope instead of a flat `{key: model}` map.** The rule "ignored unsafe key → closed warning" has nowhere to
live in a flat map without echoing the rejected key — and a rejected key may itself be a filename or path, i.e. a leak.
The envelope carries a top-level closed-vocabulary `warnings` list (`selections_malformed`, `attachment_key_invalid`)
alongside the per-attachment `attachments` map, so we can report that something was dropped without ever copying what was
dropped. The normalizer accepts both a flat client-supplied map and the persisted envelope on input, so retry
re-normalization round-trips.

**Why keys are internal attachment indices and not filenames/paths.** Persisted keys must never carry private source
identity. Filenames, paths, and source titles are user-controlled and could leak document identity into a stored
artifact, an API response, or a future export. Keys are therefore restricted to `attachment_<index>` (matched by
`_MATERIAL_ATTACHMENT_KEY_RE`, canonicalized so `attachment_00` collapses to `attachment_0`); the index corresponds to
request attachment order, which the Builder/back end already track without exposing names. Any other key is dropped with
`attachment_key_invalid` and never appears in output — verified by hostile-canary tests over the manifest and the
response.

**Why the top-level `material_page_selection` remains as fallback.** Removing or repurposing the Slice 79 field would be
a behavior change and would strand a coverage knob that may still be useful as a single global default (e.g. "exclude
the cover page of everything"). The documented precedence is: per-attachment `material_page_selections` is the preferred
intent when present, with the global `material_page_selection` as fallback/default. Slice 80 persists both (after
normalization) but applies neither — no merge into extracted page ranges happens yet.

**Why existing `page_selections` extraction behavior is preserved.** The load-bearing, filename-keyed `page_selections`
field still drives PDF page-range extraction and still 400s on bad shapes. Slice 80 adds a separate, clearly-named field
and touches none of that path; the unchanged `test_page_selections.py` (24/24) is the regression guard.

**Why application/UI are deferred.** Surfacing controls in the Builder and applying exclusions to extraction, content
planning, and visual/table manifests are separate product and privacy decisions with their own validation needs. Slice
80 keeps the surface minimal: normalize, persist, echo, and preserve across retry. It changes no extraction/OCR routing,
content/guide generation, visual manifest, render, export, prompt, provider/model/cloud behavior, or visual-pilot
selection/ranking/classification/cap/default/two-key-gate/caption behavior, and writes no `clean.md` directly. Chandra
remains blocked by its own live-validation gate. **Slice 80 is NOT committed.**

## Slice 81 — apply material selections to text extraction first, bounded by `page_selections` (2026-06-14)
Slice 80 was committed `55eb243`, fast-forward merged, and pushed to trunk `chrome-renderer-v1`; it persisted
per-attachment `material_page_selections`. Slice 81 is the first slice that *applies* the persisted material selection —
to attachment text extraction / content planning only — by filtering the page set passed to the existing
`extract_file(path, pages=...)` in `_attach_sources`.

**Why material selections are applied to content extraction before UI.** Extraction is where page selection actually
changes what the model sees, and it can be implemented and tested deterministically behind the already-stable persisted
model and the existing `extract_file(pages=...)` mechanism — no UI, prompt, render, or provider change required. Proving
the apply path first (with monkeypatched extraction capturing the effective `pages`) gives the later Builder UI slice a
working backend to drive, and keeps the risky, user-facing UI work decoupled from the extraction semantics.

**Why existing `page_selections` remains the maximum allowed universe.** `page_selections` is load-bearing and already
drives PDF page-range extraction; users (and a future Builder) may use it to bound a large deck before anything else
runs. Letting a material selection expand beyond it would silently re-introduce pages the user already excluded and
could blow past large-PDF guards. So the rule is strict subtraction: `include` intersects the existing universe,
`exclude`/`all` subtract from it, and the effective set is always a subset of `page_selections` when that field is
present. The new pure helper `apply_material_selection_to_page_universe` enforces this and never raises.

**Why per-attachment selection overrides global fallback.** Different attachments need different page intent (e.g.
"only slides 10–20 of deck A, all of handout B"). A per-attachment entry, when present, is therefore authoritative for
that attachment — even a per-attachment default-all, which intentionally suppresses the global selection so a user can
say "this one attachment: everything" while a global exclusion applies elsewhere. Absent a per-attachment entry, the
global `material_page_selection` is the fallback; absent both, default-all (no filtering).

**Why an unknown universe defers instead of guessing.** An `exclude`/`all` selection needs a concrete page universe to
enumerate "everything except N". Before extraction the natural page count is not known without re-reading the PDF (which
this slice deliberately avoids), and re-reading/guessing risks both correctness and large-PDF cost. When there is no
`page_selections` universe to bound an `exclude`/`all` selection, filtering is deferred (extraction unchanged) and
`material_selection_universe_unknown` is recorded — degrade-never-fail. `include` needs no universe because the include
list is itself the explicit page set, so it always applies (then `extract_file` validates it against the real count).

**Why visual/table manifest application is deferred to the next slice.** The visual-assets manifest, scoring, and
replacement-plan writers consume extraction metadata and have their own sanitization and advisory-only contracts.
Applying selections there is a separate behavioral surface (and must not perturb visual-pilot selection/ranking/caps),
so it is its own slice. Slice 81 touches only which pages are extracted into model-facing text; it makes no
visual-manifest, visual-pilot, render, export, prompt, or provider change, adds no Chandra/Mistral/Gemini/model/provider/
cloud call, and writes no `clean.md` directly.

**Why this is Full Material Coverage foundation work, not a visual-pilot heuristic loop.** This slice is about honoring
explicit user page/slide intent end-to-end (persist → apply to extraction), the backbone of the coverage direction. It
is upstream of and independent from the visual pilot's heuristic asset selection; it changes none of that behavior. The
per-attachment summary persisted on each attachment entry is counts/closed-tokens only — no page lists, filenames, or
paths — keeping the no-leak boundary intact. Chandra remains blocked by its own live-validation gate. **Slice 81 is NOT
committed.**

## Slice 82 — apply material selections to the visual manifest, after extraction, bounded by `page_selections` (2026-06-14)
Slice 81 was committed `7ca109d`, fast-forward merged, and pushed to trunk `chrome-renderer-v1`; it applied material
selections to attachment text extraction. Slice 82 applies the *same* effective page selection to visual-assets manifest
planning: `_attach_sources` keeps a `visual_page_filters` list in lockstep with `extraction_metadata_sources` (each entry
the effective post-material allowed page set when a selection was applied, else `None`), and passes it as a new
`page_filters=` kwarg to `write_visual_assets_manifest`, which drops `page_visual_signal` candidates whose `source_page`
is not in their source's allowed set.

**Why material selections are applied to visual manifests after content extraction (and reuse the extraction set).**
The visual-assets manifest derives from the same sanitized extraction metadata as the model-facing text; in fact
`extract_file(pages=...)` already skips unselected pages, so the manifest *already* only sees selected pages as a Slice 81
side effect. Slice 82 makes that an explicit, independent, testable manifest-level contract (defense-in-depth) by reusing
the very set Slice 81 computed for extraction. Reusing one effective set — rather than recomputing intent at the visual
layer — guarantees text and visuals agree about which pages are in scope and removes any chance of the two drifting.

**Why existing `page_selections` remains the maximum allowed universe.** Identical reasoning to Slice 81:
`page_selections` is load-bearing and already bounds PDF extraction. Because the visual filter is exactly Slice 81's
intersection(`page_selections` universe, material selection), a material selection can never keep a visual record on a page
`page_selections` already excluded, and can never expand visuals to a page outside that universe — strict subtraction at
the visual layer too.

**Why missing/unknown visual source pages degrade by dropping conservatively.** A material selection is an explicit "use
only/not these pages" instruction with coverage and privacy intent. If a manifest record's `source_page` cannot be
verified (≤ 0) while a filter is active, *keeping* it could surface a visual from a page the user excluded, whereas
dropping it only risks omitting one unverifiable candidate. The safer choice for honoring exclusion is therefore to drop
(with a closed `material_selection_visual_page_unknown` token). On the live path page candidates always carry a real
physical page number, so this rule only bites hostile/synthetic input; with no active filter the record is kept unchanged.

**Why table reconstruction / a table manifest is deferred.** There is no separate table manifest or table-extraction
artifact today — the only visual artifact is `visual_assets_manifest.json`. Inventing one here would be a large,
behavior-defining surface (extraction, reconstruction, rendering) unrelated to page filtering. So Slice 82 applies the
page filter to the existing visual manifest only and reserves a closed `material_selection_table_manifest_not_present`
token; when a real table manifest lands (Slice 85), the same per-source page filter applies to it. Likewise, gated local
figure extraction already receives the material-filtered `pages` upstream, so the explicit manifest filter targets the
live page-signal path without touching the gated extractor's identity.

**Why this remains Full Material Coverage foundation work, not a visual-pilot heuristic loop.** Slice 82 still only
honors explicit user page/slide intent (persist → apply to extraction → apply to the visual manifest). It changes none of
the visual pilot's selection, ranking, classification, cap, default, two-key-gate, or caption behavior — the pilot simply
sees fewer (or no) candidates when a selection excludes pages, and the cap is unchanged. The new
`summary.pages_filtered_by_material_selection` is a count and the warnings are closed tokens, so the manifest's no-leak
boundary (no page lists, filenames, paths, captions, image refs, text, base64, data URIs, tokens, or URLs) is preserved.
No render/export/prompt/provider change, no Chandra/Mistral/Gemini/model/provider/cloud call, no direct `clean.md` write.
Chandra remains blocked by its own live-validation gate. **Slice 82 committed `fd3fb97`, fast-forward merged to
`chrome-renderer-v1`, and pushed.**


## Slice 83 — full non-table visual inclusion planner starts as a pure core that plans ALL eligible non-table visuals (2026-06-14)

**Decision.** Slice 83 adds `pipeline/visual_inclusion_planner.py`, a pure, stdlib-only, **unwired** core that consumes a
sanitized `visual_assets_manifest.json`-shaped dict (already material-page-filtered by Slice 82) and emits a sanitized
`visual_inclusion_plan` dict naming which **non-table** visuals from included pages to plan for future guide inclusion. It
is not imported by generation, Markdown insertion, renderers, exporters, prompts, the API, or the frontend, and it
persists no artifact.

**Why a pure core (again).** Same staged pattern proven through Slices 76–82: land the decision logic as a pure,
exhaustively-testable, no-leak function *before* wiring it to anything that renders or persists. The planner can therefore
be validated with synthetic dictionaries (178 host checks) with zero risk to the load-bearing PDF/render pipeline,
extraction/OCR routing, the visual pilot, or any export — and a later slice can wire it deliberately. Persistence is
Slice 84; table policy is Slice 85; E2E coverage is Slice 86.

**Why it plans ALL eligible non-table visuals by default (no top-1/top-2 cap).** The product goal of Full Material
Coverage is to *include all useful non-table figures/diagrams/graphs/charts/instructional visuals from included pages,
after deterministic safety filtering* — explicitly the opposite of the parked visual-pilot's "best 1–2 crops" heuristic.
Re-introducing a small default cap here would re-create exactly the behavior this roadmap is moving away from. So the
default plans every eligible record. `max_items` exists only as a **defensive ceiling** for pathological documents
(default `None`); when it truncates, the plan is `partial` and records `max_items_applied`. It is deliberately *not* the
old cap and is never set by the product path in this slice.

**Why "all useful," not "every crop."** "All figures" is bounded by deterministic safety filtering, never an unfiltered
dump: table-like records are skipped (see below); decorative/logo/header/footer/background/watermark records are skipped;
low-information pages (`signals.classification == "blank_or_low_text"`) and tiny crops (`crop_*_px < 24`) are skipped;
records marked unsafe are skipped; and a record whose `source_page` cannot be verified as a positive int is dropped
conservatively so a material-excluded or unverifiable page can never surface a visual. A record with no recognized type
token at all is skipped as `visual_type_unknown` — the safer choice, and harmless in practice because today's real
manifests only emit `page_visual_signal`/`extracted_figure`.

**Why table-like records are skipped, not screenshot-inserted.** Tables are a separate problem with their own quality
bar: a screenshot of a table is rarely an acceptable study-guide artifact, and reconstructing/simplifying tables into
real Markdown/structured form is the job of the later **Slice 85** table reconstruction/simplification policy. Mixing
table handling into the figure planner would either ship low-quality table screenshots or prematurely couple two
independent policies. The planner therefore skips any record typed `table`/`table_like`/`grid_table`/`dense_table`/
`table_region`/`tabular`/`table_image` (table wins over any co-present figure token) and counts them in
`table_like_skipped_count` for later observability. No table artifact is invented here.

**Why artifact persistence / rendering / UI are deferred.** Persisting `visual_inclusion_plan.json` is a distinct,
exact-name-artifact concern (Slice 84) with its own no-leak review; rendering/insertion changes touch the load-bearing
pipeline and must not ride along with a planner experiment; and **no UI** should be built until the backend chain proves
page selections apply consistently across content extraction, visual candidates, table candidates/policy, and coverage
reporting (Slice 86). Keeping Slice 83 unwired means current rendering/export behavior is byte-unchanged.

**Why this is Full Material Coverage work, not a visual-pilot heuristic loop.** The planner makes deterministic
include/skip decisions from explicit manifest signals and user-driven page selections; it has no ranking, scoring,
provider call, two-key gate, or "pick the best N" heuristic. It changes none of the visual pilot's
selection/ranking/classification/cap/default/two-key-gate/caption behavior. The plan emits only closed tokens, ints,
`None`, and fixed strings — no filename/path, document/OCR/caption/table text, image ref, asset ref/asset id, image
bytes, base64/data URI, provider payload, token, URL, argv, socket path, model path, or raw exception (input fields are
read for decisions only and never echoed; the manifest's internal `asset_id` is used for dedupe only and never emitted),
verified by hostile-canary tests. No Chandra/Mistral/Gemini/model/provider/cloud call; no direct `clean.md` write. Chandra
remains blocked by its own live-validation gate. **Slice 83 is COMMITTED `72e1f87`, fast-forward merged, and pushed to
`chrome-renderer-v1`.**

---

## Slice 84 — Persist the visual inclusion plan as a safe exact-name artifact

**Decision.** Persist the Slice 83 planner output as the deterministic, sanitized exact-name job artifact
`visual_inclusion_plan.json` (new `pipeline/visual_inclusion_plan_artifact.write_visual_inclusion_plan`, new
`Job.visual_inclusion_plan_json`, an exact-name `_artifact_path` mapping, and a `_attach_sources` wiring call after the
visual-assets manifest is written and read back). It is exact-name download only — deliberately kept out of `ARTIFACTS`,
generic `_artifact_urls`/`_artifact_details` rows, `EXPORT_ARTIFACTS`, `EXPORT_ARTIFACT_ALIASES`, the export ride-along
tuple, and the frontend. No Markdown insertion, render, export, prompt, provider, or UI wiring.

**Why planner persistence comes before rendering/insertion.** Persisting the plan is the small, reviewable next step that
makes the Slice 83 decisions observable (downloadable, diffable, testable) without touching the load-bearing
Markdown-insertion / Chromium-render / DOCX / export pipeline. Insertion is a separate, higher-risk concern that must not
ride along with a freshly-wired artifact: landing persistence first yields a stable, sanitized contract that a later
insertion slice can consume, and current rendering/export output stays byte-unchanged.

**Why the artifact is exact-name and sanitized (mirrors `source_coverage_report.json`).** The repo already has a proven
convention for advisory/foundation JSON siblings: reachable only by a fixed filename through `_artifact_path`, never added
to the generic artifact list / UI rows / export selectors, and never gating job status. Following it verbatim means no new
path-traversal surface, no new generic UI row, and no export-bundle change — and it inherits the same no-leak posture. The
artifact re-emits only the Slice 83 plan (closed tokens, ints, `None`, fixed strings); hostile manifest fields
(filename/title/path/text/OCR/caption/table-text/image-ref/asset-ref/url/argv/socket/model-path/base64/key) are read for
decisions and never echoed.

**Why all useful non-table visuals are planned by default instead of top-2.** The artifact inherits the Slice 83 contract
verbatim — Full Material Coverage means *include all useful non-table figures after deterministic safety filtering*, the
deliberate opposite of the parked visual-pilot "best 1–2 crops" cap. Re-introducing a default cap at the persistence layer
would re-create exactly the behavior this roadmap moves away from, so the writer plans every eligible record.

**Why table-like visuals are skipped and deferred to table policy.** A persisted plan of figure screenshots must not
silently absorb tables: a table screenshot is rarely an acceptable study-guide artifact, and reconstructing/simplifying
tables is the job of the later **Slice 85** table reconstruction/simplification policy. The writer inherits the planner's
table skip (counted in `table_like_skipped_count`) rather than inventing a table artifact here.

**Why candidate mapping must use safe generated IDs if/when needed — and why it is deferred now.** A future insertion
slice will need to map plan items back to manifest visual candidates. Doing that safely requires a **generated internal
id** (e.g. `visual_candidate_0001`) keyed off manifest order — never a filename, path, raw `image_ref`/`asset_ref`,
original caption, OCR text, or source text, all of which would breach the no-leak boundary. Slice 84 takes the smallest
safe option: keep the Slice 83 plan schema **as-is** (items already carry `source_index` + `source_page` for coarse
mapping) and defer adding any `candidate_id` to the slice that actually consumes it, so no new field ships before it is
needed or test-covered.

**Why UI / export / rendering are deferred.** Same discipline as Slice 83: no UI should be built until the backend chain
proves page selections apply consistently across content extraction, visual candidates, table candidates/policy, and
coverage reporting (Slice 86); and export/render changes touch load-bearing code and must not piggyback on an artifact
slice. The writer is **degrade-never-fail** (any build/write error prints a safe message — exception type only, no raw
string — and generation continues), so the artifact can never gate or fail a job. It changes none of the visual pilot's
selection/ranking/classification/cap/default/two-key-gate/caption behavior, no extraction/OCR routing, and no render/
export/prompt/provider behavior. No Chandra/Mistral/Gemini/model/provider/cloud call; no direct `clean.md` write. Chandra
remains blocked by its own live-validation gate. (Slice 84 was subsequently committed `7cc9d6f`, merged ff, and pushed.)

---

## Slice 85 — Table reconstruction/simplification policy starts as a pure, unwired core
The non-table visual inclusion planner (Slice 83) and its persisted plan (Slice 84) deliberately **skip table-like
material**. Slice 85 fills that gap with `pipeline/table_reconstruction_policy.py` — a pure, deterministic, stdlib-only
decision layer (`classify_table_candidate`, `build_table_reconstruction_policy`) that decides what should *later* happen
to a table-like candidate, while reconstructing nothing yet.

**Why the table policy starts as a pure core (no wiring).** Reconstruction/simplification of tables is the highest-risk
visual behavior (it must preserve exam-load-bearing keywords, headers, units, labels, and numbers without leaking source
text), so the decision layer is settled and test-locked *before* any consumer touches it — the same staged discipline as
Slices 83→84 (planner → artifact → consumer). A pure core can be exhaustively unit-tested with synthetic candidates,
stays trivially safe (no PDF/image/OCR/provider access), and cannot regress generation because nothing calls it. Wiring,
an artifact writer, prompt integration, and rendering are each a later, separately-scoped slice.

**Why screenshot insertion is not the default table behavior.** A table pasted as a screenshot is rarely an acceptable
study-guide artifact: it is unsearchable, unstyled, often unreadable at PDF scale, and carries the source verbatim. The
product rule is that tables should be **reconstructed into study-friendly content** instead. The policy therefore never
emits a screenshot action and pins `screenshot_insert_count` to `0`; non-table records are explicitly *not* coerced into
table screenshots (they are warned `not_table_like` and produce no item, left to the non-table planner).

**Why `reconstruct_with_original` and `simplify_only` are future modes, not implemented now.** The two target modes —
keep the original table text *plus* a simpler/clearer version, or emit the simpler version only — both require an LLM
pass over real table content, which is exactly what this slice must not do. So Slice 85 only *decides which mode applies*
(from deterministic structural/text-layer/confidence/safety signals) and records what a later pass must `preserve`
(`headers, column_labels, row_labels, exam_terms, numeric_values, units`). The reconstruction itself is deferred until a
slice that can safely run the model and persist/insert the result.

**Why no table manifest is invented in this slice.** There is no table-candidate manifest in the pipeline today, and
inventing/persisting one here would (a) couple the policy to a not-yet-designed extraction schema and (b) risk persisting
real table text/refs before the no-leak boundary for tables is settled. The policy instead consumes *synthetic /
sanitized table-candidate-shaped dicts* and emits only closed tokens/ints/`None`, so the decision contract is fixed
independently of however a real table manifest is later shaped. The future extraction/manifest slice can adapt to this
stable policy rather than the reverse.

**Why LLM prompt integration / rendering / UI are deferred.** Same discipline as Slices 83–84: no prompt, render, export,
or UI change rides along on a policy-core slice. The module imports no API/FastAPI/fitz/OCR/renderer/provider/LMM/
job-manager/visual-insertion/visual-pilot/visual-inclusion/manifest module (import-hygiene tested), changes no API route,
no job-execution wiring, no extraction/OCR routing, and no render/export/prompt/provider or visual-pilot
ranking/classification/cap/default/two-key-gate/caption behavior. No Chandra/Mistral/Gemini/model/provider/cloud call; no
direct `clean.md` write. Chandra remains blocked by its own live-validation gate. (Slice 85 was subsequently committed
`8a1b780`, merged ff, and pushed.)

---

## Slice 86 — Validate the Full Material Coverage backend chain before building UI
Slices 76–85 added the backend foundation for Full Material Coverage as independent, individually-tested pure pieces
(source coverage report core/artifact; global + per-attachment material page-selection persistence; selection applied to
text extraction and to visual-manifest planning; the full non-table visual inclusion planner + artifact; the table
reconstruction/simplification policy core). Slice 86 adds a single deterministic, synthetic **E2E validation harness**
(`test_scripts/test_material_coverage_e2e_validation.py`) that composes those helpers and asserts they behave as one
chain: `material page selection → text extraction page filtering → visual manifest page filtering → visual inclusion plan
→ table reconstruction policy → source/visual/material coverage summary`.

**Why validation comes before UI.** The Builder UI (page pickers, material toggles, coverage readout) is the most
expensive, least-reversible layer to change, and it would *encode assumptions* about how the backend chain composes —
which page set wins, what is filtered, what is planned, what is deferred to the table policy. Locking those assumptions in
a deterministic harness first means the UI can be built against a proven contract instead of a guessed one, and any future
backend change that breaks composition fails a cheap test rather than surfacing as a UI bug over a real private document.

**Why synthetic deterministic tests instead of real private PDFs.** The chain's correctness is structural (which pages
survive, which records are planned vs. deferred, which counts are produced), not perceptual, so it can be proven entirely
with synthetic dictionaries. Real PDFs would add no signal while introducing private document text, OCR text, captions,
table text, filenames, and paths into the test corpus — exactly the categories the no-leak boundary forbids. The harness
instead seeds *canaries* (synthetic forbidden values) into every input and asserts they are stripped from every stage
output, so it doubles as a leak regression test without ever handling real material.

**Why table reconstruction and full visual insertion remain deferred.** This slice only proves *routing and planning*:
that table-like candidates are counted by the table policy (and never screenshot-inserted, `screenshot_insert_count`
stays `0`) and that all eligible useful non-table visuals are planned (not a top-1/2 subset). Actually reconstructing a
table or inserting a planned visual both require an LLM/render pass over real content and a settled persistence/insertion
boundary — each is a separate, later, explicitly-scoped slice. Validating the decisions first de-risks those slices.

**Why this is Full Material Coverage foundation work.** "Full Material Coverage" means the guide reflects exactly the
material the operator selected — every selected page's text and useful visuals, with tables reconstructed rather than
screenshotted, and nothing from excluded pages. Slice 86 is the first slice that demonstrates the whole selection→content
pipeline end to end (selection bounded by `page_selections`, per-attachment override beating the global fallback, excluded
pages absent from both text and visuals, useful visuals planned, tables routed to policy, coverage summarized), which is
the contract the remaining coverage UI and reconstruction/insertion slices build on.

**Why no new artifact is persisted in Slice 86.** A validation harness proves a property; it is not a pipeline stage, so
persisting a `material_coverage_validation.json` job artifact would (a) add a production surface that has to be wired,
secured, and kept in sync, and (b) imply a runtime contract that does not yet exist. The harness emits its summary shape
**in memory only** for assertion. The harness is also kept test-only (no `pipeline/material_coverage_validation.py`
module was needed) since the composition is already expressible directly over the merged helpers. No API route, no
job-execution wiring, no extraction/OCR routing, no render/export/prompt/provider or visual-pilot
ranking/classification/cap/default/two-key-gate/caption change; no Chandra/Mistral/Gemini/model/provider/cloud call; no
direct `clean.md` write; no table manifest invented. Chandra remains blocked by its own live-validation gate. **Slice 86
is NOT committed.**

## Builder UI for per-attachment page/slide exclusions comes after backend E2E validation (Slice 87)
The Builder's first material-coverage control (per-attachment "exclude pages/slides") was deliberately built **after**
Slices 78–86 had persisted, applied, and end-to-end **validated** the `material_page_selections` backend chain (Slice 86's
synthetic harness proved selection → extraction filtering → visual-manifest filtering → inclusion plan → table policy →
coverage as one chain). **Why:** wiring a UI to a field whose semantics were still settling would risk shipping a control
whose effect we could not yet describe or guarantee. With the backend contract locked and tested, the UI is a thin,
low-risk producer of an already-understood payload — the backend stays the single normalizer/source of truth and the UI
adds no new behavior of its own.

**Why the first UI is exclude-only, not full include/exclude.** The backend page-selection model supports `all` /
`include` / `exclude`, but the first UX exposes **exclusions only**. **Why:** "skip these few pages/slides" is the common,
low-cognitive-load operator action and maps to a single text box; an include-mode UI implies a per-attachment page picker
(or a "keep only these" mental model that interacts with the existing filename-keyed `page_selections` extraction ranges)
and is easy to get subtly wrong. Exclusions are additive and safe — the backend still normalizes, and include-mode can be
layered on later if a real need appears. Keeping the first surface minimal avoids a confusing two-axis control on day one.

**Why attachment keys are `attachment_<index>`, never filenames/paths.** The submitted/persisted envelope keys are derived
purely from **upload order** (`attachment_0`, `attachment_1`, …), matching the order the multipart request appends the
files and the order the backend already keys on. **Why:** filenames and paths are user-controlled, can collide, can carry
private document titles, and are exactly the kind of value the no-leak invariants forbid in artifacts/logs/payloads. A
positional key is stable, collision-free, and leak-safe. The local filename is still shown to the operator in the picker
for orientation, but it never becomes a persisted key — the helper accepts ordered raw inputs and assigns positional keys,
so a filename cannot reach the payload even by accident (covered by a canary test).

**Why existing `page_selections` stays a separate field.** The older `page_selections` field (filename-keyed, 1-based
inclusive extraction ranges from the large-PDF preflight card) is load-bearing and untouched. `material_page_selections`
is a distinct concept (per-attachment, positional keys, include/exclude model feeding the *full material coverage* chain:
content + visual + table planning, not just extraction page ranges). **Why keep them separate:** merging them would
overload one field with two different key schemes and two different downstream meanings, and would put the tuned extraction
path at risk. They evolve independently; the Builder owns separate state for each.

**Why JobDetails / source-coverage display is deferred.** Slice 87 only adds the *input* control. Showing the resulting
source/visual/material **coverage summary** back to the operator (in JobDetails) is a separate, later slice. **Why:** the
coverage report core/artifact exists (Slices 76–77) but surfacing it well is a read-side UX problem with its own no-leak
constraints (it must show counts/anchors without leaking source titles, captions, or document/OCR text), and it should be
designed once there is real selected-vs-covered data to render. Splitting input UI from coverage display keeps each slice
small and independently verifiable. No table reconstruction, no all-visual insertion/rendering, and no render/export/
prompt/provider/visual-pilot change ride along. Chandra remains blocked by its own live-validation gate. **Slice 87 is NOT
committed.**

## Slice 88 — JobDetails material coverage display (2026-06-14)
Slice 87 was committed `844e394`, fast-forward merged, and pushed to trunk. Slice 88 adds a **read-only** "Material
Coverage" tab in Job Details (`MaterialCoveragePanel` + pure helper `materialCoverageDisplay.js` + verify script), wired
into `RecentJobsPanel`. It consumes only already-safe job-response fields (`material_page_selection(s)`) and the
**exact-name** artifacts `source_coverage_report.json` / `visual_inclusion_plan.json`, displaying counts and closed-vocab
status. No backend code, no client.js helper, and no new route were needed.

**Why coverage display comes after backend E2E validation and Builder exclusion UI.** The order is deliberate:
Slices 76–86 built and *proved* the backend coverage chain end-to-end, then Slice 87 gave operators a way to *set*
per-attachment exclusions, and only now does Slice 88 surface the *result* back. **Why:** building the read-side before the
data path was validated would have meant rendering a model that might still change shape; doing it before the input UI
would have shown coverage with nothing for the operator to influence. Surfacing it last means the display reflects a stable
artifact contract and a real selected-vs-covered story, and each slice stays small and independently verifiable.

**Why JobDetails shows safe counts/status instead of raw source details.** The panel emits only page/visual **counts**,
closed-vocabulary status tokens, and active/inactive booleans — never filenames, paths, source titles, page text,
captions, OCR text, table text, image/asset refs, or any artifact warning payload that could carry free-form text. **Why:**
the no-leak invariants forbid private document content in any served frontend state, and the coverage artifacts are derived
from source documents. The helper re-guards everything it reads (status through an allowlist, counts clamped to
non-negative integers, attachment keys restricted to the positional `attachment_<index>` shape) so a hostile or malformed
artifact cannot smuggle text into the display model — verified by canary tests.

**Why missing artifacts are neutral, not errors.** `source_coverage_report.json` / `visual_inclusion_plan.json` only exist
for jobs that produced them (e.g. PDF jobs with extractable signals); older or text-only jobs legitimately have neither. A
404 (or a null/unfetched report) renders a calm "Coverage artifact not available for this job yet." **Why:** treating an
expected absence as an error would make ordinary jobs look broken and train operators to ignore the panel. Each artifact
fetch is independent so one missing report never blocks the other.

**Why table reconstruction and all-visual rendering remain deferred.** Slice 85 added only the table-policy *core*; no
table artifact is emitted and reconstruction is not enabled, so the panel shows a static "Policy core available; table
reconstruction not yet enabled." note rather than per-job table output. Likewise no visuals are inserted/rendered. **Why:**
both are large, separately-designed slices with their own correctness and no-leak constraints; a display slice must not
quietly start producing content. Slice 88 changes nothing about extraction, visual filtering/planning, table policy,
render/export/prompt/provider behavior, or visual-pilot behavior. Chandra remains blocked by its own live-validation gate.
**Slice 88 is NOT committed.**

## Slice 89 — Full Material Coverage controls and warnings: honest UX polish before full insertion (2026-06-14)
Slices 87–88 let users *set* per-attachment page/slide exclusions and *see* coverage counts after a job. Slice 89 adds the
user-facing **controls + warnings** layer: a Builder-side `MaterialCoverageControls` block (active/inactive state, "N
attachments have exclusions. M pages/slides will be skipped.", a generic invalid-token hint, scope and limitation copy, and
a "Clear exclusions" button) plus a JobDetails "What this means" notes section. It is a frontend UX/control slice only —
new pure helper `materialCoverageWarnings.js` (`buildBuilderMaterialCoverageSummary`, `buildJobMaterialCoverageNotes`),
wiring in `BuilderWorkspace.jsx` / `MaterialCoveragePanel.jsx`, and CSS. **Slice 89 is NOT committed.**

**Why warnings/control polish comes before full insertion.** The backend can already plan coverage (Slices 76–86) and the
UI can already set/see it (Slices 87–88), but the user has no single, honest summary of what their exclusions do or what
the system will and will not do with them. Shipping that understanding *before* Slice 90's full non-table figure insertion
means the riskier generation-quality work lands against users who already have correct expectations, instead of having to
retrofit explanations after behavior changes.

**Why the UI must not overpromise full figure insertion / table reconstruction yet.** Coverage *planning* exists, but full
automatic figure insertion (Slice 90+) and table reconstruction (Slice 85 shipped the policy *core* only, unwired) are not
enabled. The copy deliberately says visuals were *planned* ("full automatic insertion is a later step") and that "table
reconstruction is not enabled yet". **Why:** claiming inserted/reconstructed content that the generated guide does not
actually contain would be a correctness lie that erodes trust and masks the real state of the pipeline.

**Why no new backend field is added.** All the signals the controls/warnings need already exist: the Builder summary is
computed locally from the same positional exclusion inputs that build the Slice 87 envelope, and the JobDetails notes are
derived from the Slice 88 display model (itself built from already-safe job fields + exact-name artifacts). Adding a
backend field would mean touching `LLMJobRequest` and both request-construction paths for a purely presentational summary —
unnecessary risk. The Slice 87 submit payload shape is therefore unchanged, and `page_selections` is preserved/separate.

**Why raw artifact warnings / source details are converted into safe notes/counts.** Coverage artifacts are derived from
private source documents, and the no-leak invariants forbid filenames, paths, page numbers, captions, OCR/source/table
text, image/asset refs, data URIs, base64, provider payloads, tokens, full URLs, and raw exception strings in any served
frontend state. The Builder summary thinks only in positional upload order and emits counts plus a boolean "some entries
were ignored" flag (never the raw token); the JobDetails notes are a fixed, closed-vocabulary set of static strings (never
artifact warning text passed through verbatim). Canary tests verify no hostile input rides out of either builder.

**Why Slice 90 should move into actual guide-generation quality.** With coverage controls/warnings honest and complete, the
next meaningful improvement is the real payoff: full non-table figure insertion v2, which finally turns planned visuals into
inserted guide content (with its own correctness + no-leak design). Slice 89 changes nothing about extraction, material
application, visual filtering/planning, table policy, render/export/prompt/provider behavior, or visual-pilot behavior.
Chandra remains blocked by its own live-validation gate.

## Slice 90 — Full non-table figure insertion v2: plan-driven, safe-mapped, all useful figures (2026-06-14)
Slices 82–89 built and exposed the Full Material Coverage foundation (planner core, plan artifact, table-policy core,
coverage E2E, Builder exclusion UI, JobDetails display, controls/warnings). Slice 90 is the first slice that turns *planned*
non-table visuals into *inserted* guide content. When visuals are enabled it inserts **all useful planned non-table
figures from included pages** (subject to the deterministic Slice 83 safety filtering), not the legacy top-1/top-2 cap. It
adds `candidate_id` to the inclusion plan, a plan-driven full-insertion path in `visual_markdown_insertion.py`
(`is_full_visual_insertion_enabled` / `select_full_visual_markdown_candidates` / `_apply_full_visual_insertion`), and
`test_full_visual_insertion_v2.py`. **Slice 90 is NOT committed.**

**Why full figure insertion only starts now, after the coverage/control foundation.** Inserting real figures changes the
generated guide — the highest-risk, highest-value visual work. Doing it only after the deterministic planner (Slice 83),
the persisted plan artifact (Slice 84), the table-exclusion policy core (Slice 85), the coverage E2E harness (Slice 86),
and the Builder/JobDetails coverage UI with honest "not enabled yet" warnings (Slices 87–89) means insertion lands on a
filtered, audited, page-selected candidate set against users who already have correct expectations — instead of retrofitting
filtering, safety, and explanations after behavior already changed.

**Why mapping must use a safe generated id / deterministic safe index.** Slice 84 deliberately deferred candidate IDs so the
public plan could never carry a filename, path, slug, or asset ref. Slice 90 needs to map a planned item back to a manifest
record to actually insert it. Rather than expose the manifest `asset_id`/`image_ref` (a slug/path), the planner emits a
**safe generated** `candidate_id` = `visual_candidate_NNNN` derived purely from the record's positional index, and insertion
re-derives the same `{candidate_id: record}` map by the same formula. This keeps the public artifact sanitized (only one new
closed-shape field), is deterministic and order-stable (the id is tied to manifest position, not plan order, so it survives
the deterministic re-sort), and is unambiguous (positions are unique). Insertion additionally forces the generic page-derived
caption (`None` → "…source page N" / "*Source visual, page N.*"), so even if a future manifest populates `caption`/OCR the
raw text can never ride into the guide.

**Why the old cap-2 visual pilot is not the final behavior.** The Slice 54–74 pilot was a deliberately tiny, heuristic
top-1/top-2 selector built to prove the insertion plumbing safely; its cap exists to avoid dumping low-value crops before a
real candidate-quality story existed. The Slice 83 planner *is* that story: it already filters to useful non-table visuals
deterministically. So full insertion should consume the planner, not a second heuristic loop or a hard cap. The legacy pilot
is kept as a byte-identical fallback behind an off-by-default mode switch (`GUIDEFORGE_ENABLE_FULL_VISUAL_INSERTION`) layered
on the unchanged two-key visual gate — the mode switch can never enable insertion on its own, and with it off every existing
deployment is unchanged.

**Why table-like visuals are still excluded.** A table screenshot is usually reconstructable from extracted text into clean
generated Markdown/HTML — embedding it as an image is lower quality and harder to read, and table reconstruction is its own
separately-designed policy (Slice 85 shipped the core only, still unwired). The planner skips table-like records and the
insertion path never inserts them as screenshots; a test pins that a table-typed record is planned-out and absent from the
guide, with no reconstruction field introduced.

**Why export/render stress validation is deferred to Slice 91.** Slice 90 proves insertion correctness with focused
synthetic tests and the existing smoke (default output unchanged). It does **not** broadly exercise PDF/DOCX/HTML rendering
or multi-job ZIP export with many figures — and the export ride-along helper is still capped at 2 images, so a bundle of a
guide with N>2 figures would currently under-include assets. Rather than widen export/render code casually (load-bearing,
tuned), that whole surface — many-figure render fidelity, DOCX image embedding, and the export asset cap — is reserved for
Slice 91. Chandra remains blocked by its own live-validation gate.

## Slice 91 — full figure insertion export/render validation (and removing the export cap-2)

**Why render/export validation follows full insertion.** Slice 90 made full non-table figure insertion *possible* (a guide
can now reference many `assets/<slug>.png` figures) but deliberately did not touch the render/export surface, which is
load-bearing and tuned. Validating that surface as its own slice keeps the behavior change (insertion) and the fidelity
change (export/render carrying many figures) separately reviewable, and means the insertion slice could not silently
regress PDF/DOCX/HTML/ZIP output. The validation found exactly one load-bearing gap — the export bundle ride-along cap —
and proved the renderers were already safe, rather than rewriting them speculatively.

**Why all safe referenced assets must ride along, not the old top-2 pilot cap.** The export ride-along exists so exported
Markdown/HTML/DOCX stays portable — every image the guide *references* must travel with it. The legacy cap of 2
(`_HARD_MAX_IMAGES`) matched the legacy pilot, which only ever inserted ≤2 figures, so the cap was invisible. Once full
insertion can place many figures, a cap-2 ride-along would ship a guide whose later figures resolve to nothing. The fix
drives discovery purely from what `clean.md` actually references (`find_all_exportable_visual_assets`, bounded only by the
defensive `_FULL_INSERTION_HARD_CEILING`), which is correct for **both** paths: a legacy guide referencing ≤2 still yields
≤2, a full-insertion guide yields all of them. The legacy helper now just delegates with `limit=_HARD_MAX_IMAGES`, so its
behavior — and every test pinned to it — is byte-identical. The HTML/PDF/DOCX renderers needed no change: they already
render/embed every referenced asset from the job dir and leave a safe `[image missing: assets/<slug>.png]` marker for an
absent one.

**Why only safe relative `assets/<slug>.png` refs are allowed.** The same no-leak invariant as the insertion path: an
export must never copy or echo an absolute host path, a `..` traversal, a URL, a `data:`/base64 blob, a non-PNG, or a
nested path. Ride-along keeps the existing fixed-shape ref validation plus realpath containment inside the job dir (symlink
escapes rejected), and the bundle index records only the safe relative ref (never image bytes or a filesystem path). This
makes the "carry many figures" change incapable of widening the leak surface.

**Why table reconstruction remains deferred to the next phase.** Slice 91 is strictly figure render/export fidelity. Table
reconstruction is a separate, higher-risk capability (it rebuilds source table structure rather than embedding a safe
cropped figure ref) and stays governed by the Slice 85 table-reconstruction *policy* — extracted tables are still treated
as non-reconstructed visuals. Bundling it into a render/export validation slice would conflate two unrelated risk profiles.
Chandra remains blocked by its own live-validation gate.

## Slice 92 — table candidate manifest + reconstruction-policy artifacts (the bridge before prompt integration)

**Why table-candidate artifacts must exist before any reconstruction prompt integration.** Slice 85 built a pure table
*reconstruction policy* decision core, but it could only ever be exercised against synthetic, hand-written candidate dicts
— there has never been a real table manifest in the pipeline. Wiring a reconstruction prompt straight onto the raw visual
signals would mean the prompt layer, the candidate-detection rules, and the policy decision all land in one slice, each
with a different risk profile (prompt/provider exposure vs. detection correctness vs. leak surface). Slice 92 instead lands
only the deterministic, side-effect-free *bridge*: detect table-like records from the already-sanitized
`visual_assets_manifest.json`, persist them as `table_candidates_manifest.json`, and run the unchanged Slice 85 policy over
them into `table_reconstruction_policy.json`. Slice 93/94 can then integrate/validate a reconstruction prompt against a
stable, reviewed, sanitized input — never against raw extraction.

**Why candidates are sanitized counts/tokens only (never source content).** A table candidate exists to drive a *decision*,
not to carry the table. Every emitted field is a closed token (`table_kind`, `confidence`), a non-negative int
(`rows`/`columns`/cell counts), a bool (`has_text_layer`), a verified positive-int `source_page`, or a safe generated
`candidate_id` derived purely from emission order. No field of the source manifest record is ever echoed — no filename,
path, source title, caption, document/OCR/table text, image/asset ref, asset id, image bytes, base64/data URI, provider
payload, token, URL, argv, socket, model path, or raw exception string can survive into either artifact. This keeps the
bridge incapable of widening the leak surface even though it now reads "real" signals, and the `table_policy_candidates`
flattener that hands candidates to the Slice 85 policy carries only those same closed values.

**Why exact-name artifacts (not generic `ARTIFACTS` / UI rows / export selectors).** These are foundation/measurement
artifacts for a future capability, not user-facing deliverables. Following the established `visual_inclusion_plan.json` /
`source_coverage_report.json` convention, they are reachable only by their exact fixed filename through the existing
per-file route (`_artifact_path`), which introduces no path traversal and adds no row to `_artifact_urls` /
`_artifact_details` / generic UI lists and no entry to export bundles. That keeps the surface minimal and reversible: a
later slice can choose to surface them, but nothing depends on them yet.

**Why table reconstruction remains deferred (and tables are never inserted as screenshots).** Slice 92 deliberately stops
at *deciding* what should later happen to each table. It reconstructs nothing, calls no LLM/provider/model, changes no
prompt, and inserts nothing into Markdown/PDF/DOCX. Critically, a table is treated as a decision record, never an image to
embed: the policy never emits a screenshot action and `screenshot_insert_count` is always `0`. Inserting a table as a
cropped screenshot would defeat the product goal (study-friendly, reconstructed/simplified table content that preserves
headers, exam terms, units, and numeric values) and would also reintroduce the very leak/portability risks the figure path
spent Slices 90–91 containing. Reconstruction stays a separate, higher-risk slice. Chandra remains blocked by its own
live-validation gate.

## Slice 93 — table reconstruction prompt-context integration v1 (safe guidance, not extraction)

**Why prompt context follows the candidate/policy artifacts.** Slice 92 landed the deterministic, side-effect-free bridge
(`visual_assets_manifest.json` → `table_candidates_manifest.json` → `table_reconstruction_policy.json`). Slice 93 reads
only those two already-reviewed, already-sanitized artifacts to build a prompt context — it never re-derives table signals
from raw extraction, never inspects a PDF/image, never OCRs, and never extracts table text. Layering prompt guidance on top
of the stable artifacts (rather than on raw signals) keeps the detection rules, the policy decision, and the prompt surface
in separate, independently reviewable slices, and means the prompt layer can only ever see closed tokens/ints — it is
structurally incapable of widening the leak surface.

**Why no-hallucination table guidance is required.** A table is high-value exam material but also high-risk: if the model
is told "there is a table on page N" without a guarantee that the table's contents are in the source text, it will tend to
invent plausible rows/columns/values. The appended block therefore states the rule explicitly and in closed language:
reconstruct or simplify a table **only** from content already present in the provided source text, preserve the closed
`preserve` tokens when available, and never invent rows/columns/labels/values. For `defer`/`skip_unreadable` decisions the
guidance instead asks for an honest "table-like material was detected on page N but its contents were not readable" note,
so the guide is truthful about what it could not recover instead of fabricating it.

**Why source text remains the only allowed table content source.** The pipeline already places the normal extracted source
text (and, where enabled, attachment text) into the prompt. That text is the only sanctioned carrier of real table content.
The prompt context carries decisions (action, page, preserve tokens) but **no** table content, captions, OCR text, or
filenames — so the model's only material to reconstruct from is the legitimately-extracted source already in the prompt.
This keeps the no-leak invariant intact: the guidance block is built purely from closed tokens, page ints, and fixed
instruction strings, and `skip_unsafe` items are excluded so an unsafe record is never even named.

**Why image-only table reconstruction is still deferred.** Slice 93 deliberately stops at telling the model how to handle
tables whose contents are in the text. Reconstructing a table that exists only as pixels (image-only / no text layer)
requires real visual understanding (OCR or a vision model), which is a separate, higher-risk capability gated behind its
own live validation (Chandra remains blocked by its own gate). Slice 93 explicitly instructs the model NOT to attempt this
and to emit an honest unreadable note instead.

**Why UI/display is deferred.** The guidance is an internal prompt augmentation, not a user-facing artifact. Surfacing it
in the UI (or persisting it as a downloadable artifact) would broaden scope and add a display/serialization surface for no
current product need; the context is built in-memory at generation time and appended to the prompt only. A later slice can
choose to surface it if a need appears.
