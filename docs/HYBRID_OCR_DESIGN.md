# HYBRID_OCR_DESIGN.md — Hybrid OCR & scan-aware extraction (Slice 29, design-only)

> **Status: design only.** This document plans the architecture for hybrid OCR,
> scan-aware extraction, and an eventual OCR-provider boundary (including a future
> Mistral OCR candidate). **No code, schema, dependency, prompt, or extraction
> behaviour changes in this slice.** It decides the shape so the *next* slices can
> be small, verifiable, and safe.
>
> The **repo is the source of truth**. Every "current behaviour" claim below is
> grounded in `pipeline/extract.py`, `pipeline/extraction_metadata.py`,
> `pipeline/run_llm_job.py`, and `api/server.py` as they exist at Slice 28
> (`f3bb0ad`). If the code disagrees with this doc later, trust the code.

---

## 1. Current extraction flow (as built today)

### 1.1 Where PDFs are read

- Entry point: `pipeline/extract.py::extract_file(path, pages=None)` →
  `_extract_pdf(path, pages=pages)` for `.pdf`. PDFs are read with **PyMuPDF**
  (`import fitz`). No other backend path reads PDF bytes for extraction.
- `extract_file` is called from `pipeline/run_llm_job.py::_attach_sources(...)`
  (per attachment), which is the only production caller that turns uploaded
  attachments into model-facing source text.
- `pages` is an optional set of **1-based, original** page numbers. It applies
  **only to PDFs** (mirrors the per-PDF `page_selections` request field); for
  every other type it is ignored. `pages=None` preserves the previous
  whole-document behaviour byte-for-byte.

### 1.2 Where `## Page N` anchors are created

- Inside `_extract_pdf`, each kept page is prefixed with `f"## Page {index}\n…"`,
  where `index` is the **physical, original** page number (1-based). Selecting
  pages 20–21 yields `## Page 20` / `## Page 21`, never renumbered.
- Blank/unreadable pages are **dropped from the text output** without shifting the
  numbering of later pages (the index keeps advancing).
- Slice 23A proved these anchors survive into the model-facing `messages` list
  (`_attach_sources` → `orchestrator.build_messages[_for_preset]` →
  `generate_chat_completion`). Slice 23B added the conditional
  `SOURCE_PAGE_CITATION_DIRECTIVE` when `## Page N` anchors are present.

### 1.3 Per-page text-vs-OCR decision (current "hybrid")

The current extractor is already **page-level**, not whole-document:

1. `body = page.get_text("text").strip()`.
2. If `_is_meaningful_page_text(body)` (≥ 40 chars **or** ≥ 5 word tokens) →
   use embedded text, `method="embedded_text"`.
3. Otherwise the page "wants OCR" (`wanted_ocr = True`):
   - If OCR is available (`_ocr_available()` = tesseract binary + `pytesseract` +
     `PIL`), rasterise at 2× (`fitz.Matrix(2,2)`), preprocess
     (`_preprocess_ocr_image`: grayscale → optional upscale to ≥ 2000 px →
     autocontrast → binary threshold), then `pytesseract.image_to_string`.
     Non-empty → `method="ocr"`.
   - If OCR produced nothing **but** the page had a little embedded text → keep
     that text, `method="embedded_text"` + page warning
     (`ocr_unavailable` or `ocr_empty_fallback_embedded_text`).
   - If genuinely blank/unreadable → dropped from text, `method="none"` + page
     warning (`ocr_unavailable` or `no_text_extracted`).
4. Document `mode` is derived: `pdf_text` / `pdf_ocr` / `pdf_mixed` (and
   `pdf_ocr` when OCR was intended but produced nothing).

OCR availability is probed **once per document** (`_ocr_available`), and the
skip reason is surfaced once per document, not once per page.

### 1.4 Where `extraction_metadata.json` is written

- `_extract_pdf` returns an `ExtractionResult` whose `.metadata` is built by
  `_pdf_metadata` / `_pdf_page_metadata`:
  `{kind:"pdf_extraction", page_count, pages:[{page, method, text_chars,
  word_count, has_page_anchor, warnings}], warnings}`.
- `pipeline/run_llm_job.py::_attach_sources` collects PDF metadata per source via
  `pipeline/extraction_metadata.py::pdf_source_metadata(...)`, then **after**
  attachment extraction and **before** the LLM call writes the job artifact with
  `write_extraction_metadata(job, sources)` (or
  `write_skipped_extraction_metadata(job)` when any PDF metadata was
  unavailable).
