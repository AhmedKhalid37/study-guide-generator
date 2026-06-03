# VALIDATION_PROVIDER_SETTINGS_LARGE_PDF.md — Real-world validation pass

> Manual QA / validation slice run after the Provider Settings feature group
> (Slices 1–5) and the Large-PDF core (Slices 1–5) landed on
> `chrome-renderer-v1` @ `162b6c9`. **Validation only — no feature work, no
> refactor.** Two concrete findings surfaced (one medium, one low); both are
> **pre-existing** in already-merged code and are documented under
> [Findings / follow-up slices](#findings--follow-up-slices) rather than patched.

- **Branch:** `validation-provider-settings-large-pdf` (off `chrome-renderer-v1` @ `162b6c9`)
- **Date:** 2026-06-03
- **Files changed:** **none** (this report is the only addition; no application
  code, prompts, renderer, or config touched). `config/` is gitignored, so the
  working tree stays clean.
- **Overall:** Provider-settings redaction/precedence/custom-models, the
  large-PDF preflight → page-selection → extraction → OCR → render path, and
  cooperative cancel all **PASS**. Secret-leak scan **CLEAN**. Two non-blocking
  bugs found (Test Connection false-negative; `default_provider` not wired into
  runtime selection).

---

## A. Baseline repo health — PASS

| Check | Result |
| --- | --- |
| `git status` / `git log --oneline -12` | clean; HEAD `162b6c9` |
| `npm --prefix frontend run build` | OK (built in ~1s; SVG assets emitted) |
| `python -m compileall api pipeline` | OK (exit 0) |
| `docker compose config >/tmp/compose-check.txt` | exit 0 (output **not** pasted — expands `.env`) |
| `docker compose build` | OK (image built) |
| `docker compose up -d` | OK; container **healthy** on first health poll |
| `curl /api/health` | `{"ok":true}` |
| `curl /api/options` | HTTP 200, expected shape (see B2) |
| `curl /api/provider-settings` | HTTP 200, redacted (see B1) |
| `python test_scripts/smoke_release.py` | **28 passed, 0 failed, 0 skipped** (incl. live LLM, attachment, outline-ordering — no flake this run) |

---

## B. Provider Settings validation — PASS (with 2 findings)

### B1. `/api/provider-settings` redaction — PASS
Top-level keys `{default_provider, providers}`. Each provider exposes **only**
safe fields: `id`, `display_name`, `kind`, `configured`, `key_source`,
`key_hint` (last-4 only, or null), `base_url_host` (host only),
`base_url_configured`, `available_models`, `custom_models`, `default_model`,
sampling fields, `supports_thinking`, `discovery_error`, `last_test`.
- **No `api_key` / `key` / `secret` field** on any provider (verified
  structurally, not just by value).
- `key_source` correctly reports `env` for deepseek/qwen/local (keys come from
  `.env`); `key_hint` present for the cloud providers, `null` for `local`.

### B2. `/api/options` redaction + shape — PASS
Top keys: `generator_presets, input_modes, models, provider_details, providers,
providers_v2, styles, themes`. `provider_details` carries
`{available_models, base_url, base_url_configured, configured, default_model,
discovery_error, display_name, id, kind, supports_thinking}` — **no key field**.
3 providers, 3 generator presets, `models`/`providers` flattened as expected.

### B3. One provider end-to-end (qwen custom-model round-trip) — PASS
1. Viewed provider settings (B1). Active store: `default_provider=qwen`,
   `qwen.default_model=qwen3.7-plus`, `deepseek.default_model=deepseek-v4-pro`.
2. **Test connection** (`POST …/{provider}/test`) on qwen + deepseek → HTTP 200,
   redacted result body. ⚠️ both returned `ok:false` — see **Finding #1**.
3. **Refresh models** (`POST …/{provider}/fetch-models`):
   - deepseek → `ok:true`, 2 models, `source:provider`,
     `base_url_host:api.deepseek.com`, `error:null`, **no `api_key` field**.
   - qwen → `ok:true`, 145 models, redacted.
4. Picked a genuinely-new fetched id `kimi-k2.6` (not in qwen's registry).
5. **Before Save** — confirmed `kimi-k2.6` **absent** from `/api/options`
   (qwen `available_models`) and `custom_models` empty.
6. **Save** (`PATCH …/qwen {custom_models:["kimi-k2.6"]}`) → HTTP 200, returned
   `custom_models:["kimi-k2.6"]`, **no `api_key` in the PATCH response**.
7. **After Save** — `kimi-k2.6` **present** in `/api/options` qwen
   `available_models`, appended **after** the registry models (registry-first
   ordering preserved).
8. **Restored** — `PATCH …/qwen {custom_models:[]}`; `kimi-k2.6` gone from
   `/api/options` again. Store confirmed back to original defaults.

### B4. Fetch-models is read-only / non-switching — PASS
- Re-ran deepseek fetch; `deepseek.custom_models` **still `[]`** → fetch
  **does not auto-save**.
- After fetch + the B3 PATCH, `default_provider` still `qwen` and
  `qwen.default_model` still `qwen3.7-plus` → fetch **does not auto-switch**
  default provider or default model.
- No raw key written anywhere (covered by the Part E scan; `config/secrets.json`
  unchanged).

### B5. Provider/model precedence — PASS (with Finding #2)
- **Per-job wins:** live generation with explicit `provider=deepseek,
  model=deepseek-chat` (differing from store default `qwen`/`qwen3.7-plus`)
  completed `done`; manifest recorded `model=deepseek-chat`, `provider=deepseek`.
  ✓ request > store default.
- **Store default `default_model` beats `.env`:** `.env` has
  `QWEN_MODEL=qwen3.7-max`, but the store sets `qwen3.7-plus`.
  `_pick_generate_provider('qwen')` → `('qwen', 'qwen3.7-plus')` and
  `/api/options` shows `qwen3.7-plus`. ✓ store > env for the model the Builder
  then sends. (Note: `/api/jobs/llm` requires explicit `provider`+`model`
  fields; the Builder always supplies them from `/api/options`, which is where
  store>env is applied.)
- **Generator presets do not hard-pin provider/model:** verified by the existing
  C4 test suite + design §13; `model_hint` remains a soft, non-blocking advisory
  (served bundle still carries the "tuned for" advisory copy, never a gate).
- ⚠️ **`default_provider` is NOT honored at runtime** — see **Finding #2**.

---

## C. Large-PDF workflow validation — PASS

Sources: real `AWS Student Builder Group Leader Handbook.pdf` (53-page text PDF)
and `04 Neural Networks - Part 2 Backpropagation-1-118.pdf` (118-page,
image-heavy/scanned deck). OCR (tesseract) confirmed functional in-container.

**In-Docker PDF test suites:** `test_pdf_preflight.py` **24/24**,
`test_page_selections.py` **24/24**, `test_pdf_page_selection_extract.py`
**39/39**, `test_mixed_pdf_ocr.py` **PASS** (page-1 text + pages-2/3 OCR).

### C1. Normal text PDF — PASS
AWS handbook preflight → `page_count:53`, `scanned_flag:text`, `verdict:ok`,
`recommended_mode:full`, `allowed_actions:[continue]`, **no warnings** (silent,
low-noise). Generation with all pages works (smoke + the text path).

### C2. Scanned / image-heavy PDF — PASS
NN deck preflight → `page_count:118`, `13.34 MB`, `scanned_flag:image_heavy`,
`verdict:warn`, `recommended_mode:first_n`, `ocr_pages_estimate:112`,
`allowed_actions:[continue, process_first_n, choose_page_range, remove_file]`,
with the expected image-based / page-count / OCR-time warnings.
- **Process first N** = `[[1,N]]` plumbing → works (same path as the range
  cases below).
- **Manual page range** including a non-contiguous multi-range `1-3, 8-10`
  (`[[1,3],[8,10]]`) → job `done`; `source.txt` contains exactly
  `## Page 1,2,3,8,9,10`.
- **Invalid range** rejected at the backend: `[[10,3]]` and `[[-1,3]]` →
  **HTTP 400** "page ranges must use positive 1-based pages with start <= end"
  (does not apply). The frontend `parsePageRanges`/`formatPageRanges` UI
  behaviors (inline error, "Use all pages" clears, "Using pages …" confirmation)
  are present in the served bundle (all strings found; "coming later" absent) and
  were unit-covered by the Slice-5 parse/payload harness.

### C3. Extraction behavior — PASS
Live generation, NN deck, `page_selections={"…Backpropagation-1-118.pdf":[[8,10]]}`:
- `page_selections` **persisted in `job.json`** (and echoed by the job response).
- `input/source.txt` contains **only `## Page 8`, `## Page 9`, `## Page 10`** —
  original anchors **preserved** (not renumbered to `## Page 1`). ~688 chars / 3
  pages, not the full 118-page deck.
- Attachment `mode: pdf_ocr`, `status: extracted`, `extracted_chars: 568` → **OCR
  ran only on the selected scanned pages**.

### C4. Rendered output — PASS
- `final.pdf` (68 KB) + `final.html` + `clean.md` rendered from the OCR'd subset.
- With `slide_page_references` enabled, page citations use the standardized
  `(page 8)` form; **no banned forms** (`p.N`, `pp.`, en-dash) present.
- With `mcqs_with_answers` enabled, the answer key renders as readable prose
  ("Practice questions with answers" / "Answer key"), **not** wrapped in broken
  `$…$` math.
- Prompt-format guarantees re-confirmed: `test_page_reference_format.py`
  **21/21**, `test_long_formula_guidance.py` **10/10**.

---

## D. Cancel validation — PASS
Launched a full 118-page OCR generation; while it was in `stage:extracting`,
`POST /api/jobs/{id}/cancel` → `{cancelled:true, status:cancelling}` and the
`jobs/<id>/cancel.requested` marker was written.
- Job reached terminal **`status: cancelled`** (`error: null`) — distinct from
  `failed`.
- **Cooperative / checkpoint-based:** the in-flight OCR extraction **completed**
  (19,208-byte `input/source.txt`, 1539 lines for all 118 pages) and the cancel
  took effect at the **before-LLM checkpoint** — i.e. it stopped at the next safe
  boundary, not via an instant process kill.
- **Render skipped:** no `final.pdf` produced (LLM/render never ran).
- **Inputs/artifacts preserved:** `input/source.txt` + `input/attachments/`
  intact; nothing deleted. The cancel marker was **cleared** on cancel.

---

## E. Secret leak scan — CLEAN
Scanned against the **real** key values (collected from `.env` + the
container's `config/secrets.json`, never printed):

| Target | Result |
| --- | --- |
| `/api/options` | clean |
| `/api/provider-settings` | clean |
| fetch-models response | clean |
| served frontend JS (`index-*.js`, 440 KB) | clean |
| container logs (`docker compose logs`) | clean |
| all validation `job.json` files | clean |

No raw key substring in any target; **no `api_key`/`apiKey` field** in any JSON
response or manifest. The non-secret `config/provider_settings.json` holds no key
material; raw keys live only in `config/secrets.json` (`0600`, owned by the
container user). No real secret value appears in this report.

---

## Findings / follow-up slices

### Finding #1 — Test Connection reports a false failure for reasoning/thinking models (MEDIUM)
`POST /api/provider-settings/{provider}/test` returns `ok:false`
("LLM returned an empty response.", `category:"unknown"`) for **both** qwen and
deepseek — even though full generation on those same providers succeeds (smoke
28/28; live gens in B5/C all `done`).

- **Root cause:** `pipeline/provider_config.py:test_provider` calls
  `generate_chat_completion(..., max_tokens=1)`; `pipeline/llm_client.py:171-173`
  raises `RuntimeError("LLM returned an empty response.")` whenever
  `choices[0].message.content` is empty. Reasoning/thinking models
  (qwen with `enable_thinking=True`; `deepseek-v4-pro`) spend the single allotted
  token on reasoning and return empty visible content, so the probe sees a valid
  HTTP 200 + a choice but reports failure.
- **Contradicts design §7:** "Success = a non-error HTTP response with a choice;
  the content is irrelevant."
- **Impact:** the Test button is unreliable for the configured providers; a user
  could wrongly conclude a working key/provider is broken. Connectivity + auth
  are actually fine.
- **Not patched** (validation-only slice; not a trivially-isolated change — it
  touches the shared `generate_chat_completion` boundary or the probe's
  empty-content handling). **Suggested fix (own small slice):** give the test
  probe a path that treats a returned choice with empty content as success
  (e.g. a `allow_empty=True` kwarg on `generate_chat_completion`, or have
  `test_provider` catch the empty-response `RuntimeError` and classify it as
  `ok` since a choice was returned). Pre-existing — not introduced here.

### Finding #2 — Store `default_provider` has no runtime effect (LOW)
The provider-settings `default_provider` (settable via
`PATCH /api/provider-settings {default_provider}`, shown in
`/api/provider-settings`) is **not** consulted when no per-job provider is given:
`api/server.py:_pick_generate_provider(None)` picks the **first configured**
provider in registry order (deepseek), ignoring the store's `default_provider`
(qwen). It is also **not exposed in `/api/options`**, so the Builder cannot
default its provider dropdown to it either.

- **Vs design §4a tier 2** (provider-settings default should sit above `.env` for
  provider selection), this tier is effectively missing for *provider* (it works
  for *model* — see B5).
- **Impact: low.** The Builder always sends an explicit provider, and per-job
  selection + the store `default_model` precedence both work correctly; only the
  "which provider when none is chosen" default is inert.
- **Not patched** (validation-only). **Suggested fix (own small slice):** have
  `_pick_generate_provider(None)` honor the store `default_provider` (falling
  back to first-configured), and optionally surface `default_provider` in
  `/api/options` so the Builder can pre-select it. Pre-existing — not introduced
  here.

---

## Recommendation
- **This validation branch is docs-only (no code changes) and is safe to
  merge/push** as the validation record.
- The **core Provider-Settings and Large-PDF features are validated and working**
  end-to-end, redaction holds, and cancel behaves as designed.
- **Before relying on the Test Connection button**, address **Finding #1** in a
  small, isolated follow-up slice (it is the most user-visible issue). **Finding
  #2** is low-priority polish.
- No old/consumed branches were merged, rebased, or cherry-picked; no
  force-push; no `docker compose config` output pasted; no real secret printed.
</content>
</invoke>