- Artifact schema (Slice 24A), `version: 1`:
  ```json
  {
    "version": 1,
    "kind": "extraction_metadata",
    "status": "completed",
    "sources": [
      {
        "filename": "lecture.pdf",
        "content_type": "application/pdf",
        "page_count": 42,
        "pages": [
          {"page": 1, "method": "embedded_text", "text_chars": 1234,
           "word_count": 210, "has_page_anchor": true, "warnings": []}
        ],
        "warnings": []
      }
    ]
  }
  ```
  Skipped variant: `{version:1, kind, status:"skipped", reason, safe_message}`.
- `_safe_method` currently whitelists exactly `{embedded_text, ocr, none,
  unknown}`; any other value is coerced to `unknown`.
- The artifact is downloadable by **exact name** only
  (`GET /api/jobs/{id}/artifacts/extraction_metadata.json`) and is intentionally
  **not** in the generic `ARTIFACTS` list, export bundles, `_artifact_urls`, or
  `_artifact_details` — no generic UI row exposes it. Coverage is **PDF
  attachments only**; non-PDF attachments are omitted.

### 1.5 Current OCR fallback behaviour, summarised

- **Local, Tesseract-only.** No cloud OCR exists. No OCR provider abstraction
  exists — `_ocr_page` calls `pytesseract` directly.
- **Degrade-not-fail.** Missing tesseract/libs never raises; it downgrades to
  embedded text where present, else drops the page, and records a warning.
- **Preflight is OCR-free.** `preflight_pdf(...)` (read-only, bounded sample,
  no rasterise/OCR) feeds `POST /api/preflight/pdf` →
  `_build_pdf_preflight_report` to warn about large/scanned PDFs *before* a job
  exists. It produces a `scanned_flag` ∈ `{text, mixed, image_heavy, unknown}`,
  a verdict ∈ `{ok, warn, blocked}`, a `recommended_mode` ∈
  `{full, first_n, page_range}`, and `allowed_actions`.

---

## 2. Page classification model (future, derived not stored-yet)

Today's per-page `method` is `embedded_text | ocr | none`. The hybrid plan needs a
richer **classification** that distinguishes *why* a page took a path and how
trustworthy the result is. The classification is **derivable from signals the
extractor already computes plus a few cheap additions**; it is not a new heuristic
to be invented blindly.

Proposed page-level `classification` values and their determining signals:

| classification     | meaning                                              | primary signals |
|--------------------|------------------------------------------------------|-----------------|
| `embedded_text`    | rich text layer used directly, no OCR needed         | `_is_meaningful_page_text(body)` true; high `text_chars`/`word_count` |
| `ocr_fallback`     | weak/empty text layer, OCR ran and produced text     | `body` failed the meaningful gate; OCR returned non-empty |
| `likely_scanned`   | image-dominated page (page has images, ~no text)     | image/drawing object presence (`page.get_images()` / `get_drawings()` count) + near-zero `text_chars`; today inferred only at preflight via `image_ratio` |
| `blank_or_low_text`| genuinely empty/near-empty, not clearly an image scan| near-zero `text_chars` **and** no/low image object count |
| `mixed`            | page has both a partial text layer and image regions | meaningful-ish `text_chars` **and** non-trivial image object count |
| `error`            | per-page extraction/OCR raised or was unsafe         | exception caught around a single page; OCR binary failure |

Signals available (cheapest → richest):

1. **Text character count** (`len(body)`) — already computed (`text_chars`).
2. **Word-like token count** (`re.findall(r"\w+", body)`) — already computed
   (`word_count`); drives `_is_meaningful_page_text`.
3. **Image / object presence** — *not* used today in `_extract_pdf`. PyMuPDF can
   report `page.get_images()` (xref image list) and `page.get_drawings()` (vector
   ops) cheaply without rasterising. This is the key new signal that separates
   `likely_scanned` (images present, no text) from `blank_or_low_text` (nothing
   present). **Adding this signal is itself a future slice** — it changes what the
   extractor inspects.
4. **Existing OCR fallback result** — whether OCR ran and whether it returned
   text. Already known in the loop (`page_ocr` non-empty).
5. **Page dimensions** — `page.rect` (width/height). Useful only as a weak hint
   (e.g. detecting unusual aspect ratios / oversized scans) and to estimate
   rasterised pixel cost before OCR. Low priority; record only if free.
6. **Warnings / errors** — already collected per page
   (`ocr_unavailable`, `ocr_empty_fallback_embedded_text`, `no_text_extracted`).
   A new per-page `error` warning would back the `error` classification.

**Compatibility rule:** `classification` is an **additive, advisory** field
layered *next to* the existing `method`. The legacy `method` (`embedded_text | ocr
| none`) stays exactly as-is so Slice 24A consumers keep working. A future slice
maps:

- `embedded_text` → classification `embedded_text` (or `mixed` if image objects
  present).
- `ocr` → classification `ocr_fallback`.
- `none` → classification `blank_or_low_text` **or** `likely_scanned`, decided by
  the new image-object signal.

No classification value should ever be *required* by a consumer; unknown values
must coerce safely (mirroring `_safe_method`'s `unknown` fallback).

---

## 3. Metadata evolution (`extraction_metadata.json`) — proposal, **not applied here**

Goal: make the artifact able to carry OCR-routing facts **without breaking Slice
24A's `version: 1` shape**. The evolution is backward-compatible by being
**purely additive** and **optional**: every new field defaults to absent/null and
older readers ignore unknown keys.

### 3.1 Versioning rule

- Keep `version: 1` readable forever. When the first *new* field actually ships,
  bump to `version: 2` **and** keep all `version: 1` keys present and meaning the
  same. Readers must treat missing new keys as "unknown / not measured", never as
  an error. `_safe_method` and any new `_safe_classification` must keep their
  `unknown` fallback.

### 3.2 Proposed additive **per-page** fields (future)

| field                | type            | source / notes |
|----------------------|-----------------|----------------|
| `classification`     | enum (string)   | §2 values; advisory, additive to `method` |
| `text_density`       | float           | derived, e.g. `word_count / page_area` or `text_chars / page_area`; normalised, no PII |
| `image_object_count` | int             | from `page.get_images()` count; 0 when none |
| `ocr_recommended`    | bool            | routing hint: would hybrid policy OCR this page? |
| `ocr_attempted`      | bool            | did OCR actually run on this page |
| `ocr_provider`       | enum (string)   | `tesseract_local` today; future `mistral` / other — **id only, never URL/key** |
| `ocr_confidence`     | float \| null   | only if the provider reports it; Tesseract avg confidence is optional, null when unknown |
| `skipped_reason`     | enum \| null    | e.g. `ocr_unavailable`, `not_selected`, `below_threshold`, `provider_error` |
| `page_width`/`page_height` | number \| null | from `page.rect`; only if free and useful |

### 3.3 Proposed additive **per-source** fields (future)

| field                | type            | notes |
|----------------------|-----------------|-------|
| `dominant_method`    | enum            | quick summary (`embedded_text`/`ocr`/`mixed`/`scanned`) |
| `ocr_provider`       | enum            | which provider handled this source's OCR (id only) |
| `ocr_page_count`     | int             | how many pages were OCR'd |
| `ocr_timing_ms`      | int \| null     | **only if safe**: wall-clock OCR time for the source; never per-call cloud latency that leaks endpoint behaviour |
| `ocr_cost_estimate`  | object \| null  | **only if safe**: coarse units (e.g. pages billed), never raw pricing pulled from a key-scoped endpoint, never account balances |

### 3.4 Fields explicitly **excluded** from the artifact (security)

Never serialise: provider API keys, full provider URLs, `Authorization` headers,
absolute host filesystem paths, raw provider error payloads/tracebacks, account
identifiers, or anything from `secrets.json` / env. Timing/cost fields are
**opt-in and coarse**; if in doubt, omit. (See §8.)

---

## 4. OCR provider abstraction (backend-only boundary)

Today OCR is hardwired to Tesseract inside `_ocr_page`. The hybrid plan introduces
a **backend-only** provider boundary so additional engines (cloud Mistral OCR, a
future local OCR model) can be added without touching the extraction loop's
control flow.

### 4.1 Boundary shape (conceptual, not yet code)

A small internal interface, e.g. `pipeline/ocr_providers/` with a base contract:

```
OcrProvider.id            -> str   ("tesseract_local", "mistral", ...)
OcrProvider.is_available() -> (bool, reason|None)     # mirrors _ocr_available()
OcrProvider.ocr_page(image_or_page_ref, *, page_number) -> OcrPageResult
```

`OcrPageResult` (whitelisted, JSON-safe):
`{text: str, confidence: float|None, provider_id: str, warnings: list[str],
 error_category: str|None}`.

- The **existing local/Tesseract behaviour becomes the default provider**
  (`tesseract_local`) — a thin wrapper around today's `_ocr_page` /
  `_preprocess_ocr_image`, behaviour-identical. This is the *first* provider slice
  and must be a pure refactor (no output change).
- **Mistral OCR** becomes a second provider implemented **only after** its prereqs
  are verified (§7). It is **cloud**, so it is governed by privacy routing (§5).
- A possible **future local OCR model** (e.g. a local VLM/OCR engine) slots in as a
  third provider with the same contract — no routing/policy rewrite needed.

### 4.2 Inputs / outputs

- **Input:** a single page's rasterised image (or a page handle the provider
  rasterises itself) plus the 1-based page number. Providers must **not** receive
  the whole document, absolute paths, or job/user identifiers beyond what they
  need. Cloud providers receive **only the page image bytes** for selected pages —
  never the job folder, never other attachments.
- **Output:** text + optional confidence + provider id + safe warnings + optional
  safe `error_category`. Output shape is normalised so the extraction loop is
  provider-agnostic.

### 4.3 Error / degrade behaviour

- Any provider failure returns a result with empty `text` and a **safe
  `error_category`** (`provider_unavailable`, `provider_auth_failed`,
  `provider_rate_limited`, `provider_timeout`, `provider_bad_response`,
  `page_too_large`, ...). It **never** raises into the extraction loop and never
  surfaces a raw provider error string.
- Degradation chain (see §5): a failed **cloud** OCR page falls back to
  **local Tesseract**; a failed local OCR page falls back to whatever embedded
  text exists, else the page is dropped (exactly today's `method="none"` path).
  A job is **never failed** by OCR.

### 4.4 Provider secrets stay server-side only

- OCR provider keys live with the existing secret machinery
  (`config/secrets.json` + env, served write-only through the provider-settings
  pattern in `pipeline/provider_config.py` / `provider_settings_store.py`). The
  public DTO exposes only derived non-secret info (`configured`, `key_source`,
  `key_hint` last-4, `base_url_host`) — **identical invariant to LLM provider
  keys** (CLAUDE.md Security Invariants).
- The **frontend never** sees an OCR key, full URL, or `Authorization` header. The
  React app talks only to `/api/*`; the OCR provider call is made **server-side**
  by the backend. (This mirrors the LMM rule that the frontend never talks
  directly to an external boundary.)
- Whether OCR keys reuse the existing provider registry or get a dedicated
  `ocr_provider_settings` store is a **future design decision** — flagged in
  `DECISIONS.md`, not decided here.

---

## 5. Hybrid routing policy (cost- & privacy-aware)

The router decides, **per page**, what to do. Inputs: the page classification
(§2), preflight verdict, the user's page selection, OCR provider availability, and
privacy/cost config. Principles:

1. **Use embedded text directly** when `_is_meaningful_page_text` is true — never
   OCR a page that already has a good text layer. (Already true today; preserved.)
2. **OCR only weak/scanned pages** (`ocr_fallback` / `likely_scanned` /
   `blank_or_low_text` candidates) — never the whole document when only a few
   pages need it. (Already the per-page behaviour; the router formalises it.)
3. **Skip OCR and warn** when OCR is unavailable or when the estimated OCR page
   count exceeds a guard (today preflight already warns past
   `PREFLIGHT_OCR_PAGE_LIMIT`). The job still runs on whatever text exists.
4. **Cloud → local fallback.** If a cloud OCR provider (Mistral) errors, is
   rate-limited, times out, or is disabled, the page falls back to local
   Tesseract; if that also fails, fall back to embedded text / drop. No page
   blocks the job.
5. **Never OCR unnecessarily** — both a *quality* rule (text layer present) and a
   *cost/privacy* rule (cloud OCR costs money and sends page images off-box).

### 5.1 Privacy-aware default

- **Cloud OCR is opt-in and off by default.** With no OCR provider configured (or
  privacy mode on), behaviour is **exactly today's**: local Tesseract only, or
  skip-and-warn. This preserves the app's local-first posture (cf. Ask Your Guide
  staying local-only).
- Cloud OCR sends page images to a third party; the UI must make that explicit
  before enabling it, and it must be a deliberate per-deployment choice, not a
  silent default.

### 5.2 Cost-aware default

- When a cloud provider is enabled, the router still uses **embedded text first**
  and **local OCR before cloud** unless the operator explicitly chooses
  "prefer cloud OCR quality". Default ordering: `embedded_text` →
  `tesseract_local` → (optional) `cloud`. Cloud is the *last* resort for pages
  local OCR handled poorly, not the first.
- Page-range selection and preflight (§6) cap how many pages can be cloud-OCR'd in
  one job, so a 400-page scan can't silently generate a large bill.

---

## 6. Large-PDF handling & OCR interaction

OCR is the most expensive extraction path, so it must respect the existing
large-PDF guardrails rather than bypass them. Relevant existing machinery:

- **Size guard:** `MAX_LLM_ATTACHMENT_BYTES` streaming guard (reused by preflight
  so preflight can't smuggle an oversized file).
- **Preflight:** `POST /api/preflight/pdf` → `preflight_pdf` (OCR-free sample) →
  `_build_pdf_preflight_report` with `scanned_flag`, `verdict`,
  `recommended_mode`, `allowed_actions`, and estimates
  (`text_pages_estimate`, `ocr_pages_estimate`, `image_ratio_est`).
- **Page selection:** `page_selections` request field → `extract_file(pages=...)`
  → only selected pages are read **and only selected pages are OCR'd** (the loop
  skips unselected pages before any OCR work). This is already the cost lever.

Hybrid-OCR interactions to design:

1. **Scanned-vs-text awareness drives the recommended action.** Preflight already
   distinguishes `text` / `mixed` / `image_heavy`. The router should reuse this so
   an `image_heavy` large PDF defaults to `first_n` (sample) rather than full OCR,
   and a `mixed` PDF OCRs only its scanned pages.
2. **OCR page budget.** Keep/extend `PREFLIGHT_OCR_PAGE_LIMIT` as a *cloud* OCR
   page cap too. Past the cap, the router prefers local OCR or skip-and-warn over
   cloud, and surfaces a clear message.
3. **Clear, safe user messages** (extend the existing warn copy), e.g.:
   - "This PDF is too large for direct generation. Compress it, split it, or
     choose a smaller page range."
   - "This PDF is mostly scanned (~N% image pages); OCR will run on ~M pages and
     may be slow. Consider a smaller range."
   - "Cloud OCR is off; scanned pages will use local OCR (or be skipped if local
     OCR is unavailable)."
   All messages are **estimate-labelled** (`is_estimate: true`) and free of host
   paths, provider names-with-URLs, or raw errors.
4. **Automatic split/chunk processing stays deferred** (CLAUDE.md "Deferred
   Work"). Hybrid OCR must *not* implicitly enable auto-split; it operates within
   the current preflight + page-range model.

---

## 7. Mistral OCR implementation plan (prerequisites only — **do not implement**)

Mistral OCR is a **candidate** cloud provider. Its API, cost, limits, and output
shape **must be verified against current official Mistral documentation** at the
start of the implementation slice — not assumed from memory, and not from this
doc. The implementation slice's first task is a written verification of:

1. **Current API endpoint & request format** — exact path, HTTP method, auth
   header form, and request body (file upload vs. URL vs. base64; per-page vs.
   whole-document).
2. **Supported file types** — PDF directly? images only? Does it accept a PDF or
   require pre-rasterised page images? (Affects whether we send `fitz` page
   images or the PDF.)
3. **Page limits** — max pages/file, max file size, max requests, any document
   length cap.
4. **Pricing / cost model** — per-page vs. per-token vs. per-request; this gates
   the cost-aware router (§5.2) and the OCR page budget (§6).
5. **Output format** — does it return Markdown, plain text, images, layout boxes,
   or structured per-page content? (Determines how its output maps onto our
   `## Page N` anchor + text contract, and whether layout/structure is usable.)
6. **Rate limits** — requests/min, concurrency, burst behaviour → drives backoff
   and the `provider_rate_limited` degrade path.
7. **Privacy / data-retention terms** — does Mistral retain or train on submitted
   documents? Retention window? This is a **blocking** prerequisite: if retention
   is unacceptable for the operator's content, cloud OCR stays opt-in with a clear
   warning, and may be disabled by default per deployment.
8. **Error behaviour** — error response shapes/status codes to map onto safe
   `error_category` values (never surfaced raw).
9. **Markdown/text/layout/page-structure** — confirm exactly what is returned so
   the provider wrapper can normalise it into `OcrPageResult.text` (+ optional
   structure) without guessing.

Only after these are verified and recorded (in a validation doc) may the Mistral
provider be coded behind the §4 boundary, governed by the §5 privacy/cost router.

---

## 8. Security & privacy constraints (must hold for every OCR slice)

These extend the existing CLAUDE.md Security Invariants to OCR:

- **No provider keys in the frontend.** OCR keys are server-side only,
  write-only over the API, with a key-less public DTO (only `configured`,
  `key_source`, `key_hint`, `base_url_host`).
- **No provider keys/tokens in artifacts, logs, docs, tests, exports, or served
  JS.** `extraction_metadata.json` carries provider **ids** only — never keys,
  full URLs, or `Authorization` headers.
- **No absolute host paths** in artifacts or responses (Slice 24A already keeps
  paths out; new fields must too).
- **No raw OCR provider error dumps to users.** Cloud/provider errors map to safe
  `error_category` enums and concise user warnings; tracebacks and raw payloads
  stay in server-side logs by type only.
- **Degrade, don't fail.** OCR (local or cloud) can never fail a job, never block
  render, never change job status — same advisory posture as
  `extraction_metadata.json`, `math_verification.json`, and `guide_lint.json`.
- **Privacy default = local.** Cloud OCR is opt-in; default behaviour sends no
  page images off-box. Enabling cloud OCR must be an explicit, clearly-labelled
  per-deployment choice.
- **User-visible warnings are safe and concise** — estimate-labelled, no host
  paths, no key/URL leakage, no provider internals.

---

## 9. Proposed implementation slices (next 5–7, small & verifiable)

Each is one branch off `chrome-renderer-v1`, verify-and-commit between, surgical
edits only. Earlier slices unlock later ones; cloud OCR comes late and gated.

1. **Slice 30 — page image-object signal (extractor, additive metadata only).**
   Add `page.get_images()` / `get_drawings()` counts and `page.rect` dimensions to
   the per-page metadata builder. **No routing change, no OCR change** — purely
   enrich the data so classification (§2) is possible. Bump artifact to
   `version: 2` with additive optional fields; keep `version: 1` keys intact.
   Verify with a focused `test_scripts/test_*` + the existing
   `test_extraction_metadata.py`.

2. **Slice 31 — page classification field (advisory).** Compute `classification`
   (§2) from existing + Slice 30 signals; write it next to `method` (legacy
   `method` unchanged). Add `_safe_classification` with `unknown` fallback. Still
   **no behaviour change** to which pages get OCR'd.

3. **Slice 32 — OCR provider boundary refactor (pure).** Introduce
   `pipeline/ocr_providers/` with the §4 contract and wrap today's Tesseract path
   as `tesseract_local`. **Behaviour-identical** — golden test that extraction
   output and `mode`/`method` are byte-stable before/after.

4. **Slice 33 — hybrid routing policy core (pure, deterministic).** A standalone
   router module (§5) that, given page classifications + preflight + config,
   returns a per-page plan (`use_text` / `ocr_local` / `ocr_cloud` / `skip`).
   **Not yet wired** into the extractor — pure core + tests first (mirrors the
   Slice 18/19 "pure core, then integrate" pattern).

5. **Slice 34 — wire router into extraction (local only).** Use the router to
   drive the existing local Tesseract path; record `ocr_recommended` /
   `ocr_attempted` / `skipped_reason` in metadata. Cloud OCR still absent. Prove
   no regression on existing fixtures; large-PDF/page-range behaviour preserved.

6. **Slice 35 — Mistral OCR prerequisite verification (docs-only).** Verify and
   record §7 items 1–9 against current official docs in a new validation doc. **No
   code, no dependency, no API call to Mistral.** Gate for Slice 36.

7. **Slice 36 — Mistral OCR provider (cloud, opt-in, gated).** Implement the
   second provider behind the §4 boundary and §5 cost/privacy router, server-side
   key only, off by default, cloud→local fallback, safe `error_category`,
   page-budget capped. Only after Slice 35 passes.

(Optional later: a local OCR-model provider as a third `OcrProvider`; UI surfacing
of classification in JobDetails, mirroring the math/guide-lint advisory tabs.)

---

## 10. Out of scope for Slice 29 (this slice)

No backend/frontend code, no tests/fixtures, no dependency, no extraction or OCR
heuristic change, no schema change, no prompt/provider/`/api/jobs/llm`/Ask/
retrieval/render-pipeline change, no Mistral dependency or API call, no secret
printing, no `docker compose config`. Docs only.
