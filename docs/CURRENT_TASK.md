# CURRENT_TASK.md — Live handoff

> Update this every slice. For stable overview see `PROJECT_CONTEXT.md`; for the
> "why" behind choices see `DECISIONS.md`.

---

## Slice 34 — wire local OCR routing into extraction (IMPLEMENTED — uncommitted on `slice34-wire-local-ocr-routing`).

- **Purpose:** first **live** integration of the Slice 33 routing policy into the
  PDF extraction path — **local-only and behaviour-compatible**. Extraction now
  records a safe, advisory per-page **routing decision**; it does **not** add
  Mistral/cloud OCR, provider settings, UI, prompt changes, or any
  generation-gating. This is Slice 34 in `docs/HYBRID_OCR_DESIGN.md` §9.
- **Recorder, not a router (key design):** the policy is consulted *after* a page's
  method/text/visual signals are known and is recorded as metadata; it **never
  decides whether OCR actually runs.** The unchanged per-page text-vs-OCR logic in
  `_extract_pdf` still does that, so **extracted text and `## Page N` anchors are
  byte-identical** to before and OCR-availability behaviour is preserved. (A blank
  page that extraction historically *attempts* to OCR still does so even though the
  advisory route says `skip_ocr` — advisory route metadata, not yet a
  behaviour-changing router.)
- **Where it's wired:** `pipeline/extract.py` imports
  `ocr_routing.decide_ocr_route` and `extraction_metadata.classify_pdf_page_record`.
  New `_pdf_route_decision(record, *, ocr_ready)` maps a page's already-collected
  signals → advisory `classification` (shared classifier = single source of truth)
  → policy decision, with `local_ocr_available = ocr_ready` (the document-level
  Tesseract availability the extractor already probed) and `allow_cloud_ocr=False`.
  `_pdf_page_metadata(..., ocr_ready=...)` attaches the route to every PDF page.
- **New per-page fields (additive):** `ocr_route_action`, `ocr_route_provider`,
  `ocr_route_reason`, `ocr_route_confidence`, `ocr_route_warnings` — all
  closed-vocabulary / JSON-safe. **Local-only:** `ocr_route_provider` is only ever
  `"tesseract_local"` or `null` (never a cloud id).
- **Sanitiser carries, not recomputes:** `extraction_metadata._safe_page` whitelists
  each route token against the vocabularies imported from `ocr_routing` (new
  `_safe_route_*` helpers) — the same carry-and-coerce posture it already applies to
  `method`/`warnings`. A smuggled `ocr_route_*` value coerces to a fixed safe token;
  no path, secret, image blob, URL, or free-text error can survive. Route fields are
  emitted **only when the extractor supplied them**, so legacy / hand-built / non-PDF
  records stay byte-identical.
- **`extraction_metadata.json` stays `version: 2`** — additive page fields under the
  established "bump once on the first new field (Slice 30), not on every additive
  field" rule (see `DECISIONS.md`). No other artifact schema touched.
- **Degrade-not-fail:** `_pdf_route_decision` wraps the whole adapter; any unexpected
  error records a fixed safe route (`action:"unknown"`,
  `reason:"routing_unavailable"`, `warnings:["routing_input_unrecognized"]`) and
  never propagates. Routing can never fail a generation.
- **Scope guard — NO change to:** Mistral/cloud OCR, provider settings, prompts,
  `/api/jobs/llm` request fields, frontend/UI, Ask/retrieval, LanceDB/embeddings,
  the generic `ARTIFACTS`/export-bundle lists, the PDF/Chromium render pipeline,
  generation gating, or the `validation.json` / `math_verification.json` /
  `guide_lint.json` schemas. The OCR engine still goes through the Slice 32 local
  provider boundary unchanged.
- **Files changed:** `pipeline/extract.py`, `pipeline/extraction_metadata.py`,
  `test_scripts/test_ocr_routing_integration.py` (new), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `npm --prefix frontend run build` ✓ · `npm --prefix frontend run
  test` ✓ · `python -m compileall api pipeline test_scripts` ✓ ·
  `test_ocr_routing_integration` 56/56 (fitz e2e skipped on host) ·
  `test_ocr_routing_policy` 120/120 · `test_extraction_metadata` 9/9 ·
  `test_pdf_page_classification` 56/56 · `test_pdf_visual_signals` 44/44 ·
  `test_ocr_provider` 18/18 · `test_math_verifier` 74/74 · `test_guide_lint` 74/74 ·
  `test_eval_harness` 64/64 · `test_page_anchor_reachability` 21/21 ·
  `test_source_page_citations` 19/19 · `test_ask_retrieval_relevance` 12/12 ·
  `test_ask_lexical_hygiene` 34/34 · `test_guide_lint_artifact` 26/26 ·
  `run_eval.py --offline --all` scored 3 (no regression) · `git diff --check` clean.
  `smoke_release.py` requires the live Dockerized app on :8000 (not running in this
  host shell) — run it in Docker for full e2e coverage, along with the fitz path.
- **Next:** Slice 35 — Mistral OCR prerequisite verification (docs-only; gate for the
  gated cloud provider in Slice 36). Routing stays local-only/advisory until then.

---

## Slice 33 — hybrid OCR routing policy core (COMMITTED + MERGED to `chrome-renderer-v1`, commit `5296976`).

- **Purpose:** add a **pure, deterministic OCR routing-policy core** that decides
  what *should* happen for a page (use embedded text / local OCR / skip / cloud
  candidate) from the existing advisory page classification, **without wiring it
  into extraction**. This is the "pure core, then integrate" step in
  `docs/HYBRID_OCR_DESIGN.md` §9 (Slice 33); §5/§6 describe the policy. Extraction
  behaviour, OCR calls, prompts, metadata artifacts, and generation are unchanged.
- **New module `pipeline/ocr_routing.py`:**
  - `decide_ocr_route(page_metadata, config=None) -> decision` — single page.
  - `decide_ocr_routes(pages, config=None) -> [decision, ...]` — list with a
    shared OCR-page budget applied in input order.
  - `default_config()` — local-first, cloud-off defaults.
  - Reads **only** `page_metadata["classification"]`; never trusts or echoes any
    other input field, so smuggled paths/secrets/image blobs cannot leak.
  - **Pure / deterministic / dependency-free:** no I/O, clock, or randomness; no
    import of `fitz`, Tesseract, `pipeline.ocr_provider`, cloud providers, or
    provider settings. The classification vocabulary is mirrored locally.
- **Decision shape (JSON-safe, closed vocab only):**
  `{action, provider, reason, confidence, warnings}`.
  - `action` ∈ `{use_embedded_text, use_local_ocr, skip_ocr, cloud_ocr_candidate,
    unknown}`.
  - `provider` is `null` or the literal `"tesseract_local"` (no key/URL/path,
    `null` for cloud candidates — no cloud provider exists).
  - `reason` / `warnings` are fixed tokens (`REASONS` / `WARNINGS`); `confidence`
    ∈ `{high, medium, low}`.
- **Policy mapping (from classification):**
  - `embedded_text` → `use_embedded_text` (`embedded_text_sufficient`, high).
  - `mixed` → `use_embedded_text` (`mixed_has_meaningful_text`, medium) — trust
    the text layer, don't OCR a page that already has meaningful text.
  - `ocr_fallback` → `use_embedded_text` (`ocr_already_applied`, high) — OCR
    already ran and produced this page's captured text; re-OCRing would duplicate
    work and change nothing (documented choice).
  - `likely_scanned` → `use_local_ocr` (`scanned_needs_ocr`, provider
    `tesseract_local`), subject to availability + budget.
  - `blank_or_low_text` → `skip_ocr` (`blank_low_text_no_visual`, high).
  - `unknown`/unrecognised → `unknown` (`unknown_classification`, low) —
    conservative, never cloud, never spends budget.
  - `error` → `skip_ocr` (`classification_error`, low).
- **Local / cloud / budget behaviour:**
  - **Local-first, cloud-off by default.** `cloud_ocr_candidate` is returned
    **only** when `allow_cloud_ocr` is an explicit `True` AND local OCR is
    unavailable; provider stays `null` (advisory future option, nothing wired).
    With local available, cloud is never volunteered even when allowed.
  - Local unavailable + cloud off → `skip_ocr` with `local_ocr_unavailable` +
    `cloud_ocr_disabled` warnings (job still runs on whatever text exists).
  - **Budget:** `page_budget_remaining` (or `max_ocr_pages`) caps OCR-bound
    pages; only OCR actions consume budget; once exhausted, OCR-bound pages
    downgrade to `skip_ocr` (`ocr_budget_exhausted`). Deterministic by input order.
  - Config sanitiser rejects truthy non-booleans (a smuggled string can't flip
    cloud on) and coerces bad counts to `None`.
- **Failure is impossible:** any malformed/hostile input → fixed safe decision
  (`action:"unknown"`, `reason:"routing_unavailable"`,
  `warnings:["routing_input_unrecognized"]`); `decide_ocr_routes` on a non-list →
  `[]`, and a bad page mid-batch degrades without aborting the batch.
- **NOT wired into extraction.** Nothing in `pipeline/extract.py`, `api/`, or the
  frontend imports `ocr_routing`; `grep` confirms only the module + its test
  reference it. No extraction text change, no OCR call, no metadata-artifact change.
- **Scope guard — NO change to:** `pipeline/extract.py`, Mistral/cloud OCR,
  provider settings, prompts, `/api/jobs/llm` request fields, frontend/UI,
  Ask/retrieval, LanceDB/embeddings, the generic `ARTIFACTS`/export-bundle lists,
  the PDF/Chromium render pipeline, generation gating, or the `validation.json` /
  `math_verification.json` / `guide_lint.json` / `extraction_metadata.json` schemas.
- **Files changed:** `pipeline/ocr_routing.py` (new),
  `test_scripts/test_ocr_routing_policy.py` (new), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `npm --prefix frontend run build` ✓ · `npm --prefix frontend run
  test` ✓ · `python -m compileall api pipeline test_scripts` ✓ ·
  `test_ocr_routing_policy` 120/120 · `test_math_verifier` 74/74 · `test_guide_lint`
  74/74 · `test_eval_harness` 64/64 · `test_page_anchor_reachability` 21/21 ·
  `test_source_page_citations` 19/19 · `test_extraction_metadata` 9/9 ·
  `test_pdf_visual_signals` 44/44 · `test_pdf_page_classification` 56/56 ·
  `test_ocr_provider` 18/18 (tesseract-gated e2e skipped on host) ·
  `test_ask_retrieval_relevance` 12/12 · `test_ask_lexical_hygiene` 34/34 ·
  `test_guide_lint_artifact` 26/26 · `run_eval.py --offline --all` scored 3 (no
  regression) · `git diff --check` clean · `smoke_release.py` ✓.
- **Next:** Slice 34 — wire the router into the local Tesseract extraction path
  and record `ocr_recommended` / `ocr_attempted` / `skipped_reason` in metadata
  (the first slice that *changes* what extraction records; still local-only).

---

## Slice 32 — OCR provider boundary refactor (COMMITTED + MERGED to `chrome-renderer-v1`, commit `c42837c`).

- **Purpose:** isolate OCR behind a clean **backend-only provider boundary**
  before any routing change or cloud OCR provider, with **local behaviour kept
  byte-identical**. Slice 30 added visual signals, Slice 31 added advisory page
  classification; this is Slice 32 in the `docs/HYBRID_OCR_DESIGN.md` §9 sequence
  (it is the "pure refactor" slice — no behaviour change).
- **New module `pipeline/ocr_provider.py`:**
  - `OcrRequest(page, page_number)` — a single `fitz` page handle + 1-based page
    number; the provider rasterises the page itself (no whole-document, no paths,
    no job/user ids cross the boundary).
  - `OcrResult(text, provider_id, confidence=None, warnings=[], error_category=None)`
    — normalised, JSON-safe; whitelisted fields only (no image bytes, raw page
    data, paths, URLs, keys, or raw error strings). `confidence` stays `None`
    (the local `image_to_string` path doesn't return it cheaply).
  - `OcrProvider` — base contract: `provider_id`, `is_available() -> (ready,
    reason)`, `ocr_page(request) -> OcrResult`.
  - `TesseractLocalOcrProvider` (`provider_id = "tesseract_local"`) — the default
    and only provider; a **behaviour-identical** wrapper around the old in-line
    `_ocr_available` / `_ocr_page` / `_preprocess_ocr_image`. `_preprocess_ocr_image`
    moved here.
  - `get_default_ocr_provider()` — returns a stable module-level singleton.
- **`pipeline/extract.py` rewiring (minimal):** `_extract_pdf` now does
  `ocr_provider = get_default_ocr_provider()`, `ocr_ready, reason =
  ocr_provider.is_available()`, and `ocr_provider.ocr_page(OcrRequest(page=page,
  page_number=index)).text` (still guarded by `if ocr_ready`). `_ocr_available()`
  remains as a thin backward-compatible shim delegating to the provider (kept for
  `preflight_pdf` + existing tests that import it). `_ocr_page` /
  `_preprocess_ocr_image` removed from `extract.py` (no external callers); unused
  `import shutil` dropped.
- **Behaviour preserved (degrade-not-fail unchanged):** same pages OCR'd, same
  extracted text, same `mode`/`method` derivation, same per-page warnings
  (`ocr_unavailable` / `ocr_empty_fallback_embedded_text` / `no_text_extracted`),
  same once-per-document availability message strings. The old in-line OCR path did
  **not** catch raster/recognise exceptions, so — to stay byte-identical — the local
  provider does **not** either; `error_category` is reserved for future providers.
- **`extraction_metadata.json`: UNCHANGED.** No `ocr_provider` field added, **no
  version bump** (stays `version: 2`). Adding the provider id now would alter the
  artifact bytes for OCR'd pages; it is deferred to the routing slice (34). The
  existing `test_extraction_metadata.py` exact-value asserts pass unchanged = the
  byte-identical proof.
- **Scope guard — NO change to:** Mistral/cloud OCR, OCR routing, page
  classification, prompts, provider settings, `/api/jobs/llm` request fields,
  frontend/UI, Ask/retrieval, LanceDB/embeddings, the generic `ARTIFACTS`/
  export-bundle lists, the PDF/Chromium render pipeline, generation gating, or the
  `validation.json` / `math_verification.json` / `guide_lint.json` schemas.
- **Files changed:** `pipeline/ocr_provider.py` (new), `pipeline/extract.py`
  (rewire), `test_scripts/test_ocr_provider.py` (new), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `npm --prefix frontend run build` ✓ · `npm --prefix frontend run
  test` ✓ · `python -m compileall api pipeline test_scripts` ✓ · `test_ocr_provider`
  37/37 (incl. fitz integration paths: provider success, text-page-skips-OCR,
  unavailable-degrade, empty-OCR-drop, no-leak) · `test_math_verifier` 74/74 ·
  `test_guide_lint` 74/74 · `test_eval_harness` 64/64 ·
  `test_page_anchor_reachability` 21/21 · `test_source_page_citations` 19/19 ·
  `test_extraction_metadata` 9/9 host (46/46 with fitz) · `test_pdf_visual_signals`
  44/44 · `test_pdf_page_classification` 56/56 · `test_ask_retrieval_relevance`
  12/12 · `test_ask_lexical_hygiene` 34/34 · `test_guide_lint_artifact` 26/26 ·
  `eval/run_eval.py --offline --all` ✓ · `git diff --check` clean ·
  `smoke_release.py` (live :8000) ✓. **Not committed** (per slice rule).

---

## Slice 31 — advisory PDF page classification metadata (IMPLEMENTED — uncommitted on `slice31-pdf-page-classification-metadata`).

- **Purpose:** the next step after Slice 30. Use the existing text/word/method
  signals (Slice 24A) plus the visual/object signals (Slice 30) to emit an
  **advisory page classification** in `extraction_metadata.json`. This slice
  **only adds derived metadata** — it does **not** call OCR, reroute pages,
  change extracted text, or touch prompts/generation.
- **Fields added (per PDF page, advisory-only):**
  - `classification` — one of `embedded_text | ocr_fallback | likely_scanned |
    blank_or_low_text | mixed | unknown | error` (closed vocabulary; `unknown`
    fallback, like `_safe_method`).
  - `classification_reasons` — list of fixed, whitelisted reason tokens
    (e.g. `method_ocr`, `meaningful_embedded_text`, `images_present`,
    `no_visual_objects`, `visual_signals_unavailable`,
    `classification_unavailable`). No free text, paths, or values.
  - `ocr_recommended` — bool routing **hint** only; `True` only for
    `likely_scanned`. Nothing reads it yet.
- **Where computed:** `pipeline/extraction_metadata.py::_classify_pdf_page(record)`
  (pure helper) called from `_safe_page` **after** the record is fully sanitized.
  It reads only the already-sanitized numeric/method/visual fields — never any
  upstream-supplied `classification` key — so a smuggled value is overwritten by
  construction. `_safe_classification` / `_safe_reasons` whitelist the persisted
  output.
- **Heuristics (conservative, deterministic):** `method == "ocr"` →
  `ocr_fallback`. `embedded_text` with meaningful text (≥40 chars OR ≥5 word
  tokens, mirroring `_is_meaningful_page_text`) → `embedded_text`, or `mixed` when
  image objects are present. Low/zero-text pages (`none`, or sparse `embedded_text`
  fallback) → `likely_scanned` when image/drawing objects are present,
  `blank_or_low_text` when visuals were positively measured-absent, else `unknown`
  (visual signal missing → cannot distinguish scan from blank). Explicit per-page
  error warning (`page_extraction_error` / `ocr_error` / `extraction_error`, none
  emitted today) → `error`.
- **Versioning:** `extraction_metadata.json` stays **`version: 2`**. The new fields
  are purely additive/optional, consistent with the Slice 29 rule (bump once when
  the first new field ships — done in Slice 30; later additive fields keep v2). No
  version churn.
- **Degrade-not-fail:** `_classify_pdf_page` never raises; any unexpected input
  degrades to `classification: "unknown"` + `["classification_unavailable"]`.
  Persisted classification is **always** in the closed vocabulary.
- **Scope guard — NO change to:** extraction text output, OCR behaviour/routing,
  Mistral/cloud OCR, provider settings, prompts, `/api/jobs/llm` request fields,
  frontend/UI, Ask/retrieval, LanceDB/embeddings, the generic `ARTIFACTS`/
  export-bundle lists, the PDF/Chromium render pipeline, generation gating, or the
  `validation.json` / `math_verification.json` / `guide_lint.json` schemas.
- **Files changed:** `pipeline/extraction_metadata.py`,
  `test_scripts/test_pdf_page_classification.py` (new),
  `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `npm --prefix frontend run build` ✓ · `npm --prefix frontend run
  test` ✓ · `python -m compileall api pipeline test_scripts` ✓ · backend suites
  (`test_math_verifier` 74/74, `test_guide_lint` 74/74, `test_eval_harness` 64/64,
  `test_page_anchor_reachability` 21/21, `test_source_page_citations` 19/19,
  `test_extraction_metadata` 9/9, `test_pdf_visual_signals` 44/44,
  `test_ask_retrieval_relevance` 12/0, `test_ask_lexical_hygiene` 34/0,
  `test_guide_lint_artifact` 26/26, `test_pdf_page_classification` 56/56) ✓ ·
  `eval/run_eval.py --offline --all` ✓ (delta 0.0) · `git diff --check` ✓ ·
  `smoke_release.py` ✓. Host Python lacks PyMuPDF so the PDF-attachment section of
  `test_extraction_metadata.py` SKIPs (documented); classification is fully covered
  by the plain-dict tests in `test_pdf_page_classification.py` and runs end-to-end
  in Docker.
- **Not committed** (per task instruction).

---

## Slice 30 — PDF page visual-signal metadata (COMMITTED + MERGED to `chrome-renderer-v1`, commit `752bf03`).

- **Purpose:** the first implementation step after the Slice 29 design. Enrich the
  per-page PDF `extraction_metadata.json` records with cheap, additive
  visual/object signals so a **future** slice can classify scanned/image-heavy
  pages and route OCR. This slice **only collects data** — it does **not** classify
  pages, decide OCR routing, call any OCR, or change extracted text.
- **Fields added (per PDF page, advisory-only, numeric/boolean):**
  - `image_object_count` — `len(page.get_images(full=False))`; `None` if unmeasured.
  - `drawing_object_count` — `len(page.get_drawings())`; `None` if unmeasured.
  - `has_images` / `has_drawings` — booleans derived from the counts; `None` if
    unmeasured.
  - `page_width` / `page_height` — from `page.rect` (points, 2-dp); `None` if
    unmeasured.
  - `visual_warnings` — only present when a signal failed; carries safe category
    strings (`visual_image_signal_unavailable`, `visual_drawing_signal_unavailable`,
    `visual_dimension_signal_unavailable`) — never exception text or paths.
- **Where collected:** `pipeline/extract.py::_pdf_visual_signals(page)`, called once
  per processed page inside `_extract_pdf`'s loop (after the page-selection skip,
  before/around the existing text/OCR decision). Merged into the page record by
  `_pdf_page_metadata(..., visual=...)`. Carried through the artifact sanitiser
  `pipeline/extraction_metadata.py::_safe_page` (whitelisted + coerced).
- **Versioning:** `extraction_metadata.json` bumped `version: 1 → 2` (both the
  `completed` and `skipped` payloads) per the Slice 29 rule "bump to v2 when the
  first new field ships". All v1 keys remain present and unchanged; new fields are
  optional/additive; missing new keys mean "not measured", never an error.
- **Degrade-not-fail:** `_pdf_visual_signals` never raises — each of the three
  signal groups is independently guarded; on failure the field is `None` and a safe
  category is appended to `visual_warnings`. Extraction text, mode/method, job
  status, and all other artifacts are untouched. No image bytes, object data,
  paths, or text ever enter the metadata.
- **Scope guard — NO change to:** extraction text output, OCR behaviour/routing,
  page classification (deferred to Slice 31), Mistral/cloud OCR, provider settings,
  prompts, `/api/jobs/llm` request fields, frontend/UI, Ask/retrieval,
  LanceDB/embeddings, the generic `ARTIFACTS`/export-bundle lists, the
  PDF/Chromium render pipeline, or generation gating. No `validation.json` /
  `math_verification.json` / `guide_lint.json` schema change.
- **Files changed:** `pipeline/extract.py`, `pipeline/extraction_metadata.py`,
  `test_scripts/test_extraction_metadata.py` (version 1→2 + visual-field
  assertions), `test_scripts/test_pdf_visual_signals.py` (new),
  `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `npm --prefix frontend run build` ✓ · `npm --prefix frontend run
  test` ✓ · `python -m compileall api pipeline test_scripts` ✓ · backend suites
  (`test_math_verifier` 74/74, `test_guide_lint` 74/74, `test_eval_harness` 64/64,
  `test_page_anchor_reachability` 21/21, `test_source_page_citations` 19/19,
  `test_extraction_metadata` 9/9, `test_ask_retrieval_relevance` 12/0,
  `test_ask_lexical_hygiene` 34/0, `test_guide_lint_artifact` 26/26,
  `test_pdf_visual_signals` 44/44) ✓ · `eval/run_eval.py --offline --all` ✓ ·
  `git diff --check` ✓ · `smoke_release.py` 29/0 ✓. Host Python lacks PyMuPDF, so
  the PDF-attachment + route sections of `test_extraction_metadata.py` SKIP
  (documented behaviour); the visual-signal logic is fully covered by the
  fake-page tests in `test_pdf_visual_signals.py` and runs end-to-end in Docker.

---

## Slice 29 — Hybrid OCR & scan-aware extraction architecture (DESIGN-ONLY — committed `d0b91f1`, merged to `chrome-renderer-v1`).

- **Purpose:** decide the architecture for hybrid OCR, scan-aware extraction, and
  a future OCR-provider boundary (with Mistral OCR as a candidate cloud provider)
  **before** writing any OCR code. Docs only — no application code, no schema, no
  dependency, no extraction/OCR behaviour change.
- **Deliverable:** new `docs/HYBRID_OCR_DESIGN.md` covering: (1) the current
  extraction flow grounded in `pipeline/extract.py` /
  `pipeline/extraction_metadata.py` / `pipeline/run_llm_job.py` /
  `api/server.py`; (2) a page-classification model (`embedded_text`,
  `ocr_fallback`, `likely_scanned`, `blank_or_low_text`, `mixed`, `error`) and the
  signals that determine each; (3) a backward-compatible `extraction_metadata.json`
  evolution (additive/optional fields, `version: 1` stays readable, bump to
  `version: 2` only when a new field ships); (4) a backend-only OCR provider
  boundary (`tesseract_local` default, future `mistral`, future local model);
  (5) a cost- & privacy-aware hybrid routing policy (embedded → local → cloud,
  cloud opt-in/off by default); (6) large-PDF interaction reusing existing
  preflight + page-range + size guards; (7) Mistral OCR **prerequisites to verify**
  (endpoint/format, file types, page limits, pricing, output shape, rate limits,
  privacy/retention, errors) — **not implemented**; (8) OCR security/privacy
  constraints extending CLAUDE.md invariants; (9) a proposed 7-slice sequence
  (Slices 30–36).
- **Grounding facts captured (verified in code, not assumed):**
  - PDFs read via PyMuPDF (`fitz`) in `_extract_pdf`; `## Page N` anchors use the
    **original physical** page index; per-page text/OCR decision is already
    page-level (`_is_meaningful_page_text` ≥ 40 chars or ≥ 5 word tokens →
    embedded; else per-page Tesseract OCR; else drop).
  - `extraction_metadata.json` (Slice 24A, `version: 1`) is written in
    `_attach_sources` after extraction, before the LLM call; per-page `method` ∈
    `{embedded_text, ocr, none}` and `_safe_method` whitelists
    `{embedded_text, ocr, none, unknown}`. Downloadable by exact name only; not in
    generic artifact lists; PDF attachments only.
  - Preflight (`preflight_pdf` → `POST /api/preflight/pdf` →
    `_build_pdf_preflight_report`) is OCR-free, produces `scanned_flag`
    (`text`/`mixed`/`image_heavy`/`unknown`), `verdict`, `recommended_mode`,
    `allowed_actions`; image-object presence is **not** inspected today (the key
    new signal the design adds in Slice 30).
- **Key decisions:** classification is **additive/advisory** next to legacy
  `method` (never required, unknown-safe); OCR keys follow the existing
  server-side-only, write-only, key-less-DTO provider pattern; cloud OCR is
  **opt-in and off by default** (local-first, mirroring Ask staying local-only);
  OCR is **degrade-not-fail** and never changes job status (same posture as
  `extraction_metadata.json` / `math_verification.json` / `guide_lint.json`);
  auto-split stays deferred.
- **Scope guard — NO change to:** any backend/frontend/pipeline file, tests,
  fixtures, dependencies, extraction/OCR heuristics, artifact schema, prompts,
  provider settings, `/api/jobs/llm` request fields, Ask/retrieval, or the
  PDF/Chromium render pipeline. No Mistral dependency or API call. Updated only
  `docs/HYBRID_OCR_DESIGN.md` (new), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation (docs-only):** `git diff --check` ✓ · `git diff --name-only` shows
  docs only ✓. No build/smoke required (no code touched).

---

## Slice 28 — JobDetails guide-lint UI tab (DONE — committed on trunk as `f3bb0ad`).

- **Purpose:** surface the per-job `guide_lint.json` artifact (Slice 27) in the
  JobDetails drawer as a read-only, advisory panel, closing the
  visibility-parity gap with the math-verification UI (Slice 22). Frontend/UI
  only — **no** backend, pipeline, or artifact-schema change.
- **Pattern:** mirrors the Slice 22 math-verification UI architecture exactly:
  - `frontend/src/guideLintArtifact.js` — pure, React-free normalizer
    (`summarizeGuideLintArtifact`, `safeLintExcerpt`, `GUIDE_LINT_ARTIFACT`).
  - `frontend/src/components/GuideLintPanel.jsx` — drawer panel component.
  - `frontend/scripts/verify-guide-lint.mjs` — plain-node helper harness, wired
    into the `test` chain + a `test:guide-lint` script in `frontend/package.json`.
- **UI placement:** new **"Guide Lint"** tab in the JobDetails drawer tab bar
  (`RecentJobsPanel.jsx`), placed immediately after **Verification**, icon
  `FileCheck2`. Available for any job (not gated on `canEdit`), mirroring the
  Verification tab; the panel itself renders a calm "not available" state for
  jobs without the artifact.
- **Lazy fetch:** `GuideLintPanel` fetches `guide_lint.json` via the existing
  `getJobArtifact(jobId, "guide_lint.json")` client helper in a `useEffect`. The
  panel is only mounted when `drawerTab === "guide-lint"`, so the request fires
  only when the tab is opened (and re-fires if `jobId` changes).
- **States handled:** loading · completed (status chip by worst severity, source
  `clean.md`, summary tiles total/errors/warnings/info, top findings sorted
  error→warning→info with severity tag, rule, message, line) · skipped (safe
  message) · missing 404 ("No guide-lint artifact is available for this job") ·
  malformed / wrong kind ("could not be read") · fetch/network error (safe
  generic message). Copy stays explicitly advisory ("checks structure,
  formatting, and math-render risk — not whether the content is correct").
- **Compact view:** findings capped at `GUIDE_LINT_DISPLAY_LIMIT` (8) with a
  "N additional findings hidden" note; excerpts whitespace-collapsed/truncated;
  no `dangerouslySetInnerHTML`; no raw URLs/paths/secrets surfaced.
- **CSS:** reuses the existing compact `sg-mathv-claim` row layout; added two
  severity-tint rules (`.sg-mathv-claim.error`, `.sg-mathv-claim.warning`) in
  `design-system.css` alongside the math `.mismatch`/`.unparseable` tints.
- **Scope guard — NO change to:** backend, pipeline, artifact schema, generic
  artifact lists, Exports bundles, prompts, provider/model behavior,
  `/api/jobs/llm` request fields, OCR/extraction, Ask/retrieval,
  LanceDB/embeddings, or the PDF/Chromium render pipeline. No rerun/recompute
  button; no job mutation.
- **Validation:** `npm --prefix frontend run build` ✓ · `npm --prefix frontend
  run test` (incl. new `verify-guide-lint.mjs`, 22 checks) ✓ · `python -m
  compileall api pipeline test_scripts` ✓ · math_verifier / guide_lint /
  eval_harness / page_anchor_reachability / source_page_citations /
  extraction_metadata / ask_retrieval_relevance / ask_lexical_hygiene /
  guide_lint_artifact test scripts ✓ · `run_eval.py --offline --all` ✓ ·
  `git diff --check` ✓. `smoke_release.py` requires a live server at
  `localhost:8000` (end-to-end Docker check) and was not run in the host-only
  environment — frontend-only changes, backend unchanged.

---

## Slice 27 — Persist guide_lint.json advisory artifact (DONE — committed on trunk as `0d73f24`).

- **Purpose:** close the correctness-visibility asymmetry where math verification
  is persisted as a per-job artifact (Slice 21) but the deterministic guide-lint
  core (Slice 19) was still only a test/CLI tool. This slice persists a per-job
  `guide_lint.json` advisory artifact; **no UI** (JobDetails surfacing is a later
  slice, mirroring Slice 22).
- **Pattern:** mirrors the Slice 21 `math_verification.json` contract exactly —
  advisory-only, **never** fails a job, **never** changes job status, **never**
  blocks the render, downloadable by exact artifact name, and **not** added to
  generic artifact lists / Exports / Library / JobDetails this slice.
- **Where lint runs:** `pipeline/run_markdown_job.py::run_raw_markdown_pipeline`,
  in the new helper `_write_guide_lint(job)`, called immediately after
  `_write_math_verification(job)` — i.e. after the sanitized `clean.md` is saved
  and `validation.json` is written, before the Chromium render. Both job entry
  paths (`run_llm_job` and the paste/markdown paths) flow through this shared
  pipeline, so the artifact is produced for every successfully-sanitized job.
- **Artifact shape (completed):**
  ```json
  {"version": 1, "kind": "guide_lint", "status": "completed",
   "source": "clean.md", "report": { …GuideLintReport.to_dict()… }}
  ```
  **Degraded (lint crash):**
  ```json
  {"version": 1, "kind": "guide_lint", "status": "skipped",
   "reason": "lint_error", "safe_message": "Guide lint could not be completed."}
  ```
- **expected_sections / available_source_pages — NOT passed (documented):**
  - `expected_sections`: the job manifest only stores canonical section-toggle
    keys (e.g. `key_concepts`), not the heading text the LLM actually emits, so
    feeding them to the heading matcher would yield unreliable / noisy
    `missing_section` findings. Wiring real expected headings is deferred.
  - `available_source_pages`: source page anchors are not reliably available at
    this point without invasive source-text plumbing (and are absent for paste /
    Markdown-upload jobs), so the optional page-citation check stays disabled to
    keep the slice non-invasive. Lint still runs all other rules + the existing
    Node/KaTeX render bridge (which itself degrades to an info finding when
    unavailable — it never crashes the helper).
- **Degrade-not-fail:** any exception from the lint core (or the read) is caught;
  a small `skipped` artifact is written instead, and **only the exception type
  name** is logged to stderr (`Guide lint skipped (X); job continues.`) — never
  the message/args, traceback, paths, or guide content. Writing the degraded
  artifact is itself wrapped so it can never raise.
- **Plumbing:** new `Job.guide_lint_json` property (`pipeline/job_manager.py`,
  `<job>/guide_lint.json`, sibling of `math_verification.json`); exact-name
  special-case in `api/server.py::_artifact_path` returning
  `(job.guide_lint_json, "application/json")` — kept OUT of `ARTIFACTS`, so it
  never appears in `_artifact_urls` / `_artifact_details` (no generic list row)
  and is reached only by the fixed filename `guide_lint.json` (no traversal).
- **Tests:** new `test_scripts/test_guide_lint_artifact.py` (26 host checks, +1
  route check that runs only in Docker where FastAPI is importable): completed
  shape, structural-findings recorded without failing the job, zero-findings
  total 0, lint-crash → safe `skipped` (no traceback / no exc message),
  secret-name + key-like value scan on both completed and skipped artifacts,
  `validation.json` + `math_verification.json` left byte-identical, guide_lint
  report shape/version, and (Docker-only) the download route resolving the exact
  name while staying out of `ARTIFACTS` / urls / details and still 404-ing a
  traversal name.
- **Untouched (verified):** no frontend/UI/JobDetails change; no generic artifact
  list / Exports ZIP inclusion; no `validation.json` / `math_verification.json` /
  `extraction_metadata.json` schema change; no prompt / provider / model change;
  no `/api/jobs/llm` request-field change; no OCR/extraction change; no
  Ask/retrieval/LanceDB/embeddings change; no PDF/Chromium render change; no
  generation gating/failing on lint.

---

## Slice 25B — Ask lexical retrieval hygiene (DONE — committed `ae44a85`, trunk HEAD).

- **Purpose:** improve the existing deterministic local-only lexical (tf-idf) Ask
  retrieval with cheap, explainable changes, then prove the effect against the
  Slice 25A baseline. No embeddings / LanceDB / vector search / reranker /
  cross-encoder / new ML dependency — lexical hygiene only.
- **Root cause (from 25A):** the index and query both tokenised with a bare
  `[a-z0-9]{2,}` lowercaser and **no stopword/plural hygiene**. Common function
  words ("the", "it", "on") flooded scoring (idf≈1 but high tf), so unrelated
  sections out-scored the right one on a paraphrased query.
- **Change — new shared module `pipeline/ask_lexical.py`:**
  - `lexical_terms(text)` → normalised term-frequency dict, used by **both** the
    index build and the query scorer so they can never drift apart.
  - `STOPWORDS` — small built-in English function-word set (articles, pronouns,
    auxiliaries, prepositions, conjunctions, common question/determiner words).
    Deliberately excludes domain vocabulary; tokens like `l2`, `f1`, `sigmoid`,
    `dropout` survive intact.
  - `normalize_token` — conservative **regular `+s` plural** folding only
    (single trailing `-s`, guarded against doubled `ss` and short tokens), so
    `example`/`examples` and `weight`/`weights` fold to the same stem. No `-es`
    rule (would break singular/plural symmetry) and **no verb-tense stemming**
    (`-ing`/`-ed`) — that risks mangling tokens like `string`/`based` for little
    gain.
- **Wiring:** `ask_context._term_freqs` and `ask_sessions._terms` now both
  delegate to `lexical_terms` (the old per-module `_TERM_RE` and the now-unused
  `Counter` import in `ask_sessions` were removed). Segmentation is unchanged;
  only stopword filtering + plural folding are new.
- **Index/cache compatibility:** the index *shape* is unchanged (still
  `terms` + `doc_freq`), but their *contents* are now normalised. `INDEX_VERSION`
  bumped `1 → 2` so any existing v1 cache is treated as stale by `_cache_valid`
  and **rebuilt automatically** on the next `prepare_context` — no user action,
  no manual cache deletion, and no chance of mixing old un-normalised index terms
  with new query terms. See `DECISIONS.md` → "Ask index version bump on lexical-
  hygiene change".
- **Baseline before → after (k=5, `test_ask_retrieval_relevance.py`):**
  - Blocking cases **unchanged**: `hit_rate@5 = 1.0`, `mrr = 0.9`, `missing = []`
    (4 keyword guide queries rank #1; the source-page query ranks #2).
  - Paraphrase **known-weakness** case ("model memorizes training data…"):
    **rank 5 → rank 1** on this fixture. Stopword removal killed the function-word
    noise so the residual content-word overlap (`model`, `new`) ranks the
    Overfitting section first.
- **Honest remaining weakness:** this is still *lexical overlap*, not semantics.
  The paraphrase improved only because it shares a couple of content words with
  the target; a paraphrase with **zero** shared content words would still miss.
  The case is therefore kept `known_weakness: true` (non-blocking) and embedding/
  semantic retrieval remains future work. The harness `retrieval`/`version`
  labels and the fixture `note` were updated to record this.
- **Tests:** new `test_scripts/test_ask_lexical_hygiene.py` (34 checks) locks in
  stopword filtering, plural folding, technical-token survival, the
  index==query tokeniser invariant, a clean `doc_freq`/chunk-terms (no stopword
  leak), the four blocking keyword cases staying #1, and the paraphrase reaching
  #1. Existing Ask tests (`test_ask_context_prepare` 28, `test_ask_context_inventory`
  11, `test_ask_local_chat` 45) still pass.
- **Scope guardrails (verified):** no UI/frontend change; no provider/model/
  local-server/LLM call; no LanceDB/embeddings/vector/reranker/cross-encoder/new
  ML dependency; no `/api/ask/*` or other route/field change; no Ask
  chat/session API behaviour change beyond retrieval ranking; no prompt change;
  no OCR/extraction change; no citation-directive change; no artifact-schema
  (`validation.json` / `math_verification.json` / `extraction_metadata.json`)
  change; no PDF/Chromium render-pipeline change. No secrets/tokens/paths
  exposed (fixture is synthetic ML study text; redaction helpers untouched).

---

## Slice 25A — Ask retrieval relevance harness + lexical baseline (DONE — uncommitted).

- **Purpose:** establish an offline, deterministic baseline of the *current*
  local-only lexical (tf-idf) Ask retrieval **before** any LanceDB / embeddings /
  reranking / context-compression work. Measurement only — no retrieval change.
- **Retrieval boundary used (real code, no server/model/provider/Docker):**
  - `pipeline/ask_context.py::prepare_context(...)` builds the deterministic
    chunk + lexical index from a job's `clean.md` (guide) + `extracted.txt`
    (source); `load_index(...)` reads it back.
  - `pipeline/ask_sessions.py::_score_chunks(...)` / `retrieve_chunks(...)` are
    the exact functions Ask uses at chat time to rank + budget-select chunks.
  - The harness writes the fixture into a **temp** job dir (`Job(id, root=tmp)`),
    never touching real `jobs/`, `library/`, or `config/`.
- **Harness:** `test_scripts/test_ask_retrieval_relevance.py` (offline, no keys,
  no LLM call). Fixtures under `test_scripts/fixtures/ask_retrieval/`:
  `guide.md` (4 topic sections), `source.txt` (4 `## Page N` source slides),
  `queries.json` (6 query→expected-target cases, one flagged `known_weakness`).
- **Metrics (JSON-serializable, deterministic):** per-case `rank`, `hit_at_k`,
  `reciprocal_rank`, and the budgeted public-retrieval result; aggregate
  `hit_rate_at_k`, `mrr`, and a `missing` list over blocking cases. Known-weakness
  cases are reported but **non-blocking**. Run with `--json` for the full report.
- **Baseline result (k=5):** `hit_rate@5 = 1.0`, `mrr = 0.9`, `missing = []` over
  the 5 blocking cases (4 keyword guide queries rank #1; the source-page query
  ranks #2). The paraphrase **known-weakness** case ("model memorizes training
  data…", with no shared keywords) is the honest weakness: the correct section
  drops to **rank 5** (reciprocal rank 0.2), behind three unrelated sections,
  because lexical scoring has no stopword removal or semantic match. Recorded
  as-is (not forced), motivating future embedding/semantic retrieval.
- **Scope guardrails (verified):** Ask runtime/chat/session/prompt behavior
  unchanged; no provider/model/local-server call; no LanceDB/embeddings/vector
  DB/reranking/new ML dependency; no frontend/UI; no `/api/ask/*` or
  `/api/jobs/llm` route/field change; no OCR/extraction, citation-directive, or
  artifact-schema (`validation.json` / `math_verification.json` /
  `extraction_metadata.json`) change; no PDF/Chromium render-pipeline change. No
  secrets/tokens/paths exposed (fixture is synthetic ML study text).

---

## Slice 24A — Persist per-page extraction metadata artifact (DONE — uncommitted).

- **Purpose:** persist lightweight per-page extraction metadata for uploaded PDF
  attachments as a per-job artifact, creating measurement/audit groundwork for
  later hybrid OCR work without changing extraction behavior.
- **Artifact:** `extraction_metadata.json` is written as a sibling job artifact
  only when PDF attachment metadata is available, with shape
  `{version: 1, kind: "extraction_metadata", status: "completed", sources: [...]}`.
  Each PDF source records `filename`, `content_type`, `page_count`, source
  `warnings`, and page records with `page`, `method`, `text_chars`,
  `word_count`, `has_page_anchor`, and `warnings`.
- **Skipped shape:** if metadata collection/writing cannot be completed safely,
  the helper writes `{version: 1, kind: "extraction_metadata", status: "skipped",
  reason: "metadata_unavailable", safe_message: ...}` on a best-effort basis.
  Failures never fail job creation, never change job status, and logs include
  only the exception type.
- **Collection point:** `pipeline/extract.py::_extract_pdf(...)` now records page
  metadata while it makes the existing embedded-text vs OCR decision. The text
  blocks, `## Page N` anchors, mode calculation, warnings, OCR availability
  checks, and page-selection behavior are otherwise unchanged.
- **Pipeline/API integration:** `pipeline/run_llm_job.py::_attach_sources(...)`
  writes PDF metadata after attachment extraction and before the LLM call.
  `pipeline/job_manager.py` adds `Job.extraction_metadata_json`.
  `api/server.py::_artifact_path(...)` exact-special-cases
  `extraction_metadata.json`, so it is downloadable at
  `GET /api/jobs/{id}/artifacts/extraction_metadata.json`.
- **Not listed:** `extraction_metadata.json` is intentionally not added to
  `ARTIFACTS`, export bundle selectors, `_artifact_urls(...)`, or
  `_artifact_details(...)`, so generic UI artifact lists / JobDetails remain
  unchanged in this slice.
- **Attachment coverage:** PDFs only. Non-PDF attachments are omitted from this
  artifact.
- **Tests:** added `test_scripts/test_extraction_metadata.py` for completed and
  skipped artifact shape, no secret-like leakage, no generic artifact-list
  exposure, and PDF attachment integration when PyMuPDF is available.
- **Scope guardrails:** no frontend/UI, prompt, provider, OCR heuristic,
  page-selection, `/api/jobs/llm` request-field, `validation.json`,
  `math_verification.json`, Ask/retrieval, VLM, or PDF/Chromium render-pipeline
  changes.

---

## Slice 23B — Source page-citation directive + checks (DONE — uncommitted).

- **Purpose:** add model-facing guidance that uses the Slice 23A proof: when
  source text contains extraction-style `## Page N` anchors, generated guides
  should cite source pages compactly and deterministically measurable offline.
- **Prompt change:** `pipeline/orchestrator.py` now defines
  `SOURCE_PAGE_CITATION_DIRECTIVE` and conditionally inserts it when
  `source_text` contains `## Page N` anchors. Exact directive:
  "When the source text contains '## Page N' anchors, cite the source page for
  factual claims, examples, formulas, and definitions where possible. Use compact
  citations like (p. 3) or (pp. 3-5), and cite only pages that appear as source
  anchors. Do not invent page citations."
- **Insertion point / invariants:** both `build_messages(...)` and
  `build_messages_for_preset(...)` insert the conditional citation block after
  axis/include-section guidance and before `MARKDOWN_MATH_SYSTEM`; preset system
  prompts still come first; `MARKDOWN_MATH_SYSTEM` remains the final block in
  both paths. With no page anchors and no other options, the default system
  prompt remains `MARKDOWN_MATH_SYSTEM`; the preset no-anchor baseline remains
  `{preset_prompt}\n\n{MARKDOWN_MATH_SYSTEM}`.
- **Format alignment:** the existing optional `slide_page_references` fragment was
  aligned from the older `(page N)` policy to compact `(p. N)` / `(pp. N-M)` so it
  does not conflict with the new source-driven directive.
- **Advisory checker:** `pipeline/guide_lint.py` now has optional
  `available_source_pages` support plus `extract_source_page_anchors(...)`. When
  offline tooling supplies pages, it detects conservative citations such as
  `p. 3`, `pp. 3-5`, `page 3`, and warns with `page_citation_range` if cited
  pages are unavailable or no anchors were supplied. It is advisory only and is
  not wired into live jobs, artifacts, UI, `validation.json`, or
  `math_verification.json`.
- **Eval wiring:** `test_scripts/eval/score_guide.py` accepts optional golden-spec
  `source_page_anchors` and passes them into the linter. The sample golden spec
  and fixtures now include `## Page 1` / `## Page 2` source anchors and valid
  compact citations so offline mode measures citation plausibility.
- **Tests added/updated:** new `test_scripts/test_source_page_citations.py`
  covers conditional directive insertion, no-anchor baselines, preset/non-preset
  consistency, and math-block-last ordering. Updated
  `test_scripts/test_page_anchor_reachability.py`,
  `test_scripts/test_page_reference_format.py`,
  `test_scripts/test_guide_lint.py`, and `test_scripts/test_eval_harness.py`.
- **Scope guardrails:** no frontend/UI, JobDetails, backend route, provider,
  provider setting, `/api/jobs/llm` request-field, OCR/extraction,
  retrieval/LanceDB/Ask, `validation.json`, `math_verification.json`,
  guide-lint job artifact, or render/PDF pipeline changes.

---

## Slice 23A — Verify source page-anchor reachability (DONE — uncommitted).

- **Purpose:** measurement/proof slice before citation behavior changes. Prove
  whether extraction-style source anchors such as `## Page N` survive the
  ingestion/input/prompt path and reach model-facing prompt assembly.
- **Inspected path:** `pipeline/extract.py` emits PDF anchors as `## Page N`;
  `pipeline/run_llm_job.py::_attach_sources(...)` copies/extracts attachments,
  appends extracted text under `## Attached Sources`, and passes the augmented
  source into `generate_study_guide(...)`; `pipeline/orchestrator.py` assembles
  model messages with `build_messages(...)` (template path) or
  `build_messages_for_preset(...)` (preset path); `pipeline/prompt_loader.py`
  injects `{source}` into the user template. The exact model-facing boundary is
  the `messages` list passed to `generate_chat_completion(messages, config)`.
- **Result:** PASS. `## Page 1`, `## Page 2`, etc. currently reach the
  model-facing `user` message. Template prompts preserve anchors inside the
  rendered source block; preset prompts use `source_text` as the user message
  verbatim; attachment-augmented source preserves anchors after `_attach_sources`.
- **Focused proof added:** `test_scripts/test_page_anchor_reachability.py` plus
  fixture `test_scripts/fixtures/page_anchor_reachability/extracted_pages.txt`.
  The test covers simple two-anchor source text, anchors surrounded by normal
  lecture text, attachment augmentation into prompt assembly, preset prompt
  assembly, and explicitly verifies no default citation directive/output citation
  assumption is introduced.
- **Behavior changes:** none. Tests/docs only. No citation directive change, no
  generated-guide instruction change, no citation lint/eval rule, no frontend/UI,
  provider, OCR, extraction, retrieval, `validation.json`, `math_verification.json`,
  or `/api/jobs/llm` request-field change.
- **Slice 23B implication:** citation/page-reference prompt, lint, and eval work
  can proceed from the premise that extraction-produced `## Page N` anchors are
  already available to the model input. Slice 23B still needs to add citation
  behavior explicitly; Slice 23A does not assume rendered output citations.

---

## Slice 22 — JobDetails math verification artifact UI (DONE — uncommitted).

- **Purpose:** add the first read-only JobDetails surface for the Slice 21
  per-job `math_verification.json` artifact without adding it to the generic
  artifact grid/list.
- **Scope guardrails:** frontend read-only UI only. No backend job behavior, no
  pipeline behavior, no prompt/provider changes, no `/api/jobs/llm` request-field
  changes, no `validation.json` schema change, no guide-lint integration, no
  artifact writes, no rerun button, and no raw HTML/`dangerouslySetInnerHTML`.
- **UI placement:** `JobDetailsDrawer` now has a `Verification` tab. Opening that
  tab mounts `MathVerificationPanel`, which fetches
  `GET /api/jobs/{id}/artifacts/math_verification.json` on demand. The existing
  `Artifacts` section remains unchanged and still does not list
  `math_verification.json`.
- **Frontend files:** `frontend/src/api/client.js` adds a bounded JSON artifact
  reader; `frontend/src/mathVerification.js` contains pure artifact
  classification/bounding helpers; `frontend/src/components/MathVerificationPanel.jsx`
  renders the read-only panel; `RecentJobsPanel.jsx` adds the tab mount;
  `design-system.css` adds compact semantic claim-row styles; `frontend/package.json`
  chains the new helper harness.
- **States handled:** completed artifacts show `report.summary` total / ok /
  mismatch / unparseable and a bounded, compact claim list prioritizing mismatch
  and unparseable claims; skipped artifacts show the safe skipped message; 404
  older jobs show "not available"; unexpected shapes and invalid JSON show
  malformed-artifact messaging; network/fetch failures show fetch-error
  messaging.
- **Validation:** `npm --prefix frontend run build` green; `npm --prefix frontend
  run test` green (now includes the math verification helper harness);
  `node frontend/scripts/verify-math-verification.mjs` green; `python -m
  compileall api pipeline test_scripts` green; `python
  test_scripts/test_math_verifier.py` → 74/74; `python
  test_scripts/test_guide_lint.py` → 64/64; `python
  test_scripts/test_eval_harness.py` → 59/59; `python
  test_scripts/eval/run_eval.py --offline --all` → 3 guides scored; `git diff
  --check` clean; `python test_scripts/smoke_release.py` → 29 passed / 0 failed
  / 0 skipped.

---

## Slice 20 — Eval harness Phase 1: deterministic scoring framework + golden specs (DONE — reviewed + committed).

- **Purpose:** third **correctness / measurement** slice. Build the first
  **deterministic evaluation harness** for guide quality — the *measurement spine*
  that lets us score guide outputs using the pure correctness modules from Slice 18
  (math verifier) and Slice 19 (guide lint) **before** we optimize prompts, OCR,
  retrieval, or styles. This slice **measures**, it does not improve generation.
- **Scope guardrails honored:** **no** generation-prompt change, **no** provider
  behavior change, **no** `/api/jobs/llm` request-field change, **no** Builder/
  JobDetails UI change, **no** job-artifact integration of math/lint, **no** writes
  to live `jobs/`/`library/`/`config/` (offline never touches the API; the optional
  live mode only POSTs to the existing no-provider `/api/jobs/paste`). **No**
  LLM-judge, **no** embeddings/LanceDB, **no** OCR/retrieval/citation changes. **No
  new dependency** — JSON specs (stdlib), reusing Slice 18/19 modules.
- **New area — `test_scripts/eval/`:**
  - `score_guide.py` — pure, importable scoring core. `build_result(spec,
    guide_text, *, guide_path, mode, artifacts, run_katex) -> dict` plus the
    per-metric scorers `score_concepts`, `score_must_not_claim`, `score_math`
    (reuses `pipeline.math_verifier.verify_math_claims`), `score_lint` (reuses
    `pipeline.guide_lint.lint_guide_markdown`, KaTeX **off** by default for fast
    offline runs), `score_artifacts`, and `compute_overall`. Spec validation via
    `validate_spec` / `SpecError`.
  - `run_eval.py` — CLI: `--offline` (required; no keys/Docker/LLM), `--all`
    (every golden spec × its `offline_guides`), `--live` (optional; submits the
    spec's `source_path` to `/api/jobs/paste`, fetches `clean.md`, scores it +
    probes artifact presence; times out cleanly, records only the API **host**,
    never the full URL). Writes a JSON result + appends `summary.csv`; **scans
    every result for credential-looking field names/values and blocks the write
    on a suspected secret**.
  - `golden/sample.json` + `golden/README.md`; `fixtures/` (`sample_source.md`,
    `sample_good_guide.md`, `sample_bad_math_guide.md`,
    `sample_bad_structure_guide.md`) + `fixtures/README.md`; `results/README.md`
    (generated `*.json`/`*.csv` git-ignored). Top-level `README.md`.
- **Spec format — JSON (not YAML):** stdlib-only, so offline scoring needs no
  extra dependency and runs identically on host and in the non-root Docker image
  (same dependency-free stance as Slice 18 declining SymPy). A `.yaml`/`.yml`
  loader is used only if PyYAML is importable; committed specs stay `.json`.
  Fields: `id` (required), `title`, `source_kind`, `source_path` (required for
  `--live`), `expected_sections`, `required_concepts`, `must_not_claim`,
  `known_numbers` (advisory/reserved this slice), `offline_guides`.
- **Scoring metrics (all `[0,1]`, higher better):** `concepts` = found/total by
  normalized substring match; `must_not_claim` = (total−violations)/total; `math`
  = `(ok + 0.75·unparseable)/total` (mismatches earn **no** credit, unparseable
  earns partial — never fails on unparseable, never on zero claims); `lint` =
  `clamp(1 − (0.20·errors + 0.05·warnings))` (info ignored); `artifacts` =
  present/expected (live only; `null`/not-applicable offline); `overall` =
  weighted mean (`.30/.25/.20/.15/.10`) **renormalized** over non-null components.
- **Regression comparison:** keyed on `(spec_id, mode, guide)` — a result is
  compared to the most recent prior result for *that same guide* (never a
  different guide that shares the spec), reporting previous/current overall, the
  delta, and per-metric deltas. **Non-blocking** this slice. Result filenames are
  guide-keyed (`<spec>__<mode>__<guide>__<run_id>.json`) with a collision counter.
- **Result shape:** `{version, run_id, mode, spec_id, spec_title, guide_path,
  scores{overall,concepts,math,lint,must_not_claim,artifacts}, details{
  missing_concepts, must_not_claim_violations, math_summary, lint_summary,
  lint_top_findings, artifacts}, regression?}`.
- **Tests / fixtures:** `test_scripts/test_eval_harness.py` (plain-Python
  assertion style) — **59/59 PASS**. Covers valid/invalid spec loading, concept
  matching + normalization, must-not-claim detection, math + lint integration on
  fixtures, scoring clean / bad-math / bad-structure guides + ordering, artifact
  scoring, overall renormalization, the JSON result shape, previous-run comparison
  (incl. different-guide isolation), the `--all` CLI, and the no-secret guarantee
  (clean result clean; planted `sk-…` value blocks the write; `api_key` field name
  caught).
- **Validation:** `npm --prefix frontend run build`; `npm --prefix frontend run
  test`; `python -m compileall api pipeline test_scripts`; `python
  test_scripts/test_math_verifier.py` → 74/74; `python test_scripts/test_guide_lint.py`
  → 64/64; `python test_scripts/test_eval_harness.py` → 59/59; `python
  test_scripts/eval/run_eval.py --offline --all` → 3 guides scored; `git diff
  --check` clean — **all green.** `python test_scripts/smoke_release.py` → 26
  passed / 2 failed / 0 skipped; the 2 failures (LLM attachment + outline flows)
  are **environmental, not a regression** — the host hit its thread/process limit
  so Chromium could not fork to render PDFs (`pthread_create: Resource temporarily
  unavailable (11)`; confirmed by a direct paste probe returning "PDF rendering
  failed: Chromium failed to render the PDF"). Slice 20 adds **zero**
  server/pipeline/frontend code, so it cannot affect `/api/jobs/llm` or PDF
  rendering. The optional live eval mode hit the same host PDF fork limit and
  failed cleanly through its graceful error path — exactly as designed.
- **Status:** **DONE — reviewed + committed.** Approval condition was one final
  smoke retry after freeing host resources; the environmental Chromium fork limit
  was traced to the app container's cgroup `PidsLimit=256` being saturated by
  ~179 zombie/`<defunct>` Chromium children (uid 10001) from earlier failed
  renders. Resolved by restarting the container (no runtime `jobs/`/`library/`/
  `config/` data deleted); smoke retried after the restart. Slice 20 adds **zero**
  server/pipeline/frontend code, so it cannot affect `/api/jobs/llm` or PDF
  rendering regardless of the smoke outcome.
  Next (separate, designed phase): eval Phase 2 may add an LLM-judge layer and/or
  a curated golden dataset, or we begin surfacing the verifier + linter as a
  job-stage advisory report — none of which start without their own slice.

---

## Slice 19 — Deterministic guide-lint core: pure advisory module + fixtures (DONE — reviewed + committed).

- **Purpose:** second **correctness / measurement** slice. Add a deterministic,
  **advisory-only** linter that scans generated guide Markdown for *structural and
  rendering-risk* issues, producing a JSON-serializable findings report. **Pure
  core only** — it never mutates input, never fails generation, and is wired into
  nothing.
- **Scope guardrails honored:** **no** frontend change, **no** API change, **no**
  job-pipeline integration, **no** artifact writing, **no** prompt change, **no**
  render/OCR/math-sanitizer rewrite. `pipeline/math_validator.py` (KaTeX render
  validation) is **reused, not modified**; `pipeline/math_verifier.py` (Slice 18)
  is **untouched**. No new dependency.
- **New file — `pipeline/guide_lint.py`:**
  - Public API: `lint_guide_markdown(markdown, *, source_name=None,
    expected_sections=None, run_katex=True) -> GuideLintReport`. Dataclasses
    `LintFinding` / `GuideLintReport` with `to_dict()` / `to_json()`; report shape
    = `{version, source_name, summary{total,error,warning,info}, findings[...]}`,
    each finding `{id, rule, severity, line, message, excerpt}`.
  - **Rules implemented:**
    1. `empty_heading` (warning) — heading with no body before the next heading;
       whitespace-only counts as empty; a parent heading whose body lives under a
       deeper child heading is **not** flagged; a heading is not flagged when it
       has a paragraph/list/table/math block/image/code block under it.
    2. broken-table family (warning, conservative — never `error`):
       `separator_without_header`, `header_separator_mismatch` (header vs separator
       column count), `malformed_separator` (header followed by an invalid
       separator-candidate row), `body_row_mismatch` (body row column count).
    3. `unbalanced_math` — unbalanced `$$…$$`/`\(…\)`/`\[…\]` (**error**) and
       unbalanced single `$` (**warning**, since it is ambiguous with unescaped
       currency). Escaped `\$` is ignored.
    4. `katex_render` (error) / `katex_skipped` (info) — **reuses** the existing
       Node/KaTeX bridge (`scripts/validate_math.js` via
       `pipeline.math_validator.validate`) by writing the Markdown to a transient
       temp file (never a job artifact) and reading the result. If Node/KaTeX is
       unavailable or the subprocess raises, it degrades to a single `katex_skipped`
       info finding — it never crashes linting and never changes math-validation
       behavior. Verified live: node + katex present → invalid `$\frac{1}$` yields
       a real `katex_render` error; valid math yields nothing.
    5. `missing_section` (warning) — when `expected_sections` is provided, each
       entry is matched against headings by normalized text (lowercase, punctuation
       → space, collapsed spaces) with equality or substring fallback (len ≥ 3).
       Order is **not** enforced this slice.
  - **Markdown safety:** fenced code blocks (``` / ~~~, marker-tracked) are excluded
    from heading/table/math checks; inline code spans are excluded from math checks;
    input is never mutated; no `dangerouslySetInnerHTML`, no HTML rendering.
  - **Bounds:** text ≤ 200k chars, ≤ 2000 findings, KaTeX subprocess timeout 30s,
    excerpts ≤ 160 chars.
  - **Optional CLI:** `python -m pipeline.guide_lint <file>` prints the JSON report
    (stdout only — no file writes).
- **Intentionally unsupported / deferred:** setext (underline) headings (ATX only),
  GFM cell-alignment correctness, escaped-pipe cell counting, table content/semantic
  checks, link/image-target validation, spelling/readability, and any
  job/`validation.json`/UI integration. All deferred to later designed slices.
- **Tests / fixtures:** `test_scripts/test_guide_lint.py` (plain-Python assertion
  style, run `python test_scripts/test_guide_lint.py`) — **64/64 PASS**. Covers a
  clean guide (0 findings), empty headings (same-level/whitespace/nested/parent +
  each body type), broken tables (each rule + valid table not flagged), math
  delimiters (balanced inline/display + unbalanced `$`/`$$`/`\(`/`\[`), fenced-code
  safety (broken table / unbalanced math / heading-like text inside a fence all
  ignored), expected sections (all-present / missing-one / normalization / `None`),
  KaTeX (valid passes, invalid → render finding or skip, disabled, no-crash), input
  immutability, non-string/empty input, and the JSON report shape. Five fixtures
  under `test_scripts/fixtures/guide_lint/` (`clean_guide.md`, `empty_headings.md`,
  `broken_tables.md`, `math_delimiters.md`, `code_safety.md`).
- **Validation (all green):** `npm --prefix frontend run build`; `npm --prefix
  frontend run test` (full maintained chain); `python -m compileall api pipeline`;
  `python test_scripts/test_math_verifier.py` → 74/74; `python
  test_scripts/test_guide_lint.py` → 64/64; `git diff --check` clean; `python
  test_scripts/smoke_release.py` → **28 passed / 0 failed / 0 skipped** (live app
  unchanged — guide-lint is not imported by the server).
- **Status:** **DONE — reviewed + committed** on `chrome-renderer-v1`. **Pure
  advisory guide-lint core only:** no job integration, no artifact, no API, no
  `validation.json`, no prompt, no frontend/UI. Next (separate, designed slice):
  the **eval-harness Phase 1** (deterministic scoring framework over the Slice 18
  verifier + Slice 19 linter), then decide whether/how to surface the verifier +
  linter (job-stage advisory report / `validation.json` / JobDetails) — generation
  must never fail on either.

---

## Slice 18 — Deterministic math verification core: pure module + fixtures (DONE — reviewed + committed).

- **Purpose:** first **correctness / measurement** slice after the reskin/hygiene
  phase. Add a deterministic, safe verifier that inspects generated guide
  Markdown/text and checks **simple numeric math claims** (`2 + 3 = 5`, `sqrt(16)
  = 4`, `exp(1.43) / (1 + exp(1.43)) ≈ 0.806`, …), producing a structured report
  with per-claim verdicts `ok` / `mismatch` / `unparseable`. **Pure core only.**
- **Scope guardrails honored:** **no** job-pipeline integration, **no** artifact
  writing, **no** `validation.json` change, **no** API routes, **no** frontend/UI/
  JobDetails change, **no** prompt change, **no** render/OCR/math-sanitizer rewrite.
  `pipeline/math_validator.py` (KaTeX render validation) is **untouched** — this is
  a deliberately separate concept (numeric correctness, not render syntax).
- **New file — `pipeline/math_verifier.py`:**
  - Public API: `verify_math_claims(text, *, source_name=None, tolerance_abs=1e-6,
    tolerance_rel=1e-3) -> MathVerificationReport`. Dataclasses `ClaimResult` /
    `MathVerificationReport` with `to_dict()` / `to_json()`; report shape =
    `{version, source_name, summary{total,ok,mismatch,unparseable}, claims[...]}`.
  - **Extraction (Tier A, line-based):** `expr <rel> number` where `rel` ∈
    `=`, `≈`, `~=`, `→`, `->` (normalized to exact `=` / approx `≈`); chained
    `a = b ≈ c` handled as adjacent pairs. Skips fenced code blocks (``` / ~~~)
    and inline code spans; unwraps `$…$`, `$$…$$`, `\(…\)`, `\[…\]`. A prose
    lead-in is trimmed to the trailing expression **only** when bounded by a
    non-word char, so `x + 2 = 5` stays `unparseable` (never a false `2`).
  - **Normalizer (deliberately limited):** unicode minus `−`→`-`; `×`,`·`,
    `\times`,`\cdot`→`*`; `÷`→`/`; `^`→`**`; `√(…)`/`\sqrt{…}`; `\frac{a}{b}`;
    `\left`/`\right` removal; thousands commas; `π`→`pi`; `e`/`exp`; constants
    `pi`/`e`/`tau`.
  - **Evaluation safety:** stdlib `ast` parse + explicit whitelist walk —
    **no `eval`/`exec`**, no attribute access, no names beyond whitelisted
    constants, no imports/FS/network/process. Allowed funcs: `sqrt, exp, log,
    ln, log10, log2, sin, cos, tan, abs`. Bounds: text ≤ 200k chars, line ≤ 2k,
    expr ≤ 200 chars / ≤ 100 tokens / ≤ 120 AST nodes, `**` exponent ≤ 100 /
    base ≤ 1e6, ≤ 5000 claims. Every verifier exception → `unparseable` (never
    `mismatch`); attribute/dunder/string payloads are rejected unexecuted.
  - **Tolerance:** `ok` if abs diff ≤ `1e-6` OR rel diff ≤ `1e-3`; approximate
    (`≈`) claims additionally allow one unit-in-last-place of the claimed literal
    (chained-rounding slack) — e.g. `0.8057 ≈ 0.806` and the logistic example are
    `ok`, while real near-misses (`1/3 ≈ 0.350`, `2 + 3 ≈ 5.4`) stay `mismatch`.
  - **Optional CLI:** `python -m pipeline.math_verifier <file>` prints the JSON
    report (stdout only — no file writes).
- **Dependency decision:** **none added.** SymPy *is* installed in the host env
  (1.14.0) but is **not** listed in `requirements.txt` and is **not used** — a
  stdlib `ast`+`math` evaluator is safer (explicit whitelist, no parser surprises,
  no hang risk) and keeps the backend dependency set unchanged.
- **Tests / fixtures:** `test_scripts/test_math_verifier.py` (plain-Python
  assertion style, run `python test_scripts/test_math_verifier.py`) — **74/74
  PASS**. Covers good claims, mismatches, unparseable (units/variables/symbolic/
  prose), Markdown safety (fenced + inline code, `$…$`/`\[…\]` wrappers),
  normalization, tolerance/rounding, chained claims, line numbers, safety guards
  (long expr rejected, unknown function rejected, malicious `__import__`/attribute/
  `open` payloads not executed → `unparseable`, pow-blowup + div-by-zero guarded),
  report JSON round-trip, and four fixtures under
  `test_scripts/fixtures/math_verifier/` (`good_claims.md`, `mismatch_claims.md`,
  `unparseable_claims.md`, `code_block.md`).
- **Validation (all green):** `npm --prefix frontend run build`; `npm --prefix
  frontend run test` (full maintained chain); `python -m compileall api pipeline`;
  `python test_scripts/test_math_verifier.py` → 74/74; `git diff --check` clean;
  `python test_scripts/smoke_release.py` → **28 passed / 0 failed / 0 skipped**
  (live app unchanged — verifier is not imported by the server).
- **Pure-core scope (reconfirmed at commit):** Slice 18 is **math-correctness core
  only** — **no** job-pipeline integration, **no** artifact writing, **no**
  `validation.json` field, **no** API route, **no** prompt change, and **no**
  frontend/UI/JobDetails surfacing. The verifier is not imported by `api/server.py`
  or any pipeline stage.
- **Status:** **DONE** — reviewed, approved, and committed.
  Next (separate, designed slice): decide whether/how to integrate the verifier
  (job-stage report / `validation.json` / JobDetails) — generation must never fail
  on it.

---

## Slice 17 — Hygiene checkpoint: dead-file sweep + test-chain repair (DONE — reviewed + committed).

- **Purpose:** hygiene checkpoint after committed Slice 16 (`eaa1263`) and Slice 15
  (`033e7d1`). **Not a feature slice** — no backend/API/pipeline/endpoint/payload
  changes, no render/OCR/math/prompt changes, no LMM/provider changes, no new deps.
  Carry out the dead-code sweep Slice 16 deferred and fix the stale `npm test` chain.
- **Working tree (what this slice changes):**
  - **Deleted (proven-unreachable dead files, via `git rm`):** mockup/legacy
    presentational set — `BrandMark.jsx`, `Chip.jsx`, `ClaudeIcons.jsx`,
    `DesktopMockup.jsx`, `FallbackImage.jsx`, `Field.jsx`, `GlowBackground.jsx`,
    `ImplementationNote.jsx`, `MobileScreenPicker.jsx`, `PasteGenerationPanel.jsx`,
    `PhoneMockup.jsx`, `StatCard.jsx`, `TopBar.jsx`, `data/mockups.js`; the five
    `public/mockups/*.png` assets; and the obsolete `scripts/verify-assets.mjs`
    harness. Zero live imports/usages confirmed before removal.
  - **`frontend/package.json`:** `npm test` was `node scripts/verify-assets.mjs`
    (stale mockup harness). Now chains the maintained harnesses:
    `verify-shortcut-{status,repair,activation,form}` +
    `verify-local-model-{status,command,library}` + `verify-ask-guide` +
    `verify-style-compare`. The old stale-test caveat is now obsolete.
  - **`frontend/src/App.jsx`:** comment updated to drop the stale `GlowBackground`
    mention (component deleted).
  - **`docs/PROJECT_DEEP_CONTEXT_REPORT.md`:** §6 component map + verify-harness
    list updated to remove `GlowBackground`/mockup/`verify-assets` references and
    record the Slice 17 deletions.
- **Validation (all green):** `npm run build`; full `npm test` chain (all 9
  harnesses pass) + the four explicitly-run `test:local-model-{status,command,
  library}` / `test:style-compare`; `python -m compileall api pipeline`;
  `git diff --check` clean. Container already healthy and serving the
  post-deletion build (deleted `/mockups/mobile-home.png` → **404**, SPA root →
  **200**); `smoke_release.py` **28 passed / 0 failed / 0 skipped** (incl. no-key-
  leakage on `/api/options`, `/api/styles`, JobDetails + full paste/upload/LLM/
  attachment/outline/ZIP/folder/style-CRUD/rerender flows).
- **Audit D (semantic CSS / inert utilities):**
  - **Undefined live `sg-*`: 0** — 743 `sg-*` tokens used in JSX, all defined among
    the 773 `.sg-*` selectors. (The dead `Tile`/`sg-tile-*` source from Slice 16's
    note is gone with `ClaudeIcons.jsx`.)
  - **Old-palette/inert Tailwind in live reachable files: only 2 occurrences**, both
    in `RecentJobsPanel.jsx` lines 348/362 (`text-slate-300`/`text-slate-400`) inside
    `PreviewPanel`, which renders **only** in the non-embedded `RecentJobsPanel`
    branch. The sole render site (`HomeShortcuts`) always passes `embedded`; the
    other importers (`Builder`/`Exports`/`Library`) pull only the named exports
    (`JobDetailsDrawer`/`StylePill`/`FolderPill`). So this branch is **unreachable
    dead code** — **intentionally left** (a hygiene slice avoids churning a
    known-dead branch; logged for a future structural pass), not a live leftover.
  - **Dead-file leftovers:** none — no live references to any deleted component.
- **Security quick-scan (no secrets printed):** `/api/options` & `/api/styles` —
  no raw keys (smoke also asserts this); `/api/provider-settings` — only safe DTO
  fields (`configured`, `key_source`, `key_hint` last-4, `base_url_host`), no raw
  key/full URL; `/api/local-model/status` — whitelisted fields only, no token/
  socket/Authorization/absolute host path/executable path/raw argv (the lone
  `.gguf` token is a bare model basename, the documented non-secret identifier).
- **Live walkthrough (functional, API-backed; visual review is operator-owned):**
  all 7 workspaces + Help + JobDetails reachable — Home (`/api/shortcuts`,`/api/jobs`
  200), Builder (`/api/options`,`/api/presets` 200; generation PASS), Library
  (`/api/library`,`/api/library/folders` 200; move/batch PASS), Ask Guide
  (`/api/ask/jobs` 200), Styles (`/api/styles` 200; style CRUD PASS), Models
  (`/api/provider-settings`,`/api/local-model/status` 200), Exports (`/api/exports`
  200; ZIP PASS), Help (static workspace wired in nav + Ask `onOpenHelp`),
  JobDetails (metadata + no-key-leakage PASS).
- **Status:** **DONE** — reviewed, approved, and committed.

---

## Slice 16 — Post-reskin release audit + checkpoint (implemented + verified, awaiting review).

- **Purpose:** release-audit/checkpoint after the GuideForge reskin + UX phase
  (Slices 1–15). **No features, no redesign, no roadmap work.** Verify the app is
  clean, document the reskin phase complete, and make only surgical low-risk
  fixes the audit turns up.
- **Audit A (baseline):** Slice 15 committed (`033e7d1`), working tree started
  clean.
- **Audit B (build/test):** `npm run build` green; `test:local-model-status`,
  `test:local-model-command`, `test:local-model-library`, `test:style-compare`
  all pass; `python -m compileall api pipeline` green; `git diff --check` clean.
- **Audit C (served app):** `docker compose build` + `up -d` green; `/api/health`
  `{"ok":true}`; `/api/options` 200 with only non-secret keys. `smoke_release.py`
  **28 passed / 0 failed / 0 skipped** (incl. the "no key leakage in job details"
  assertion + full paste/upload/LLM/attachment/outline/ZIP/folder/style-CRUD/
  rerender flows). Served container bundle confirmed **fresh** (the `sm:grid-cols-2`
  token removed in this slice is absent from the served JS), not stale host/dev
  output.
- **Audit D (semantic CSS / inert utilities):**
  - Defined `.sg-*` selectors: 773; `sg-*` tokens used: 745. **Undefined in the
    live render path: 0.** The only two unmatched tokens (`sg-tile-`,
    `sg-tile-glow`) come from the dynamic `Tile` export in `ClaudeIcons.jsx`,
    which is **dead** (zero imports/usages) — not in any live path.
  - **Live inert/old-palette leftovers found:** a handful in the JobDetails
    drawer body of `RecentJobsPanel.jsx` (stray `text-sm font-bold text-white`
    headers, `text-slate-*`/`mt-*`/`grid sm:grid-cols-2` on `h3/dt/dd/p/dl/section/
    span`). These were **inert no-ops, not raw UI** — the `.sg-drawer-body`
    base element cascade (Slice 5b/15) already styles `section/h3/dl/dt/dd/p` —
    but they were stripped anyway so the live path carries no leftover palette.
  - **Dead-file/dead-branch leftovers (left in place, reported):** the
    non-embedded `RecentJobsPanel` return branch + its `PreviewPanel` helper
    (lines ~311–393, `bg-navy-900`/`shadow-navy`/`backdrop-blur`/`ember-500`)
    are **unreachable** — the sole caller (`HomeShortcuts`) always passes
    `embedded`. Also dead: `Tile` (ClaudeIcons), `MetaRow` (BuilderWorkspace),
    and the mockup components (`DesktopMockup`, `PhoneMockup`, `BrandMark`,
    `GlowBackground`, `FallbackImage`, `ImplementationNote`, `MobileScreenPicker`,
    `PasteGenerationPanel`, `data/mockups.js`, etc.). Not churned (checkpoint
    slice avoids structural rewrites); recorded for a future dead-code sweep.
  - **Other live workspaces** (Ask/Builder/Home/Library/LocalModels/Styles/Help/
    DesktopDashboard): **zero genuine old-palette tokens.** Remaining matches are
    layout utilities (`flex`/`grid`/`gap-1`) on elements that also carry inline
    styles or `sg-*` classes, or render acceptably inline — cosmetically
    negligible, not raw. Deferred (not worth churn).
- **Audit E (functional):** end-to-end flows validated at the API/data layer via
  `smoke_release.py` (generation start→done, JobDetails metadata, library
  folder/move, Exports ZIP, Styles create/use/delete, rerender, outline order).
  Browser-driven visual walkthrough + screenshots are **operator-owned** (per
  standing instruction); not produced here.
- **Audit F (security):** `/api/options`, `/api/styles`, `/api/provider-settings`,
  `/api/local-model/status` carry **no raw keys/tokens/secrets**; provider DTO
  exposes only `configured`/`key_source`/last-4 `key_hint`/`base_url_host`;
  local-model DTO exposes no token/socket/abs-path/executable/argv/Authorization;
  served JS bundle contains no `.env` secret (and not even the last-4 hint).
- **Fixes made (1 file, frontend-only):** `frontend/src/components/RecentJobsPanel.jsx`
  — stripped inert Tailwind/old-palette className tokens off live drawer-body
  `h3/dt/dd/p/dl/section/span` elements (now styled solely by the existing
  `.sg-drawer-body` semantic cascade); the failed-job title span and `MetaTerm`
  values use small inline `var(--*)` styles matching the in-file pattern. **No
  CSS file change needed** (the semantic rules already existed). No behaviour,
  handlers, endpoints, payloads, tab ids, artifact links, drawer-open contract,
  or data surface changed.
- **Docs:** this entry + `NEXT_CHAT_HANDOFF.md` (reskin/UX phase complete through
  Slice 16; next phase = correctness/measurement, starting with deterministic
  math verification).
- **Status: implemented + verified, awaiting review before commit.**

---

## Slice 15 — RecentJobsPanel + JobDetails body reskin (DONE / committed).

- **Slice 15 closes the last Slice 11 reskin debt:** the JobDetails drawer
  **body/tab content** still rendered with inert Tailwind utilities (badges
  concatenating, tiles/cards with no surface, code/log blocks unstyled, notices
  uncoloured, oversized 24px lucide icons). **Frontend visual/CSS/markup only** —
  no backend/API/pipeline changes; every handler, endpoint, payload, tab id,
  artifact link, retry/rerender/section-regen/revert flow, and the
  `useImperativeHandle({ openJob })` drawer-opening contract are untouched.
- **Files changed (2, frontend-only):**
  `frontend/src/components/RecentJobsPanel.jsx` (markup/className swaps across the
  drawer body: Details, Quiz, Outline-compliance, Sections, Edit-Markdown,
  Version-History tabs + FailedJobPanel, AttachmentDetails, Validation/Render-log
  tiles, DiffView, QuizQuestionCard) and `frontend/src/design-system.css`
  (additive **"RecentJobs + JobDetails body — Slice 15"** block).
- **Scope A (Recent list):** the Home Recent/Favorite cards already used the
  semantic `Panel`/`ItemCard`/`ProviderPill` system (Slice 11/12) — left as-is.
  The dead non-embedded `PreviewPanel` branch was not churned.
- **Scope B/C (drawer body):** new semantic classes layered on the existing
  Slice 5b `.sg-drawer-body` element cascade — `.sg-tag(+tones)`,
  `.sg-tile/.sg-tile-value`, `.sg-pre`, `.sg-notice(+tones)`, `.sg-danger-card`,
  `.sg-card-row(+good/warn/bad)`, `.sg-stack`, `.sg-grid-2/3`, `.sg-head-row`,
  `.sg-chip-row`, `.sg-btn-row`, `.sg-btn-accent`, `.sg-opt-btn`, `.sg-idx`,
  `.sg-diff-*`, `.sg-q-opt`, `.sg-att-item`, plus a generic
  `.sg-drawer-body svg{16px}` default (Tailwind `h-x/w-x` are inert) and
  `.sg-drawer-body .sg-spin` so loaders actually spin. Reuses `.pill`,
  `.recent-state`, `.sg-form-sub`, `.sg-modal-action`, `.sg-tab-stack`,
  `.sg-art-*`, `.sg-row*` where they already fit.
- **Safety:** pure class/markup change — no new data surfaced; no secrets, keys,
  host paths, tokens, socket paths, raw argv, or hidden prompts exposed; no
  `dangerouslySetInnerHTML`/raw HTML; no new deps; no Tailwind utilities revived
  (no `.grid`/`.flex`-by-name rules). Larger Slice 5b density baseline kept.
- **Verification:** `npm run build` green; `python -m compileall api pipeline`
  green; `git diff --check` clean; `git diff` is **frontend-only (2 files)**;
  `docker compose up -d --build` green (healthy) and the **container-built served
  bundle** confirmed to contain the new CSS + JSX classes; `smoke_release.py`
  **28 passed / 0 failed / 0 skipped** (incl. no-key-leak assertions; provider LLM
  flows exercise untouched backend). Screenshots delegated to the operator; no
  automated screenshots.
- **Status: implemented + verified, awaiting review before commit.**

---

## Slice 14 — Styles "Compare styles" feature DONE.

- **Slice 14 adds a real Compare Styles feature to the Styles workspace.** This is
  the long-missing capability the "compare built-in prompts side by side" shortcut
  always described but nothing implemented. **Frontend-only** — no backend, API,
  pipeline, style CRUD, generation, or Builder-payload changes.
- **Data source:** the existing **`GET /api/styles/{id}`** detail endpoint already
  returns the full prompt `content` (it backs clone/edit) for both built-in and
  custom styles. The list `GET /api/styles` deliberately omits `content`, so the
  compare panel fetches each selected style's body **lazily on demand** and caches
  it. Verified live: detail returns `content` with **no** filename/path/secret/key
  leakage (built-in *and* custom).
- **Files changed:** `frontend/src/components/StylesWorkspace.jsx` (compare state +
  `ComparePanel`/`CompareColumn`/`Stat`/`FlagChip`, card selection wiring),
  `frontend/src/design-system.css` (additive "Compare styles — Slice 14" block),
  `frontend/package.json` (`test:style-compare` script). **New:**
  `frontend/src/styleCompare.js` (pure helpers: `toggleCompareSelection`,
  `stylePromptStats`, MIN/MAX) and `frontend/scripts/verify-style-compare.mjs`
  (node harness, 20 checks).
- **UX:** header **Compare styles** toggle (turns into **Exit compare**); in
  compare mode the cards become checkbox-selectable (selection is visually
  separate from **Use** — Use/Build/Edit/Delete still work via stopPropagation);
  2–4 styles allowed (locked out + dimmed at 4). The top **Compare panel** shows a
  `<2`-selected empty state ("Select at least two styles to compare."), Clear, and
  Exit; otherwise renders side-by-side columns (2 = balanced; 3–4 = horizontally
  scrollable grid, no body overflow). Each column shows name, built-in/custom
  badge, description, type, based-on, tags, deterministic stats (words/chars/
  headings) + math/quiz/concise flags, a scrollable monospace prompt block, and
  Use/Build (+Edit/Delete for custom). No LLM/semantic analysis; no
  `dangerouslySetInnerHTML`; compare state is local-only (never persisted).
- **Verification:** `npm run build` green; `npm run test:style-compare` 20/20;
  `python -m compileall api pipeline` green; `git diff --check` clean; docker
  `build`+`up` green (served bundle/CSS contain the compare markup + grid);
  `/api/styles/{id}` leak-scanned (built-in + custom) — none; `smoke_release.py`
  **28/28**. (`npm run test`/verify-assets is a pre-existing stale failure on
  unrelated `App.jsx` mockup checks — fails identically on clean HEAD.)
- **Visual inspection delegated to user; no automated screenshots required.**
- **Status: implemented + verified + visually reviewed — committed.**

---

## Slice 13 — Ask Guide workspace redesign DONE.

- **Slice 13 (Ask Guide workspace UX/layout redesign) is DONE.** Frontend
  UX/layout-only — no backend/API/pipeline changes; Ask endpoints, payloads,
  session ids, cache semantics, prepare-context behavior, citation parsing, and
  message response handling are untouched.
- **Files changed:** `frontend/src/components/AskGuideWorkspace.jsx`,
  `frontend/src/components/DesktopDashboard.jsx`,
  `frontend/src/components/HelpWorkspace.jsx` (new),
  `frontend/src/design-system.css` (additive "Ask Guide redesign — Slice 13" +
  Help block).
- **Redesign:** chat-first layout; a compact selected-guide / local-model /
  session **status bar** (model + green/red connection dot, selected guide,
  prepared status, chat count, with **Refresh chats** + **New chat** actions); a
  **collapsible guide selector** (collapses once a guide is selected, expands to a
  client-side title search + list); **collapsible right-rail details** (Chats,
  Context sources, Preparation, Local model, and conditional Latest answer
  context — the last three collapsed by default); and a new frontend-only **Help
  workspace** hosting the manual local-model / llama-server setup instructions
  (reuses `CommandHelper`), wired to the previously-dead Help nav row. Ask's
  Local-model card now links to Help instead of embedding the command block.
- **Preserved:** local-only Ask behavior (no cloud fallback / provider switching),
  session/cache semantics, prepare-context behavior, citation safety, retrieved
  metadata safety (metadata only — never chunk bodies), local-model gating,
  handlers, API calls, and payloads. `/no_think` is never surfaced; no secrets,
  host paths, argv, tokens, socket paths, or URLs are exposed; no new
  dependencies; no Tailwind utilities revived; larger Slice 5b density baseline
  kept.
- **Verification:** build green; local-model status/command/library harnesses
  green; `compileall` green; `git diff --check` clean; `docker compose build && up`
  green (container serves the new bundle — new Ask/Help markup + CSS confirmed in
  the served JS/CSS); `smoke_release.py` **28/28** (clean run — outline-order
  assertion passed).
- **Visual inspection delegated to user; no automated screenshots required.**

---

## Slice 12 — Home & Library UX polish DONE.

- **Slice 12 (Home + Library UX polish) is DONE.** Frontend visual/UX only — no
  backend routes, payloads, job/shortcut ids, or pipeline behavior changed.
- **Files changed:** `frontend/src/components/DesktopDashboard.jsx`,
  `frontend/src/components/HomeShortcuts.jsx`,
  `frontend/src/components/LibraryWorkspace.jsx`,
  `frontend/src/components/RecentJobsPanel.jsx`,
  `frontend/src/design-system.css`.
- **Original review blockers and the fixes applied:**
  - **Stale/capped favorites →** Home "Favorite Guides" now loads real favorites
    from the full `/api/library` (newest sort) instead of the capped recent-20
    `jobs` prop Home was previously handed; the obsolete `jobs` fetch/prop wiring
    in `DesktopDashboard` was removed. Favorites refresh on `jobsRefreshKey` so a
    favorite toggled elsewhere shows on return to Home.
  - **Quick Launch cards →** simplified to icon / title / type (+ status pill only
    when degraded/broken); dropped the pastel fills and the inline description.
    Cards now use the shared dark `glass` treatment and the **silver hover sheen
    no longer clips**.
  - **Provider badges →** every real badge uses the white circular treatment
    (`variant: "light"`) so all marks read as centred glyphs on matching white
    circles (no odd dark circle).
  - **Provider tooltip copy →** each real badge carries curated, non-sensitive
    hover copy (model name + strength + how GuideForge uses it); cluster stays
    `aria-hidden`.
  - **Ghost/empty badge removed →** the cluster now renders only real providers.
  - **Library favorites filter + Home deep-links →** added a **Favorites** filter
    chip and a **Title Z–A** sort to Library (search / filter / sort / folder /
    trash / selection / bulk behavior all preserved); Home "View all" links on the
    Favorite and Recent panels deep-link into Library via the existing
    `libraryView` nonce channel (`favorites` presets the new filter + reveals the
    filter bar; `recent` opens newest). Both panels are capped at 5 items on Home.
  - **Library folder rail →** ends naturally under the folder controls when short
    and grows only as needed.
- **Security preserved:** no keys/tokens/paths/secrets in the DOM; badge copy is
  static curated text, nothing dynamic or sensitive.
- **Live verification:** local browser pass confirmed (Quick Launch hover no
  longer clips, white provider circles, working favorites, Home→Library
  deep-links, favorites filter), no horizontal overflow at 1920/1440.
- **Verification:** build green; `compileall` green; `git diff --check` clean;
  `smoke_release.py` 28/28 (checked with the known unrelated LLM
  `outline use → followed in order` ordering flake only — clean on re-run).

---

## Slice 11 — Final QA / polish sweep (HomeShortcuts + ShortcutInspector) DONE.

- **Slice 11 (GuideForge UI reskin — final QA pass) is DONE.** Visual/CSS/markup
  only. No app logic, handlers, state, ids, endpoints, payloads, or render
  pipeline changed.
- **Audit-driven scope (Option 2):** fixed the two live raw surfaces that the
  Slices 1–10 reskin left behind — **HomeShortcuts** leftovers and a full reskin
  of the **ShortcutInspector** Inspect/Repair drawer. The large
  **RecentJobsPanel / JobDetails body** reskin was **deliberately deferred** to
  its own dedicated slice (it is ~2.1k lines and needs screenshot/live
  verification; the JobDetails drawer *shell* already has its baseline
  `sg-drawer-*` reskin).
- **Files changed:** `frontend/src/components/HomeShortcuts.jsx`,
  `frontend/src/components/ShortcutInspector.jsx`, and
  `frontend/src/design-system.css` (additive "Reskin QA — Slice 11" block).
- **HomeShortcuts fixes:** shortcut-row meta chips (type / status / saved-prompt)
  → real `.sg-tag*`; emoji tile sizing; **Degraded / Broken activation dialogs**
  now use a real centered overlay (`.sg-modal-scrim` + `.sg-dialog`) instead of
  inert `fixed inset-0` Tailwind that rendered them inline; Import-shortcuts
  panel (intro, mono textarea, preview/primary buttons, error box, preview item
  cards, rename field, footer) reskinned; `Field` + `SavedPromptControl`
  helpers; native `<option>` backgrounds via one scoped CSS rule (removed inert
  per-option Tailwind).
- **ShortcutInspector fixes:** full reskin of the right-side drawer reusing the
  `.sg-drawer-root/scrim/sheet` shell (z-index lifted so it sits above the
  Customize modal); status pills, finding cards, repair field controls,
  mode/section option rows, preview + diff, confirm step, and footer
  Preview/Apply/Close actions all use dedicated `.sg-insp-*` / `.sg-act`
  semantic classes. Repair/confirm/destructive semantics, disabled states, and
  the preview-before-apply gate are unchanged.
- **Class audit:** undefined `sg-*` classes in the live render tree = **0**
  (before and after; the only 3 unmatched — `sg-tile*` — live solely in the dead,
  never-imported `ClaudeIcons.jsx`). Inert-Tailwind/old-palette leftovers in
  live-rendered code reduced to RecentJobsPanel only (deferred); `MetaRow` in
  BuilderWorkspace is dead/unused and left as-is.
- **Security preserved:** the inspector still renders only redacted backend
  candidates; no keys/tokens/paths in the DOM.
- **Live verification:** container rebuilt (`docker compose build && up`) and
  confirmed serving the new dist; all five target surfaces visually verified at
  100% zoom (Home cards / Customize modal + Import panel / Inspector drawer above
  the modal / Degraded+Broken activation overlays), no horizontal overflow at
  1920/1440/1024.
- **Verification:** build green; local-model status/command/library harnesses
  green; `compileall` green; `git diff --check` clean; class audit clean;
  `smoke_release.py` **28/28** (an earlier run flaked only on the LLM
  `outline use → followed in order` ordering assertion; clean on re-run).

---

## Slice 10 — Exports workspace reskin DONE.

- **Slice 10 (GuideForge UI reskin — Exports workspace) is DONE.**
  Visual/layout-only.
- **Files changed:** `frontend/src/components/ExportsWorkspace.jsx` and
  `frontend/src/design-system.css`.
- **Preserved:** export list behavior, artifact download URLs, inline/download
  variants, ZIP bundle payload/manifest behavior, selection/filter/sort state,
  rerender action, `JobDetails` wiring, handlers, and API calls.
- **Verification:** build green, `compileall` green, `git diff --check` clean,
  live browser pass, artifact endpoints checked, ZIP bundle checked,
  `smoke_release.py` 28/28.

---

## Slice 9 — Models workspace reskin DONE.

- **Slice 9 (GuideForge UI reskin — Models workspace) is DONE.**
  Visual/layout-only.
- **Files changed:** `frontend/src/components/ProviderSettingsWorkspace.jsx`,
  `frontend/src/components/LocalModelsPanel.jsx`, and
  `frontend/src/design-system.css`.
- **Preserved:** provider settings behavior, write-only API key behavior,
  fetched-models review-only flow, Local Models status, command helper, model
  library, managed-server safety behavior, handlers, state, endpoint paths, and
  API payloads.
- **Security preserved:** no raw keys, full URLs, companion tokens, socket paths,
  absolute host paths, executable paths, or raw argv exposed.
- **Verification:** build green, local-model status/command/library harnesses
  green, `compileall` green, `git diff --check` clean, live browser pass,
  `smoke_release.py` 28/28.

---

## Slice 8 — Styles workspace reskin DONE.

- **Slice 8 (GuideForge UI reskin — Styles workspace) is DONE.**
  Visual/layout-only.
- **Files changed:** `frontend/src/components/StylesWorkspace.jsx` and
  `frontend/src/design-system.css`.
- **Preserved:** style CRUD, built-in/custom/generated style behavior, AI style
  generation behavior, form validation, handlers, state, and API calls.
- **Verification:** build green, `compileall` green, `git diff --check` clean,
  live browser pass, `smoke_release.py` 28/28.

---

## Slice 7 — Ask Guide workspace reskin DONE.

- **Slice 7 (GuideForge UI reskin — Ask Guide workspace) is DONE.**
  Visual/layout-only.
- **Files changed:** `frontend/src/components/AskGuideWorkspace.jsx` and
  `frontend/src/design-system.css` (additive "Ask Guide — Slice 7" block).
- **Preserved:** local-only Ask behavior, sessions, prepare-context behavior,
  citations, retrieved metadata safety (metadata-only, no chunk body),
  local-model status gating, handlers, and API calls/payloads.
- **Verification:** build green, `compileall` green, `git diff --check` clean,
  live browser pass, `smoke_release.py` 28/28.

---

## NEXT — LMM Phase 2G11 final hardening/regression DONE; Phase 2 paused.

- **Local Model Manager Phase 2G11 is DONE** on branch
  `lmm-phase2g11-final-hardening`.
- **Current safe LMM Phase 2 milestone is complete/paused.** The implemented
  Linux path remains: host companion, approved-root GGUF scanning,
  Unix-socket-only backend bridge, model-library UI, selected-model handoff,
  companion-managed server controls, real `llama-server` lifecycle hardening,
  safe real-profile metadata/typed controls, `.ini` preset import, configured
  real-profile E2E harness, runtime setup UX, and runtime-service/operator docs.
- **Final offline regression harness added:**
  `test_scripts/test_lmm_phase2_final_regression.py` validates runtime-service
  example files/placeholders, JSON/INI parsing through the companion preset
  loader, Compose/systemd template boundaries, backend/profile DTO redaction,
  CPU-safe/manual helper defaults, risky-only `gpu_layers=999` scope, no LMM
  Provider Settings writes, no Ask coupling, no direct frontend companion calls,
  no permanent production Compose companion mount/env, companion-config-only
  approved roots, no browser folder picker, and safe selected-model fields.
- **Validation facts preserved:** CPU-safe real validation passed with
  `/usr/bin/llama-server`, `LMM_REAL_MODEL_ROOT=/mnt/ai/llm-models`,
  `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`, `port=18080`, `ctx_size=4096`,
  `gpu_layers=0`, and `threads=8`. Full offload `gpu_layers=999` failed safely
  with CUDA OOM / `model_may_be_too_large` on the 26B model and is not a default.
- **Scope preserved:** tests/docs only; no production backend behavior change,
  no frontend UI change, no Ask change, no Provider Settings write, no permanent
  Docker Compose change, no installer/autostart behavior, no committed token,
  no token/socket/absolute host model path/executable path/raw argv exposure, no
  browser folder picker, no approve-root implementation, no model download
  manager, and no app-suggested settings.
- **Deferred after pause:** approve-root flow design and implementation,
  app-suggested settings/recommendations, Ollama/simple-local-model path,
  Windows/macOS packaging/support, and model downloads.
- **Recommended next slice:** pause LMM Phase 2 and move to another planned area;
  resume LMM only with a separately designed approve-root flow or packaging
  slice.

## Previous — LMM Phase 2G10 runtime-service/operator packaging docs DONE.

- **Local Model Manager Phase 2G10 is DONE** on branch
  `lmm-phase2g10-runtime-service-docs`.
- **Runtime service guide added:**
  `docs/LOCAL_MODEL_MANAGER_RUNTIME_SERVICE.md` documents Linux-first operator
  startup for the host companion, safe paths, token handling, manual companion
  health checks, temporary Docker override shape, systemd user-service template,
  E2E validation, troubleshooting, and the security checklist.
- **Safe templates added under `docs/examples/`:**
  `lmm-companion.config.example.json`,
  `lmm-companion.profiles.example.ini`,
  `lmm-companion.user.service.example`, and
  `docker-compose.lmm-companion.override.example.yml`.
- **Operational boundary preserved:** the socket directory is the only Docker
  mount shown; the token is a placeholder and server-side only; model roots are
  read by the host companion, not the Docker backend; and the examples avoid
  whole-home mounts, Docker socket, privileged mode, host PID namespace, host
  networking, and host-gateway TCP.
- **Validation basis documented:** Phase 2G8 CPU-safe E2E passed with
  `/usr/bin/llama-server`, `/mnt/ai/llm-models`,
  `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`, `port=18080`,
  `ctx_size=4096`, `gpu_layers=0`, and `threads=8`; full offload
  `gpu_layers=999` remains an advanced risky example only because it failed
  safely with CUDA OOM on the 26B model.
- **Scope preserved:** docs/templates only; no production backend behavior
  change, no frontend UI change, no Ask change, no Provider Settings write, no
  permanent Docker Compose change, no actual installer, no app-installed system
  service, no committed token, no model download manager, and no app-suggested
  settings.

## Previous — LMM Phase 2G9 approved-folder setup UX polish DONE.

- **Local Model Manager Phase 2G9 is DONE** on branch
  `lmm-phase2g9-runtime-setup-polish`.
- **Manual command helper presets changed:** the default profile is now
  CPU-safe (`-c 4096 -ngl 0 --threads 8`), with GPU balanced
  (`-c 4096 -ngl 20 --threads 8`) and low-memory
  (`-c 2048 -ngl 0 --threads 8`) presets. Full offload `-ngl 999` remains only
  as an advanced profile explicitly labeled risky / may OOM, and is not the
  default.
- **Setup UX clarified:** Local Models now explains that approved GGUF folders
  come from the host companion config, the browser app cannot safely browse the
  whole PC or pick host folders directly, operators must configure
  `approved_roots`, restart the companion, then scan, and manual server mode
  still works without the companion. A compact example/edit-me JSON config block
  uses placeholders only.
- **Stale selection copy clarified:** when the companion is unconfigured and a
  saved selected model exists, the UI says it is a saved selection from a
  previous validation/session and is not confirmed by a live scan. When the
  companion is configured but the model is absent from the current library, the
  UI says it is saved but not in the current scan and may need rescanning.
- **Safe root/status display:** companion/backend library payloads may now
  include path-free root summaries (`id`, `recursive`, `model_count`) and the UI
  displays them when available. Absolute root paths, socket paths, tokens, and
  raw argv are not exposed.
- **Managed Server setup copy clarified:** controls remain disabled when the
  companion/profile is unavailable, explain they only control the
  companion-managed process, do not stop manual servers, and do not change
  Provider Settings. No-profile copy points to companion config/preset files.
- **Validation basis:** Phase 2G5/2G8 CPU-safe validation passed with
  `gpu_layers=0`, `ctx_size=4096`, `threads=8`; full GPU/offload
  `gpu_layers=999` failed safely as CUDA OOM / `model_may_be_too_large` and is
  not a default.
- **Scope preserved:** no true browser folder picker, no companion config write
  endpoint, no frontend-provided host path accepted by backend/companion, no
  Provider Settings writes, no Ask changes, no permanent Docker Compose changes,
  no model download manager, no app-suggested settings, no browser storage, no
  token/socket/raw absolute path/raw argv exposure, no free-form flags UI, and
  no whole-PC scan.
- **Recommended next slice:** packaging/runtime-service docs and a guided
  operator startup flow for running the host companion reliably. A future
  approve-root flow still needs a separate host-companion design.

## Previous — LMM Phase 2G7 operator setup docs + safe preset import DONE.

## Previous — LMM Phase 2G5 real Linux llama-server validation/hardening DONE.

## Previous — LMM Phase 2G4 Local Models managed-server UI DONE.

## Previous — LMM Phase 2G3 backend process bridge DONE.

- **Local Model Manager Phase 2G3 — FastAPI backend bridge for companion server
  status/start/stop/restart is DONE** on branch
  `lmm-phase2g3-backend-process-bridge`.
- **Backend routes added only:** `GET /api/local-model/server/status`,
  `POST /api/local-model/server/start`, `POST /api/local-model/server/stop`, and
  `POST /api/local-model/server/restart`. They delegate to the companion's
  existing Unix-socket `/server/*` endpoints using server-side
  `LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`, and optional
  `LMM_COMPANION_TIMEOUT_SECONDS`.

## Previous — LMM Phase 2G2 companion HTTP process API DONE.

- **Local Model Manager Phase 2G2 — companion Unix-socket HTTP process-control
  endpoints is DONE** on branch `lmm-phase2g2-companion-process-api`.
- **Endpoints added on the host companion only:** `GET /server/status`,
  `POST /server/start`, `POST /server/stop`, and `POST /server/restart`. They use
  the existing companion token auth and Unix-socket `BaseHTTPRequestHandler`
  server.

## Previous — LMM Phase 2G1 companion process-control internals DONE.

- **Local Model Manager Phase 2G1 — companion process-control internals with
  fake/safe test executable only is DONE** on branch
  `lmm-phase2g1-companion-process-internals`.
- **Code added:** `tools/local_model_companion/profiles.py` defines typed,
  bounded launch profiles and the explicit `fake_test` profile constructor.
  `tools/local_model_companion/process_manager.py` defines
  `ManagedServerProcessManager`, `start_managed_server`,
  `stop_managed_server`, and `get_managed_server_status`.
- **Recommended next slice was:** Phase 2G2 companion HTTP server endpoints for
  process status/start/stop/restart, still no backend bridge or UI.

## Previous — LMM Phase 2F start/stop design review DONE.

- **Local Model Manager Phase 2F — start/stop design review is DONE** on branch
  `lmm-phase2f-start-stop-design`. This was a docs-only safety review for future
  Phase 2G companion-managed `llama-server` process control.
- **Design scope:** `docs/LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md` defines the
  future contract for companion `GET /server/status`, `POST /server/start`,
  `POST /server/stop`, and `POST /server/restart`; backend bridge routes
  `GET/POST /api/local-model/server/*`; and Local Models UI start/stop/restart
  behavior. Phase 2F added no code/routes/UI/Docker changes.
- **Boundary reaffirmed:** Docker FastAPI never directly starts, stops, restarts,
  signals, or inspects host processes; only the host companion may spawn
  `llama-server`; the companion may stop only a process it started and still
  tracks; no Docker socket, privileged container, host PID namespace, or direct
  Docker-to-host spawn.

## Previous — LMM Phase 2E selected library model handoff DONE.

- **Local Model Manager Phase 2E — selected library model handoff is DONE** on
  branch `lmm-phase2e-selected-model-handoff`. Added safe backend persistence for
  a chosen companion-library GGUF model without process control.
- **Backend endpoints added:** `GET /api/local-model/library/selection` returns
  `{ selected, future_launch_preview }`; `POST /api/local-model/library/selection`
  persists a selected model by `model_id` plus optional safe snapshot, preferring
  validation against the cached companion library when available; `DELETE
  /api/local-model/library/selection` clears only the app-side selection.
- **Safety scope preserved:** no Provider Settings write, no Ask change, no local
  provider base URL/model behavior change, no Docker change, no host-gateway TCP,
  no Docker socket, no privileged container, no host PID namespace, no
  `llama-server` process launch, no subprocess/shell execution, no start/stop/
  restart route or UI control, no browser localStorage/sessionStorage, no
  raw companion token/socket/Authorization/full URL exposure, and no absolute host
  model path exposure.

## Previous — LMM Phase 2D UI model-library picker DONE.

- **Local Model Manager Phase 2D — Local Models UI model-library picker is DONE**
  on branch `lmm-phase2d-model-library-ui`. Frontend/client/tests/docs only.
  Added a compact **Model Library** section to the existing Local Models panel.
  It fetches companion status from `GET /api/local-model/companion/status` and
  cached library data from `GET /api/local-model/library`, and adds **Scan
  approved folder(s)** wired to `POST /api/local-model/library/scan`.
- **Selection was frontend-only in Phase 2D:** clicking a discovered model only
  updated React component state for visual selection inside the panel. Phase 2E
  supersedes this with backend selection metadata while still avoiding Provider
  Settings writes and process control.

## Previous — LMM Phase 2C socket-mount validation harness ADDED.

- **Local Model Manager Phase 2C socket-mount validation — PASSED** on
  branch `lmm-phase2c-socket-mount-validation`. Added
  `test_scripts/validate_lmm_companion_socket_mount.py`, a manual live validation
  harness that proves the deployed Docker backend can reach a host companion
  through a mounted Unix domain socket and call the Phase 2C backend endpoints
  successfully.
- **Validation-only behavior:** the harness creates a temporary `/tmp`
  validation workspace, fake approved model root, fake `.gguf` files plus one
  non-GGUF file, explicit companion config, host companion process, and temporary
  Compose override. The override mounts only the temporary runtime directory into
  the app container and sets server-side `LMM_COMPANION_SOCKET`,
  `LMM_COMPANION_TOKEN`, and `LMM_COMPANION_TIMEOUT_SECONDS`. It is removed during
  cleanup and is not committed. The committed `docker-compose.yml` is unchanged.
- **Runtime checks covered by the harness:** wait for companion `GET /health` over
  the host Unix socket, bring the app service up with the temporary override, wait
  for `GET /api/health` on `http://127.0.0.1:8000`, then call
  `GET /api/local-model/companion/status`, `GET /api/local-model/library`,
  `POST /api/local-model/library/scan`, and `GET /api/local-model/library`. It
  asserts configured/reachable status, `scan` capability, safe empty pre-scan
  library, fake GGUF model discovery, non-GGUF exclusion, root-relative
  `relative_path`, and no backend response leak of the token, raw socket path, or
  temporary absolute host model path.
- **Safety scope preserved:** no frontend UI, no production Docker Compose change,
  no Provider Settings write, no Ask change, no local provider base-URL behavior
  change, no host-gateway TCP, no Docker socket, no privileged container, no host
  PID namespace, no `llama-server` launch, no start/stop/restart backend API, and
  no process-control/subprocess/shell addition outside the validation script's own
  orchestration. The harness explicitly checks that
  `POST /api/local-model/server/start`, `/stop`, and `/restart` are unavailable.
- **Validation command:** `python test_scripts/validate_lmm_companion_socket_mount.py`.
  This is manual/live only and should not be added to normal smoke release unless
  explicitly requested. It will fail clearly if Docker is unavailable, Compose
  cannot use service `app`, port `8000` cannot become healthy, or the socket mount
  cannot be reached from the container.
- **Validation result:** live Docker/socket validation passed 17/17. Endpoint
  summary: companion status was configured/reachable with `scan`; pre-scan library
  returned safe empty models; scan returned the two fake GGUF fixtures
  (`gemma-validation-Q4_K_M.gguf`, `nested/qwen-validation-Q8_0.GGUF`) and excluded
  `notes.txt`; post-scan cached library returned both models; process-control
  probes for `/server/start`, `/server/stop`, and `/server/restart` returned
  unavailable (`405 Method Not Allowed`). Redaction proof passed: backend responses
  contained no companion token, no raw host/container socket path, and no temporary
  absolute host model/runtime path. The app service was restored with the committed
  Compose file only and was healthy afterward.
- **Recommended next slice:** Phase 2D Local Models UI model-library picker using
  the existing read-only endpoints, still with no start/stop/process control.

## Previous — LMM Phase 2C backend companion bridge DONE.

- **Local Model Manager Phase 2C — read-only backend bridge to the host companion
  model library is DONE** on branch `lmm-phase2c-backend-companion-bridge`.
  Backend-only: added `pipeline/local_model_companion_client.py`, wired
  `api/server.py`, and added `test_scripts/test_local_model_companion_bridge.py`.
  New endpoints under the existing LMM namespace:
  `GET /api/local-model/companion/status`, `GET /api/local-model/library`, and
  `POST /api/local-model/library/scan`. They use server-side env only:
  `LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`, and optional
  `LMM_COMPANION_TIMEOUT_SECONDS`.
- **Phase 2C bridge behavior:** the backend uses a tiny stdlib Unix-socket HTTP
  client (`socket.AF_UNIX`) with `Authorization: Bearer <token>`, bounded timeout,
  and JSON response parsing. Missing socket/token means unconfigured. Missing,
  refused, timed-out, auth-failed, malformed, or unexpected companion responses
  return safe HTTP-200-style DTOs with normalized categories:
  `companion_config`, `companion_offline`, `companion_auth`,
  `companion_timeout`, or `companion_error`. The frontend never receives the raw
  token, raw socket path, Authorization header, traceback, or low-level socket
  detail.
- **Phase 2C library safety:** the bridge whitelists model fields only (`id`,
  `display_name`, `filename`, `relative_path`, `root_id`, `size_bytes`,
  `modified_at`, `family_hint`, `quant_hint`, `server_compatible`), drops
  unexpected companion fields, rejects absolute `relative_path` values, redacts
  absolute paths/URLs/auth-like text/tokens from strings and bounded warnings, and
  never scans host files directly from Docker. `GET /api/local-model/library`
  reads the companion's cached model list only; `POST /api/local-model/library/scan`
  delegates the explicit scan to the companion.
- **Phase 2C hard non-goals preserved:** no frontend UI, no Docker Compose change,
  no Provider Settings writes, no Ask changes, no local provider base-URL behavior
  change, no direct Docker host filesystem scan, no host-gateway TCP
  implementation, no start/stop/restart routes, no process control, no model
  launch, no shell execution, no subprocess usage in the bridge, and no new
  dependency.
- **Validation:** `python test_scripts/test_local_model_companion_bridge.py` passed
  14/14 checks (FastAPI route introspection skipped because FastAPI is not
  installed in host Python), covering unconfigured env, successful fake Unix-socket
  responses and Authorization header, model whitelisting/counting, auth failure,
  missing/refused socket, timeout, malformed/unexpected JSON, redaction, absolute
  path rejection, warning bounds, and no process-control route/source surface.
  Also passed: `python test_scripts/test_local_model_companion_scan.py` 21/21
  (with the known AF_UNIX bind runtime skip in this sandbox),
  `python test_scripts/test_local_model_status.py` 17/17,
  `python test_scripts/test_local_model_command_profile.py` 13/13,
  `python -m compileall api pipeline tools`, `npm --prefix frontend run
  test:local-model-status`, `npm --prefix frontend run test:local-model-command`,
  `npm --prefix frontend run build` (existing Vite large-chunk warning only),
  `git diff --check`, and `docker compose config >/tmp/compose-check.txt` exit 0.
- **Recommended next slice:** Phase 2D Local Models UI model-library picker using
  these read-only endpoints, still with no start/stop/process control. If runtime
  deployment confidence is preferred first, do a narrow Docker/socket-mount
  validation slice before UI; no Compose mount was added in Phase 2C.

## Previous — LMM Phase 2B approved-folder scanning companion DONE.

- **Local Model Manager Phase 2B — host companion approved-folder GGUF scanning
  prototype is DONE** on branch `lmm-phase2b-companion-scan`. Added isolated,
  stdlib-only companion code under `tools/local_model_companion/`:
  `config.py`, `model_library.py`, and `companion.py`. It loads an explicit JSON
  config, scans only configured user-approved roots for `.gguf` files, returns safe
  metadata with stable opaque ids derived from `root_id + normalized relative_path`,
  and keeps absolute host paths out of model records. Config path is explicit via
  `--config` or `LMM_COMPANION_CONFIG`; there is no default home scan, no implicit
  `~/models`, and no silent root creation. Missing config returns a safe
  `no_approved_roots` warning and no models.
- **Phase 2B Unix socket status:** implemented a minimal Unix-domain-socket HTTP
  companion API in `tools/local_model_companion/companion.py`: `GET /health`,
  `GET /models` (cached only), and `POST /models/scan` (explicit scan). Every
  endpoint requires `Authorization: Bearer <token>`; token comes from
  `LMM_COMPANION_TOKEN` or the explicit local companion config and is never
  returned. The current execution sandbox denies AF_UNIX bind with
  `PermissionError: [Errno 1] Operation not permitted`, so the focused test verifies
  the socket server implementation shape and reports the runtime bind as skipped by
  sandbox.
- **Implemented scan safety:** approved-root canonicalization, candidate
  canonicalization, `.gguf` case-insensitive match, symlink resolution with
  inside-root enforcement, symlink escapes rejected, symlinked directories skipped
  to avoid loops, optional recursion, max files inspected, max models returned,
  elapsed-time guard, bounded warnings, missing-root/broken-symlink/path errors as
  warnings, root-relative paths only in records, best-effort family/quant hints, and
  no absolute host paths in model records.
- **Hard non-goals preserved:** no backend bridge endpoints, no frontend UI, no
  Docker Compose changes, no Provider Settings changes, no Ask changes, no new
  frontend dependency, no model execution, no whole-PC scan, no default home scan,
  no arbitrary path search from Docker, no arbitrary shell commands, no
  `llama-server` start/stop/restart, no process control, no subprocess usage in the
  companion package.
- **Focused validation:** `python test_scripts/test_local_model_companion_scan.py`
  passed 21/21 checks, including no-config/no-roots, missing root warning, simple
  GGUF metadata, non-GGUF ignore, recursive scan, symlink inside accepted, symlink
  escape rejected, traversal guard, broken symlink warning, max models, bounded
  warnings, config shape, socket implementation shape, source inspection for no
  process control/shell/subprocess, stable ids, hints, and no absolute host paths in
  model records. Continue to run `python -m compileall api pipeline tools` and
  `git diff --check` before closing the slice if not already run.
- **Recommended next slice:** Phase 2C should add a read-only Docker backend bridge
  that talks to the mounted Unix socket for companion health/status and model
  library/scan, with server-side token/socket config only and no frontend token or
  socket exposure. Keep start/stop/restart deferred.

## Previous — LMM Phase 2A host companion design DONE.

- **Local Model Manager Phase 2A — host companion + approved GGUF model library
  DESIGN is DONE** — branch `lmm-phase2-host-companion-design`, docs-only. New
  design doc: `docs/LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md`. It keeps Phase 1 as
  complete/validated and defines the future Phase 2 boundary: React UI →
  Docker FastAPI backend → Unix-socket-first, token-authenticated host companion →
  approved model directory scan → host `llama-server` process lifecycle. The
  Docker backend must not directly browse the host filesystem or start/stop host
  processes; direct Docker-to-host spawn remains permanently rejected. Model
  scanning is limited to explicit user-approved roots, never whole-PC or default
  home-directory scanning. The companion owns host filesystem/process access and
  exposes only a narrow local API with whitelisted command profiles, typed safe
  parameters, bounded/redacted logs, and stop behavior limited to processes it
  started and tracks.
- **Phase 2A transport correction:** for the current Linux Docker deployment,
  Phase 2B should assume a Unix domain socket mounted into the backend container.
  A companion bound only to host `127.0.0.1` is not assumed reachable from Docker;
  loopback-only TCP is valid only for host-network/native packaging, and
  host-gateway TCP requires explicit operator sign-off, firewall restriction to
  Docker bridge subnets, and token auth. `llama-server` may still bind
  `--host 0.0.0.0` for the model `/v1` API so Docker can reach it; that is
  separate from the companion control API, which must never be public.
- **Phase 2A non-goals were preserved:** no code, no companion implementation, no
  backend endpoints, no frontend UI, no Docker changes, no process spawn, no
  model scanning implementation, no provider settings behavior change, no Ask
  behavior change, no uploads, and no new dependency.
- **Recommended next LMM slice only if the operator chooses to proceed:** Phase
  2B companion prototype for approved-folder GGUF scanning only, using the chosen
  transport contract, with no start/stop yet. Do not implement start/stop before
  the companion design and security boundary are accepted.

## Previous — Ask local direct-answer guard DONE; NEXT = explicit extra-uploads slice or broader manual Ask polish. (LMM Phase 1 COMPLETE + VALIDATED below.)

- **Ask Your Guide — local direct-answer guard is DONE** — branch
  `ask-local-direct-answer-guard`. Manual local llama-server testing with
  `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf` showed thinking-style responses could spend
  the whole budget in `reasoning_content` and return empty visible assistant content.
  The first system-rule-only guard failed in the full Ask prompt; direct tests showed
  `/no_think` in the model-facing user message produces visible content.
  `pipeline/ask_sessions.py` now keeps the concise visible-answer system rules and
  adds a standalone `/no_think` local thinking-model control immediately before the
  final `User question:` block sent to `generate_chat_completion`. The marker is
  model-only: it is not stored in `history.jsonl`, returned by session load/list
  responses, included in session summaries, or rendered by the frontend.
  Citation/grounding rules are preserved. Validated: `python
  test_scripts/test_ask_local_chat.py` passed 45/45 pure checks with endpoint skip
  because FastAPI is unavailable in this environment; `python
  test_scripts/test_ask_context_inventory.py` passed 11/11 with the same endpoint
  skip; `python test_scripts/test_ask_context_prepare.py` passed 28/28 with the same
  endpoint skip; `python -m compileall api pipeline` passed; `npm --prefix frontend
  run test:ask-guide` passed; `npm --prefix frontend run build` passed with the
  existing Vite large-chunk warning; `python test_scripts/smoke_release.py` passed
  28/28; `docker compose config >/tmp/compose-check.txt` exited 0. Local-only
  behavior is unchanged: no hosted fallback, provider-settings writes, local model
  process control, uploads, streaming, retrieval changes, citation-validation
  changes, or reasoning_content exposure.
- **Ask Your Guide — empty local-model response guard is DONE** — branch
  `ask-empty-response-guard`, see DONE #59 below. During manual Ask UI validation
  after the math/source polish slice, a browser Ask message returned
  `POST /api/ask/sessions/{session_id}/message` → 500 because
  `generate_chat_completion` raised `RuntimeError("LLM returned an empty response.")`
  and Ask did not catch it. `pipeline/ask_sessions.py` now catches that narrow empty
  local-model RuntimeError and returns a safe structured `provider_error` response
  with `error.category: provider_empty_response` plus a retryable user-safe message.
  The failed turn does not append a successful user/assistant message to history.
  Local-only behavior is unchanged, and no retrieval, prompt assembly, model fallback,
  citation validation, session management, clear/delete, provider settings,
  streaming, uploads, rolling summary, multimodal, or process-control behavior
  changed. Focused coverage was added in `test_scripts/test_ask_local_chat.py`;
  validations are listed in DONE #59. The original empty local-model behavior was
  not reproducible after the Docker app was rebuilt/restarted and healthy, but the
  simulated regression is now covered.
- **Ask Your Guide — chat math/source visual polish is DONE** — branch
  `ask-chat-math-source-polish`, see DONE #58 below. Frontend-only Ask chat
  readability polish in `frontend/src/askGuide.js`,
  `frontend/src/components/AskGuideWorkspace.jsx`, and
  `frontend/scripts/verify-ask-guide.mjs`. Added inert math-aware answer parsing for
  `$$...$$`, `\[...\]`, `\(...\)`, and escaped-dollar inline math; display math
  renders as readable monospace blocks preserving line breaks; inline math renders as
  small monospace chips. No `dangerouslySetInnerHTML`, no markdown dependency, no
  KaTeX/MathJax, and no new dependency. Trusted backend-used citations now appear in
  a clearer **Sources used** section; unsupported citations remain warning-only and
  are not trusted chips. Retrieved chunk metadata stays collapsed and shows cleaner
  label/type/page/score/token rows; chunk text is still never rendered. Local-only
  Ask behavior and session management are unchanged.
- **NEXT — conservative choices only.** Do not start extra uploads automatically.
  Recommended next is either (1) broader/manual Ask UI polish only if another
  concrete issue surfaces, or (2) Ask Your Guide extra session uploads as a separate
  explicit slice if the operator chooses to continue Ask features. Keep streaming,
  hosted/cloud Ask, rolling summary, multimodal, and process control deferred.
- **Ask Your Guide — session management UI/API is DONE** — branch
  `ask-session-management`, see DONE #57 below. Added safe session listing,
  switching, new chat, clear-history, and delete-session behavior. Backend routes:
  `GET /api/ask/jobs/{job_id}/sessions`,
  `DELETE /api/ask/sessions/{session_id}/history`, and
  `DELETE /api/ask/sessions/{session_id}`. Clear keeps the session id and prepared
  context cache; delete removes only the fenced session directory. The Ask workspace
  now has a compact Chat sessions rail panel plus active-session clear/delete
  controls, preserves lazy session creation on first send, and keeps explicit prepare
  + local-only chat behavior unchanged. No extra uploads, no export, no streaming,
  no cloud/DeepSeek/Qwen fallback, no process control, no provider settings writes,
  and no new dependencies.
- **Ask Your Guide — chat polish + emitted-citation validation is DONE** — branch
  `ask-chat-polish-citations`, see DONE #56 below. The local-only Ask message
  endpoint now validates bracket-style model citations against the turn's retrieved
  citation labels, strips unsupported Ask-looking citations from the returned/stored
  answer, and returns `citations_allowed`, `citations_used`,
  `citations_unsupported`, plus `citation_validation{ok, unsupported_count}`.
  Normal bracketed prose that does not look like an Ask citation is left alone. The
  prompt now asks for fewer, clearer citations at paragraph ends or a short sources
  line without weakening grounding. The Ask UI renders safe answer blocks for
  headings/bold/lists without `dangerouslySetInnerHTML`, fixes the
  `Guide only · [object Object]` metadata bug, hides full technical session ids,
  shows trusted citation chips from backend-used citations, warns on unsupported
  citations, and keeps retrieved chunk metadata collapsed by default. No chunk text,
  raw prompts, keys, full URLs, provider settings writes, cloud fallback, streaming,
  extra uploads, process control, or new dependencies.
- **Ask Your Guide — frontend chat UI wiring is DONE** — branch
  `ask-chat-ui`, see DONE #55 below. The existing Ask workspace now creates chat
  sessions lazily on first send, loads the session with `GET /api/ask/sessions/{id}`,
  posts non-streaming messages to the backend local chat endpoint, renders bounded
  history, answer text, backend-returned citation chips, safe retrieved citation
  metadata, and safe local-model info. Chat stays gated on selected guide + ready
  context + explicit prepare + reachable local model + no in-flight send. Local
  offline/unconfigured keeps the composer disabled and shows the existing command
  helper. No localStorage/sessionStorage persistence, no raw HTML rendering, no
  chunk/source/guide text rendering, no process control, no provider writes, no extra
  uploads, no exports, no streaming, and no cloud fallback.
- **Ask Your Guide — backend local chat API is DONE** — branch
  `ask-local-chat-api`, see DONE #54 below. Backend-only session creation/load +
  non-streaming local-only message endpoint now exist:
  `POST /api/ask/jobs/{id}/sessions`, `GET /api/ask/sessions/{session_id}`, and
  `POST /api/ask/sessions/{session_id}/message`. The message path status-gates on
  LMM/local provider availability, prepares or reuses the Slice 3 lexical index,
  retrieves a bounded top-K chunk set, assembles citation-labelled prompt context +
  recent history, and calls only the existing `local` OpenAI-compatible provider.
  Offline/unconfigured local returns a structured safe response with **no model call**.
  Sessions live under `jobs/<job_id>/ask/sessions/<session_id>/`; original artifacts
  are untouched. **No frontend/UI changes, no extra uploads, no cloud fallback, no
  DeepSeek/Qwen fallback, no streaming, no rolling summary, no generation jobs, no
  new dependency.**
- **Ask Your Guide — Slice 3 is DONE (backend context preparation / chunking)** —
  branch `ask-context-prepare`, see DONE #52 below. New stdlib-only helper
  `pipeline/ask_context.py` chunks `clean.md` (guide) + optional `extracted.txt`
  (source) deterministically on heading / `## Page N` boundaries (~650-token target,
  ~800 ceiling, `chars/4`, no overlap), preserving each chunk's **citation label**
  (nearest guide heading / `Page N`) and building a dependency-free lexical index
  (per-chunk term frequencies + `doc_freq`). `POST /api/ask/jobs/{id}/prepare` builds
  or reuses a cache at `jobs/<id>/ask/cache/context_index.json`, keyed by a content
  hash over guide+source bytes: **idempotent** (`hit` rewrites nothing; content change
  → `rebuilt`; corrupt/stale → safe rebuild), **atomic** writes, **fenced** to the job
  dir. Unknown job → 404; guide-less existing job → 200 `ready:false`. Response is an
  explicit whitelist (counts + bounded citation summary + job-relative cache path) —
  **no guide/source body, chunk text, key, URL, or host path.** **No chat, no retrieval
  endpoint, no model/local-model call, no sessions, no extra uploads, no UI, no new
  dependency; original artifacts untouched (no `save_clean_md`, no manifest write).**
- **Ask Your Guide — Slice 2 is DONE (backend context inventory endpoint)** —
  branch `ask-context-inventory`, see DONE #51 below. Two **read-only** endpoints over
  generated-guide artifacts: `GET /api/ask/jobs` lists **only Ask-eligible jobs** (those
  with a generated `clean.md`; guide-less / failed / incomplete jobs are filtered out)
  with curated, redacted picker fields (id/title/status/created+updated/style/preset/
  provider/model/favorite/attachment_summary/guide+source availability); `GET
  /api/ask/jobs/{id}/context` returns a per-job **readiness + source inventory**
  (guide `clean_md` present + char + heading counts; source `extracted.txt` present +
  char + `## Page N` anchor count; redacted attachment names/modes/extracted_chars/
  warnings; page selections; a `readiness{status,ready,reasons}` object). Thin read-only
  reader `pipeline/ask_inventory.py` (counts only — never a guide/source **body**);
  routes reuse the existing `_safe_manifest`/`_safe_attachment_metadata`/
  `_attachment_summary`/`_safe_page_selections` redaction and emit an explicit field
  whitelist, so **no raw key / full base URL / filesystem path / artifact body** can ride
  along. **No chat, no chunking, no retrieval/indexing, no model call, no session storage,
  no UI; original job artifacts untouched (no `save_clean_md`, no manifest write).**
- **Ask Your Guide — Slice 1 design is DONE (docs-only)** — branch
  `ask-your-guide-design`, on `docs/ASK_YOUR_GUIDE_DESIGN.md`, see DONE #50 below.
  A dedicated **`AskGuideWorkspace`** (first-class page/tab) where the user selects a
  generated guide/job and chats with it using a **local model only** (status-gated on
  LMM Phase 1; no DeepSeek/Qwen/cloud fallback). Mandatory **context manager +
  budgeted retrieval** (chunk `clean.md`/`extracted.txt` with `## Page N`/heading
  citation anchors, dependency-free lexical index cached per `(job_id, content_hash)`,
  reserve answer/system-rules/recent-chat, rolling chat summary). Hard
  **accuracy/citation contract** (answer from material first, cite page/section, say
  so when not covered, never invent). Conservative session-scoped storage (never
  auto-exported, no secrets). 8 proposed endpoints, all local-only + read-only over
  job artifacts. **No code changed.**
- **LMM Phase 1 is COMPLETE and VALIDATED.** Slices 1→4 (design → detection-only
  status endpoint → status panel → command helper) are on trunk (`94003bc`,
  `e27c674`, `7429f24`, `e399f09`), and the **Slice 5 validation + docs-reconciliation
  pass PASSED** — see DONE #49 below and
  `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`. All static, Docker, smoke,
  live-API, no-process-execution, and secret-leak checks pass; **no code changed.**
- **LMM Slice 4 is DONE (command-helper profiles / Copy start command)** — branch
  `local-model-command-helper`, on trunk `e399f09`, see DONE #48 below. Read-only
  `GET /api/local-model/command-profile` (`get_local_model_command_profiles()`)
  serves static, whitelisted `llama-server` start commands (default GPU + CPU-only
  profiles) with a `/path/to/model.gguf` **placeholder**, `--host 0.0.0.0 --port
  8080`, and safety warnings. The Local Models panel renders a first-class **Copy
  command** block (profile chips, selectable code block, clipboard + manual
  fallback), prominent when offline and collapsed when reachable. **Command helper
  only — the app never executes it; no spawn/start/stop, no GGUF scan, no host
  companion.** Pure `localModelCommand.js` helpers; backend + frontend harnesses
  green; no provider-write or status-DTO behavior change.
- **NEXT — Ask Your Guide local-only chat (recommended), OR host-companion DESIGN
  (optional, sign-off-gated).** Phase 1 is feature-complete + validated, so the next
  major choices are: (1) **Ask Your Guide** local-only chat — consumes LMM status,
  no process control — recommended; (2) **host companion DESIGN** (LMM Slice 5,
  Option B) only if the user wants app-managed start/stop later; (3) Math/PDF
  font-size rationalization; (4) Large-PDF preflight size-limit polish. **Still
  deferred (do not begin without an explicit slice):** no host process control, no
  start/stop, no GGUF browsing, no host companion implementation, no Ask Your Guide
  chat yet. See `LOCAL_MODEL_MANAGER_DESIGN.md` §11.
- **LMM Slice 3 is DONE (Local Models status panel, FRONTEND)** — branch
  `local-model-status-ui`, see DONE #47 below. Consumes the Slice 2 endpoints
  (`getLocalModelStatus`/`checkLocalModelStatus` API helpers) and renders a
  read-only **Local Models** panel inside the Providers page: live status pill
  (reachable green / offline amber / not-configured grey / error red), host-only
  base URL, in-Docker flag, latency, model count + bounded model chips,
  default/selected model, redacted offline message + first-class troubleshooting
  (with the `--host 0.0.0.0` gotcha), backend `notes`, a **Refresh status** button
  (calls `/check`, never saves/starts anything), an "Edit local provider settings"
  link that scrolls to the Local provider card (single writer), and the disabled
  **Copy start command — Planned** affordance. Pure `localModelStatus.js` helpers
  unit-tested by `verify-local-model-status.mjs` (47/47). **No process control, no
  inline base-URL editing, no raw key/URL.**
- **LMM Slice 2 is DONE (detection-only backend status endpoint)** — branch
  `local-model-status-api`, DONE #46. Read-only `GET /api/local-model/status`
  (+ thin `POST /api/local-model/check` alias), `get_local_model_status()`.
- **LMM Slice 1 design is DONE** (DONE #45) — `docs/LOCAL_MODEL_MANAGER_DESIGN.md`:
  detection-first, Option D (Docker→host spawn) REJECTED, Option C not the default.
- **LMM Slice 4 is DONE** (DONE #48) — the §9 command-profile helper +
  enabled **Copy command** button (a display template the app never executes;
  `--host 0.0.0.0` guidance kept).
- **LMM Slice 5 (Phase-1 validation / docs reconciliation) is DONE** (DONE #49) —
  validation **PASSED**, `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`, docs-only,
  no code changed. Phase 1 is complete. NEXT is **Ask Your Guide local-only chat**
  (recommended) or the sign-off-gated host-companion DESIGN (see the header above +
  design §11).
- **The Shortcut Inspector / Repair loop is COMPLETE** (Slices 1+2+3A+3B + the
  degraded-activation confirm polish, DONE #39→#43). See the block just below and
  DONE #43 for the latest slice. **A follow-up shortcut slice (DONE #44) then
  fixed the Edit-modal generator-preset source bug and added opt-in
  `saved_prompt`** — see DONE #44.

---

## Shortcut Inspector / Repair Loop (Slices 1+2+3A+3B + degraded-activation DONE)

- **Design doc:** `docs/SHORTCUT_INSPECTOR_REPAIR_DESIGN.md`. Safe UX + backend
  contract for inspecting and repairing shortcuts whose saved references
  (provider/model/style/preset/section/axis/tool/view) have gone invalid.
- **Slice 1 (backend inspector, read-only) is DONE** (DONE #39, branch
  `shortcut-inspector-backend`). Added a findings engine in
  `pipeline/shortcut_store.py` (`_collect_findings` / `_validity`) + the additive
  `validity` object on every `_public` view (list/get/import-preview) + the
  read-only `GET /api/shortcuts/{id}/inspect` route. Legacy `valid`/`reason` are
  **unchanged**. Fixes all three gaps: 3-tier status (binary→`valid`/`degraded`/
  `broken`), **full** findings list (not first-failure), and the previously-missing
  **saved-model** check. No writes, no frontend, no store refactor.
- **Slice 2 (frontend badges + read-only Inspector UI) is DONE** (DONE #40, branch
  `shortcut-inspector-ui`). `inspectShortcut` API helper + pure
  `frontend/src/shortcutStatus.js` status/badge/finding helpers (3-tier, with a
  fallback for old payloads lacking `validity`) + 3-tier badges on Home cards
  (valid quiet; degraded amber "Needs attention"; broken red "Broken") and
  Customize rows + a read-only `ShortcutInspector` drawer (findings + redacted
  repair-candidate summary + "read-only; repair comes next"). **No mutation, no
  preview/apply, no provider/model auto-switch, no raw keys.** Card activation is
  **unchanged** (still gated on legacy `valid`; broken never auto-routed). Backend
  untouched. node harness `verify-shortcut-status.mjs` 25/25; live Chromium UI
  proof; secret scan clean.
- **Slice 3A (backend repair preview + apply endpoints, BACKEND ONLY) is DONE**
  (DONE #41, branch `shortcut-inspector-repair-backend`). Added a shared,
  read-only repair normalizer (`_prepare_repair`) + `preview_repair` (pure) +
  `apply_repair` (the only write) to `pipeline/shortcut_store.py`, plus the two
  routes `POST /api/shortcuts/{id}/repair/preview` and `…/repair/apply`. Repair
  is an **explicit whitelisted patch** (`mode` + `changes{provider, model, style,
  generator_preset, output_depth, difficulty, include_sections{remove,set},
  remove_fields}` + `clone_name`) — **no arbitrary merge-patch**. Apply reuses the
  existing `update_shortcut` (in place) / `create_shortcut` (clone) CRUD, so the
  whitelist + atomic write hold automatically. **No auto-repair, no
  migration-on-read, no silent overwrite, no provider/model auto-switch, no raw
  keys.** `test_scripts/test_shortcut_repair.py` 29/29; existing
  `test_shortcut_store.py` 39/39 + `test_shortcut_inspector.py` 19/19 unchanged.
- **Slice 3B (frontend repair UI wiring) is DONE** (DONE #42, branch
  `shortcut-inspector-repair-ui`). The read-only drawer is now a safe repair
  surface: `previewShortcutRepair`/`applyShortcutRepair` API helpers + pure
  `frontend/src/shortcutRepair.js` draft/payload/staleness helpers + an enabled
  repair panel (provider/model/style/preset/depth/difficulty Keep/Replace/Remove,
  unknown-section removal, in-place/clone mode, live Preview diff, confirm-gated
  Apply). **Apply requires a fresh preview** (editing the draft marks it stale);
  no repair-on-open, no auto-switch, no raw keys. `verify-shortcut-repair.mjs`
  green; backend tests unchanged; live in-container repair flow + secret scan
  clean. Card activation behaviour is **unchanged**.
- **Degraded-activation confirm + "Repair instead" is DONE** (DONE #43, branch
  `shortcut-inspector-degraded-activation`). Home activation is now gated through a
  pure `activationDecision` (`frontend/src/shortcutStatus.js`): a **valid** shortcut
  launches immediately (no prompt); a **degraded-yet-launchable** shortcut
  (`validity.status === "degraded"` while legacy `valid === true`) raises a
  confirm dialog (**Continue anyway** / **Repair instead** → existing Inspector
  drawer / **Cancel**) before launching; a **broken** shortcut (`valid === false`)
  stays blocked and now shows a "This shortcut is broken" dialog offering
  **Inspect / Repair** instead of silently routing. **Legacy `valid` is still the
  hard guard**; Continue anyway calls the unchanged launch path with **no
  mutation**; Repair instead only opens the Inspector (no preview/apply until the
  user acts). New node harness `verify-shortcut-activation.mjs` (wired into
  `test:shortcuts`). Backend untouched; secret scan clean.
- **Remaining deferred polish (not started — pick one as an explicit slice):**
  (a) manual browser click-through of the live Preview→Apply UX + drawer/dialog
  layout polish; (b) the design §"Optional later polish" — "Repair all" batch, a
  Home "N shortcuts need attention" banner, model auto-suggest (preselect-only).
  See design doc §5/§7 and the `DECISIONS.md` repair entries.

---

## Where we are

- **Branch:** `chrome-renderer-v1` (the live integrated trunk; PR target)
- **Trunk tip:** `e399f09` — "Add local-model command-helper (copy start command)
  (LMM Slice 4)". The **Local Model Manager Phase 1** landed as four commits on top
  of the Shortcut Inspector group + the Edit-preset follow-up (`adc2a7e`): `94003bc`
  (Slice 1 design), `e27c674` (Slice 2 detection-only status endpoint), `7429f24`
  (Slice 3 Local Models status panel), and `e399f09` (Slice 4 command helper). Phase
  1 is now **validated** (Slice 5, DONE #49,
  `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`). Below the LMM group sit the
  **Shortcut Inspector / Repair Loop** (`a0f96d1`→`4458c9a`), the **in-app provider
  settings feature group** (`978516e`→`61fb423`), and the large-PDF core
  (`60c3e78`). Older `4458c9a` / `61fb423` / `60c3e78` / `901d44b` / `65b9b8f`
  references further down are historical — trunk is now `e399f09`.
- **`origin/chrome-renderer-v1`:** `e399f09` (local == origin; pushed)
- **Provider settings feature group is COMPLETE through Slice 5** (design →
  backend store/endpoints → Providers UI → runtime wiring → fetch-models endpoint
  → Refresh Models UI). See DONE #32 (backend store), #33 (Providers UI), #34
  (runtime), #35 (fetch-models endpoint), #36 (Refresh Models UI), and the design
  doc `docs/PROVIDER_SETTINGS_DESIGN.md`. Highlights:
  - **Security:** raw API keys stay **server-side only**. `/api/options` and
    `/api/provider-settings` are **redacted** (no key field by construction —
    only `configured`/`key_source`/last-4 `key_hint`/`base_url_host`).
    `config/provider_settings.json` is **non-secret** (`0644`);
    `config/secrets.json` holds **raw keys only** (`0600`, gitignored +
    dockerignored). The frontend never receives a raw key.
  - **Precedence:** provider/model resolves **per-job request > provider-settings
    default > `.env` > built-in default**. Generator presets **never hard-pin**
    provider/model — `model_hint` stays **advisory** — but a preset's **explicit**
    sampling/thinking value **can override** the stored runtime defaults.
  - **Runtime applied:** the stored `timeout_seconds`, `retry_count`, and
    `thinking_default` now reach the live model call (resolved once in
    `build_provider_config`, applied in `generate_chat_completion`). No store
    files ⇒ byte-identical to trunk (no timeout, 0 retries, thinking `True`).
  - **fetch-models endpoint: DONE** (DONE #35, branch
    `provider-settings-fetch-models`) — read-only `POST
    /api/provider-settings/{provider}/fetch-models`, no auto-persist.
  - **Refresh Models UI: DONE** (DONE #36, branch
    `provider-settings-fetch-models-ui`) — each Providers card has a **Refresh
    models** button calling the read-only endpoint. Fetched ids are
    **review-only**; a per-model **Add** / **Add all new** stages them into the
    draft `custom_models`, and an **explicit Save** is required to persist (after
    which `/api/options` includes the saved custom models — Builder dropdowns keep
    reading `/api/options`). Fetching never auto-saves and never auto-switches the
    provider/default model.
  - **Deferred:** encrypted-at-rest / OS keyring, `.env` import, the **Local Model
    Manager** (separate design-first feature), and the optional Builder "Provider
    default" thinking UI polish.
- **Large-PDF core is COMPLETE end-to-end** (preflight design → endpoint →
  Builder warning UI → page-selection plumbing → extraction honors selected
  pages → first-N/manual page-range UI). See DONE #27→#31. Automatic
  split/chunk processing and hybrid embedded-text + OCR dedup remain **deferred**.
- **Group C is COMPLETE and INTEGRATED** (C1 → C5, incl. C4a–d) onto `chrome-renderer-v1`.
- **For new sessions:** branch from `chrome-renderer-v1` @ `e399f09` (or later). Do **not**
  re-merge any of the old stacked feature branches — they are consumed/archival (see
  `DECISIONS.md` → "Consumed feature branches must not be re-merged"). The short one-page
  start-here is `docs/NEXT_CHAT_HANDOFF.md`.

## INTEGRATION — DONE: Group C is now on `chrome-renderer-v1` (pushed)

Group C was integrated onto the real target and `chrome-renderer-v1` was moved to the
integrated tip and pushed. The work originally landed on the throwaway `integ-group-c`
branch (off `origin/chrome-renderer-v1` @ `38cc822`); `chrome-renderer-v1` now points at
`1d51b36`. Sequence on the trunk:

- `6f888b2` — **Squash of the Group C stack** onto `38cc822`. Clean fast-forward, **zero
  conflicts** (the earlier "5 conflicts" were artifacts of two local-only commits on local
  `chrome-renderer-v1`: `863f5b7` Docker-hardening and `61c134c`, neither pushed nor in the stack).
- `5bde798` — **Re-applied `_preprocess_ocr_image`** (the one non-duplicate piece salvaged from
  local-only `61c134c`); its event-loop and provider-error changes were already superseded by the stack.
- `75ec24f` — **Prompt fixes** for two manual-test findings: MCQ answer explanations were wrapped in
  `$...$` (KaTeX stripped the spaces → `Biasshiftsthebaseline`); `slide_page_references` was too weak.
  Strengthened `mcqs_with_answers` (prose, never `$...$`) and `slide_page_references` (carry `## Page N`
  anchors through as compact `(p. N)` refs). Prompt-only; verified on a synthetic multi-page source.
- `72dab90` + `773209a` — **Mixed scanned/text PDF OCR fallback fixed** (+ its docs). Real issue:
  `_extract_pdf` decided text-vs-OCR for the WHOLE document, so one page of embedded text (a title
  slide) suppressed OCR for the rest — the 118-page `04_Neural_Networks...Backpropagation` extracted
  only ~97 chars / `## Page 1`. New behavior: **page-level** fallback — each page uses meaningful
  embedded text (≥40 chars OR ≥5 word-like tokens) else is OCR'd individually (reusing
  `_preprocess_ocr_image`); `## Page N` anchors preserved; mode now `pdf_text` / `pdf_ocr` /
  `pdf_mixed`. Verified on the real artifact: **~97 → 18,799 chars, 1 → 118 `## Page` headings, mode
  `pdf_mixed`**. Regression test `test_scripts/test_mixed_pdf_ocr.py` (synthetic page-1-text +
  pages-2/3-image PDF; skips cleanly without PyMuPDF/tesseract, full pass in Docker). Release smoke
  28/28 (the known outline-ordering check flaked once, passed on rerun).
- `1d51b36` — **Compose resource limits + `no-new-privileges` hardening** salvaged from local-only
  `863f5b7` (`mem_limit: 2g`, `pids_limit: 256`, `cpus: 2.0`, `security_opt: no-new-privileges:true`).
  Additive to `docker-compose.yml` only; `docker compose config` validated. `863f5b7`'s non-root/gosu
  hardening was already integrated at `6f888b2`; its **GHCR publish workflow / prebuilt image** and
  **pinned dependency lockfile** remain **deferred** decisions (see `DECISIONS.md`).

### Local-only commits `61c134c` and `863f5b7` — parked on `hardening`
Both were investigated. Useful pieces were salvaged onto the trunk (OCR preprocessing from
`61c134c` → `5bde798`; compose resource limits from `863f5b7` → `1d51b36`). The remaining
pieces (GHCR publish/prebuilt image, pinned deps) are deferred. The commits themselves stay
parked on the `hardening` branch — not merged, not deleted.

- **NOT automated — needs manual click-through:** generate a guide from a real scanned PDF through the
  Builder and confirm page references appear and MCQ answer spacing is correct in the rendered PDF.
- **Deferred:** large-PDF upload UX / preflight / page-range selection.

## DONE (in order)

1. **Generator presets** — Claude-Exam / Review / Cram: full system prompts +
   tuned sampling params (`a97d763`).
2. **Slice 3 — env-configurable attachment caps** (200k/600k default) +
   preset-aware truncation warning (`6f4d28c`).
3. **Slice 4 — math degrade** — math validation failures degrade to marked spans
   instead of killing the job; math prompt hardened (`9ba7e52`).
4. **Slice 5 — cleanup/hardening** — removed `legacy_scripts` + stray root files;
   redact host paths in error responses (`f3a8d84`).
5. **Slice 1A** — job stage reporting in pipeline + `/api/jobs/{id}/progress`
   endpoint (`d3d75fd`).
6. **Slice 1B** — persistent Builder action bar, live progress button,
   dirty-state warning, tooltips (`ec34d59`); progress poll tuned to 300ms
   (`f6424c9`).
7. **Slice 2A** — backend shortcut store with whitelist-validated import/export,
   defaults, 11 endpoints (`72fa2cd`).
8. **Slice 2B** — Home shortcuts UI, customize modal, import/export,
   save-as-shortcut (`afab4f2`).
9. **Slice 3/B1 — Library bulk actions (BACKEND ONLY)** — `51fc7b9`. Three
   partial-success endpoints under `/api/jobs/bulk/*` (`delete`/`restore`/
   `move`) that **reuse the existing single-item internals**: bulk delete →
   `trash_job` (soft-delete to `jobs/.trash/`, guarded by
   `_guarded_trash_target` — never hard-deletes), bulk restore → `restore_job`,
   bulk move → `library_store.move_job` (existing `folder_id` model). Routes
   registered **before** the parametric `/api/jobs/{job_id}/restore` so the
   literal `bulk` segment is never read as a job id. Verified in Docker (uid
   10001/appuser) via `test_scripts/smoke_library_bulk.py` (16/16) +
   curl/`ls .trash` evidence. **Frontend multi-select UI is NOT in this slice.**
10. **Slice B2 — Library multi-select bulk actions UI (FRONTEND)** — `5916861`.
    Library multi-select with per-job checkboxes + **select-all-visible**, a
    selection-aware bulk toolbar (Move to folder / Move to Unfiled / **Delete** /
    Clear), **bulk delete** routed through the soft-trash with an **Undo toast**
    (bulk restore of exactly the trashed ids), and **bulk move-to-folder**. All
    three use the canonical `/api/jobs/bulk/*` family; the legacy
    `/api/library/jobs/move` caller was migrated to `/api/jobs/bulk/move`
    (`folder_id`, not `folder`). Partial-success aware (`partitionResults`):
    succeeded ids cleared, `error` ids kept selected, ok/fail counts toasted;
    whole-request 404 (unknown folder) keeps selection + list untouched.
    Selection clears on folder/search/filter change. Verified in Docker via a
    real headless-Chromium (Playwright) click-through + captured bulk network
    calls; release smoke 28/28 (flaky outline check passed 3/3 in preflight).
11. **Slice B3 — finish Library folder + trash actions (FRONTEND + 1 backend
    route)** — `f1201a0`. **Folder multi-select** in the rail (per-folder
    checkboxes on non-system folders) + a folder action bar (count / Delete /
    Clear). **Bulk folder delete** offers BOTH behaviors via a dedicated
    two-path modal: **(A) Delete folders only** → guides fall back to Unfiled
    (loops the existing `DELETE /api/library/folders/{id}`), and **(B) Delete
    folders + move guides to Trash** → guides soft-deleted via the existing
    `/api/jobs/bulk/delete` (trash, NOT hard-delete) before the folders are
    removed. Partial-success aware: failed folders stay selected, successful
    ones disappear, ok/fail (+ trashed count) toasted. **Trash view** gained
    **multi-select** (per-card checkboxes + select-all), **Restore selected**
    (`/api/jobs/bulk/restore`), and **Permanently delete selected** behind a
    strong "cannot be undone" confirm. New backend route **`POST
    /api/jobs/bulk/purge`** loops the existing guarded `purge_trashed_job`
    (operates strictly inside `jobs/.trash/`; no new `rmtree` path) and refuses
    any id not currently trashed. Verified in Docker (smoke 28/28) + curl:
    bulk/purge returns ok for a trashed id and `error: not in trash` for
    bogus / `../escape` / active ids (active job untouched on disk); Option A
    leaves the guide active+Unfiled; Option B lands the guide in Trash and gone
    from active; bulk/restore returns a purged job to active.

12. **Slice C1 — expanded output-section toggles (BACKEND + prompt assembly)** —
    `fe898c4` (branch `style-output-toggles`). Added a real `include_sections`
    dict-of-bool field to `LLMJobRequest`, threaded
    `LLMJobRequest → run_llm_job → generate_study_guide → orchestrator`. Investigation
    first confirmed the pre-existing "module" keys (`mcqs`/`glossary`/… in
    `shortcut_store.KNOWN_MODULE_KEYS` + `frontend/shortcutMeta.js`) were
    **shortcut-only UI state** that **never reached prompt assembly**, so a new
    backend mechanism was required (per the STEP-1 stop rule, confirmed with the
    operator before building). Single source of truth is `INCLUDE_SECTION_FRAGMENTS`
    in `pipeline/orchestrator.py` (21 canonical keys: the 18 target toggles + 3 kept
    legacy keys); legacy keys normalise via `INCLUDE_SECTION_ALIASES`
    (`mcqs→mcqs_with_answers`, `formulas→formula_sheet`, `diagrams→diagrams_figures`).
    **New toggles default off** — an unset/empty/unknown-only map produces a
    **byte-identical** system message (verified: default `== MARKDOWN_MATH_SYSTEM`;
    preset path `== "{system}\n\n{MARKDOWN_MATH_SYSTEM}"`). Enabled fragments are
    injected **before** `MARKDOWN_MATH_SYSTEM`, which **remains the final block** in
    both default and preset paths; order is deterministic (insertion order). Unknown
    keys ignored (whitelist convention). `include_sections` is persisted in the job
    manifest so **rerender** reproduces the same sections. Verified in Docker (uid
    10001/appuser): in-container orchestrator proof of fragment presence/ordering for
    7 toggles, a real DeepSeek generation whose guide followed the requested sections
    (Glossary / MCQs+Answer Key / Worked examples / Formula sheet; slide refs
    correctly omitted as the source had none), manifest persistence confirmed; release
    smoke **28/28** (flaky outline-ordering check passed). **Builder UI exposure
    deferred to C3; depth/difficulty/voice deferred to C2; shortcut
    whitelist/persistence extension deferred.** Also documented the prior bulk-purge
    decision in `DECISIONS.md`.

13. **Slice C2 — generation depth + difficulty axes (BACKEND + prompt assembly)** —
    `24442bd` (branch `style-axes`). Added two **optional scalar-enum** global
    generation-directive axes to `LLMJobRequest`: `output_depth`
    (`quick`/`balanced`/`exhaustive`) and `difficulty`
    (`beginner`/`normal`/`exam_level`/`advanced`), threaded
    `LLMJobRequest → run_llm_job → generate_study_guide → orchestrator` (mirroring C1)
    and **persisted in the job manifest** so rerender/retry reproduces them. Source of
    truth: `OUTPUT_DEPTH_FRAGMENTS` / `DIFFICULTY_FRAGMENTS` in
    `pipeline/orchestrator.py`; assembled via `build_axis_directives_block`.
    - **Axes default unset.** With both unset the system message is **byte-identical**
      to before (verified: default `== MARKDOWN_MATH_SYSTEM`; preset path
      `== "{system}\n\n{MARKDOWN_MATH_SYSTEM}"`). Unknown/None axes add no fragment.
    - **Assembly order:** preset system prompt (preset path) → **axes** →
      **include_sections** → `MARKDOWN_MATH_SYSTEM`. Axes inject **before**
      include_sections; `MARKDOWN_MATH_SYSTEM` **remains the final block** in both paths.
    - **`voice` was DROPPED** — STEP-1 found it duplicates the Styles system
      (`baby_steps`/`exam_cram` styles + "blunt voice"/"formal" prompt directives);
      confirmed with the operator. **Voice/tone remains owned by Styles.** `difficulty`
      does **not** duplicate `mode` (mode is vestigial free-text with no difficulty
      semantics).
    - **Validation:** unknown axis values rejected at the API boundary (`HTTP 400`),
      orchestrator ignores unknowns defensively.
    - **Verified in Docker** (uid 10001/appuser, container healthy): in-container
      orchestrator proof of byte-identical no-axes paths + ordering (depth<difficulty<
      sections<MATH); a real DeepSeek generation with `output_depth=quick` +
      `difficulty=exam_level` + `include_sections={glossary, mcqs_with_answers}` whose
      guide showed a definitions table + MCQs/Answer Key (concise, exam-pitched);
      manifest persisted both axes + sections; invalid `output_depth`/`difficulty`
      returned 400. Release smoke **28/28** (flaky outline-ordering check passed).
    - **Builder UI exposure deferred (C3); shortcut persistence bridge deferred.**

14. **Slice — shortcut options persistence bridge (BACKEND ONLY)** — `cc75292`
    (branch `shortcut-options-bridge`). Extended the `builder_setup` shortcut
    payload whitelist (`pipeline/shortcut_store.py:_normalize_payload`) with the
    real C1/C2 generation fields: `include_sections` (canonical dict-of-bool),
    `output_depth`, and `difficulty`. **Closes the "legacy shortcut modules are
    inert" gap at the backend shortcut boundary** — shortcuts can now carry the
    fields that actually reach prompt assembly.
    - **Reuses C1 normalization** — `include_sections` is validated through
      `orchestrator.normalize_include_sections` + `INCLUDE_SECTION_ALIASES`
      (no second alias table); unknown keys dropped, only canonical enabled keys
      stored.
    - **Axes validated, not coerced** — invalid `output_depth`/`difficulty` are
      **rejected** via `ShortcutStoreError` (→ HTTP 400 on create/update; import
      pushes the offending shortcut into the batch `errors` list), never silently
      persisted. Unset → `None`.
    - **Legacy `modules` translate-on-read** — `_bridge_payload` derives
      `include_sections` from legacy `modules` in the **returned/exported**
      representation only (`_public` + `_exportable`); explicit `include_sections`
      wins, legacy modules only fill missing sections. **`shortcuts.json` is never
      rewritten on read** — old shortcuts stay old on disk until the user
      explicitly creates/updates/imports.
    - **Verified in Docker** (uid 10001/appuser, healthy): Test A create/read
      canonical round-trip; Test B export→import-preview→import (fields survive,
      id regenerated on conflict, no silent overwrite); Test C invalid axes → 400
      / import `errors`, unknown section key dropped; Test D legacy modules-only
      injected in-container translated to canonical sections on GET **and** export
      with **identical sha256 before/after** (disk still has no `include_sections`);
      Test E old field-less shortcut loads cleanly, nothing forced. Unit test
      `test_scripts/test_shortcut_store.py` **39/39**; release smoke **28/28**
      (flaky outline check passed).
    - **Builder UI wiring (load fields into Builder state + send to
      `/api/jobs/llm`) is the NEXT slice — NOT done here.**

15. **Slice C3 — expose output sections + axes in the Builder (FRONTEND + 1
    backend form-parser fix)** — `7af9cbd` (branch `builder-options-ui`).
    Surfaces the C1 `include_sections` + C2 `output_depth`/`difficulty` fields in
    the Builder and round-trips them through save/load shortcuts and the local
    draft.
    - **New `frontend/src/sectionMeta.js`** holds the display metadata only:
      21 section toggles in 4 cosmetic groups (Practice/Reference/Exam help/
      Source-aware) + the axis option tables + `normalizeSectionState`/
      `hasEnabledSections`. **The backend owns the key set** — every key mirrors
      `INCLUDE_SECTION_FRAGMENTS`/`OUTPUT_DEPTH_FRAGMENTS`/`DIFFICULTY_FRAGMENTS`
      in `pipeline/orchestrator.py` (verified 1:1, no invented keys). The frontend
      never widens the vocabulary.
    - **Builder UI:** replaced the old free-text `includes` chips with grouped
      `SectionControls` toggles + a new `AxisControls` (two segmented rows, "Auto"
      = unset). Action bar gained Sections + Axes summary chips. Legacy
      `includesToModules`/`modulesToIncludes`/`includeOptions` removed.
    - **Default stays clean:** `buildLlmPayload` omits `include_sections` when no
      section is enabled and omits each axis when unset, so a fresh Builder
      generate request carries none of these fields (and never a `voice` field —
      voice stays owned by Styles). Sections no longer appended as free text in
      `augmentSourceText`.
    - **Save/load shortcut wiring:** `builderStateToPayload` now emits the
      canonical `include_sections` + axes (not the inert legacy `modules`);
      `applyBuilderPrefill` reads them back and re-normalizes sections via
      `normalizeSectionState` (drops keys the Builder no longer exposes).
    - **Local draft parity:** `buildDraft`/`handleRestoreDraft` now persist +
      rehydrate the canonical fields (restore re-normalizes), replacing the old
      `includes` they used to carry. Dirty-state `settingsSignature` already
      covers all three, so changing a section/axis after a generation marks the
      preview stale.
    - **Backend form-parser fix:** the multipart branch of `_parse_llm_request`
      (`api/server.py`) now reads `include_sections` (JSON string → dict) +
      `output_depth`/`difficulty`. **Without this the options were silently
      dropped whenever a generation had attachments** (the no-attachments JSON
      path already worked). See `DECISIONS.md`.
    - **Verified in Docker** (uid 10001/appuser, healthy): frontend build OK; an
      esbuild-bundled harness drove the real `buildLlmPayload`/
      `builderStateToPayload`/`normalizeSectionState` (default omits all 4 incl.
      `voice`; selected sends canonical sections+axes; save→load→generate
      round-trips; unknown keys dropped on load; empty shortcut → `{}`/null).
      Live end-to-end: JSON-path job persisted sections+axes to `job.json`;
      **multipart-path job WITH an attachment persisted `{flashcards,
      formula_sheet}` + `exhaustive`/`advanced`** (proves the fix); default job →
      `{}`/null/null; invalid `output_depth` → HTTP 400. Release smoke **28/28**.
    - **NOT automated — needs manual click-through:** visual layout/spacing of the
      new grouped toggles + segmented axes, and tooltip hover behaviour
      (`InfoTip`/`FieldLabel tip`). DOM presence + wiring are proven; pixel
      layout is not.

16. **Slice C4a — generator preset display metadata + `model_hint` exposure
    (BACKEND ONLY)** — `3820c0c` (branch `preset-metadata`). Added three
    **display-only** descriptive fields to the canonical generator-preset registry
    (`_PRESET_DEFS` in `pipeline/generator_presets.py`) ahead of the preset-card UI:
    `purpose` (short purpose label), `recommended_use` (one-line "best with …"
    guidance), and `model` (clean model-name string for an icon/model chip, distinct
    from the longer prose `model_hint`). All exposed through the **existing**
    `_public()` → `list_generator_presets()` → `/api/options.generator_presets` path —
    **no new endpoint, no schema migration**. `name`/`description`/`provider`/
    `model_hint` already existed and were already exposed; this slice only **added the
    three missing fields**.
    - **`model_hint` exposed as a SOFT advisory only.** Unchanged semantics: the preset
      path only **soft-warns** on a provider mismatch (`generator_preset_warning`) and
      never blocks; the user can still pick any provider+model. C4a adds **no**
      enforcement and **no** hard pin.
    - **Display-only proof (source + grep):** `purpose`/`recommended_use`/`model` appear
      **only** in the registry defs and `_public`, nowhere in `orchestrator.py`/
      `run_llm_job.py`/the `/api/jobs/llm` handler. Generation still reads only `block`
      (→ system prompt), the sampling params, and `provider`/`model_hint`/`name` (warning
      text). `_public` reads the new fields via `.get()` so a preset omitting one
      serializes it as `None` instead of raising. Existing preset ids unchanged.
    - **Verified in Docker** (uid 10001/appuser, healthy): `python -m compileall`,
      `docker compose config/build/up`; `/api/options` shows all three presets carrying
      `purpose`/`description`/`recommended_use`/`model`/`model_hint`/`provider`; a
      full-payload secret scan (`sk-`/`api_key`/`secret`/…) found **no** leak. A live
      `claude_review` generation on DeepSeek completed `done` (no mismatch warning — it
      ran on its tuned provider) and the job manifest recorded `generator_preset:
      claude_review` unchanged, with **none** of the new display fields in the manifest.
      Release smoke **27/28 then 28/28** — the only failure was the **known flaky
      outline-ordering check**, which passed on rerun (pre-existing, depends on LLM
      output order, unrelated to this backend metadata change).
    - **Frontend preset cards / icons / compatibility warning deferred to C4b.** Do not
      hardcode card data in the frontend — it must consume this backend metadata.
    - Also added the permanent `DECISIONS.md` rule: any future `/api/jobs/llm` request
      field must be wired into **both** the JSON and multipart paths and verified in both.

17. **Slice C4b — generator preset cards + soft compatibility warning
    (FRONTEND ONLY)** — `b3d7785` (branch `preset-cards-ui`). Renders the C4a
    generator-preset metadata as preset **cards** in the Builder Style tab and adds
    a soft, advisory model-compatibility warning. **Consumes backend data only** —
    no preset copy is hardcoded; the cards read `name`/`purpose`/`description`/
    `recommended_use`/`model`/`model_hint`/`provider`/`params`/`available` from
    `/api/options.generator_presets` (the **generator** preset list from
    `generator_presets.py`, NOT the purpose/outline `presets.py`).
    - **New `frontend/src/presetMeta.js`** (display/compat helpers only): provider
      id → local SVG icon map (`providerIconFor`), text-badge fallback
      (`providerLabelFor`), and the soft `presetCompat(preset, selectedModel)`
      matcher. Three local SVGs committed under
      `frontend/src/assets/providers/{deepseek,qwen,local}.svg` (Vite resolves them
      to emitted asset URLs — 54–82 KB, above the 4 KB inline limit, so they are
      **separate files**, not JS-inlined). Logos render on a small **white chip**
      because Qwen/Local marks are near-black and would vanish on the dark UI; a
      missing/broken icon falls back to the text badge (`onError` + badge sibling),
      never blocking card render.
    - **Cards** (`GeneratorPresetCard` + rewritten `GeneratorPresetControls`):
      provider icon/badge, `model` chip, preset name, purpose label, description,
      recommended-use ("Best for: …"), selected ring + check. `available:false`
      greys/disables the card per the existing convention. The "None (use style)"
      option is kept. **Selection semantics unchanged** — a card still sets the same
      `generatorPreset` id the old chip selector did; the generate payload is
      untouched.
    - **Soft compatibility warning** replaces the old provider-mismatch note with a
      `model_hint`-vs-selected-model advisory: shown only when a preset is selected
      **and** it has a `model_hint` **and** the selected model is a confident
      non-match. Matching (`presetCompat`) normalises both sides to alphanumeric-only
      tokens and accepts equality/containment against **both** the prose `model_hint`
      **and** the cleaner `model` chip string (so "Gemma 4" rescues the local
      `gemma-4-…gguf` id where the longer prose hint would false-positive). Prefers
      **no** warning when unsure (no hint / unknown model → no warning). Warning copy:
      "This preset is tuned for {model_hint}. It may still work with {selectedModel},
      but {model_hint} is recommended." Plus an InfoTip restating it is advisory.
    - **Advisory-only — never blocks.** The Generate button stays `disabled={running}`
      only (never gated on compat); `buildLlmPayload` sends the user's `model` +
      `generator_preset` independently of the warning. **Proven end-to-end:** a live
      `claude_review` (hint "DeepSeek V4 Pro") generation with the **non-hint**
      `deepseek-chat` model completed `done`; the job manifest recorded
      `generator_preset: claude_review` + `model: deepseek-chat` (the user's choice).
    - **Tooltip priority adjusted** (`sectionMeta.js`): removed tips from the obvious
      controls (MCQs ×2, Flashcards, Glossary) and added/kept them on the less
      obvious ones (TL;DR summary, cram sheet, exam alerts, common mistakes,
      diagrams/figures, solved mock exam, self-test checklist, definitions cheat
      sheet, summary tables, instructor notes) plus the existing
      formula-sheet/worked-examples/citations/slide-refs tips and the new
      model-compatibility tip. Uses the existing `InfoTip` system — no new tooltip
      mechanism.
    - **Verified in Docker** (uid 10001/appuser, healthy): frontend build OK (SVGs
      emitted as separate assets); an esbuild harness drove the real `presetCompat`
      through **10/10** match/mismatch/absent cases (incl. the local-gemma rescue and
      the unsure→no-warning cases) + icon URL/badge fallback; served bundle contains
      the card/warning strings and references all three SVGs (served `200
      image/svg+xml`); `/api/options` unchanged; release smoke **28/28** (flaky
      outline check passed). **C3 controls confirmed intact** in the served bundle
      (axes Exhaustive/Exam-level, sections Cram sheet/Worked examples, Save draft,
      action bar/shortcut/progress markers).
    - **NOT automated — needs manual click-through:** card visual layout/spacing,
      provider-icon visual quality, warning placement/legibility, tooltip hover
      behaviour, overall UX feel.

18. **Slice C4c — add Qwen `qwen3.7-plus` to the model registry (REGISTRY ONLY)** —
    `390060c` (branch `qwen37-plus-model`). Added the model id `qwen3.7-plus` to
    `QWEN_MODELS` in `pipeline/provider_config.py` — the **single source of truth**
    for the Qwen model list surfaced through `/api/options` (`models.Qwen` +
    `provider_details[qwen].available_models`) and enforced by
    `validate_provider_model` (a model must be in `QWEN_MODELS` to be accepted).
    - **Ordering:** inserted at index 1, immediately after `qwen3.7-max`, next to the
      other 3.7-family model. **Default unchanged** — the Qwen default is
      `os.getenv("QWEN_MODEL") or os.getenv("LLM_MODEL") or QWEN_MODELS[0]`, and
      `qwen3.7-max` is still `QWEN_MODELS[0]`, so `default_model` stays `qwen3.7-max`.
      `qwen3.7-max` was not replaced; all six existing Qwen ids remain.
    - **Scope:** registry list only — no Builder UI, preset cards, prompt assembly,
      shortcut store, provider-settings architecture, Local Model Manager, or
      generation-pipeline behaviour changed (beyond now accepting this model id). The
      Builder's static `fallbackProviderDetails` Qwen list (a pre-`/api/options`
      placeholder) was intentionally left untouched — the real, authoritative list
      comes from `/api/options` and now includes `qwen3.7-plus`.
    - **Verified in Docker** (uid 10001/appuser, healthy): `compileall` OK; `compose
      config/build/up` OK; `/api/options` shows `qwen3.7-plus` in `models.Qwen` and
      `provider_details[qwen].available_models` (position 2), `default_model` still
      `qwen3.7-max`, all existing Qwen models present; full-payload secret scan clean.
      **Live generation verified:** a real `provider=qwen` + `model=qwen3.7-plus`
      generation completed `done` (manifest recorded `model: qwen3.7-plus`, 2716-byte
      `clean.md` with genuine study-guide content) — not just options exposure.

19. **Slice C5 — Home/nav cleanup + non-destructive stack merge preview
    (FRONTEND ONLY + preview)** — `7f78542` (branch `home-nav-cleanup`).
    Closes Group C by cleaning the Home page. **Cleanup, not a redesign.**
    - **Duplicate lower "Customize" button removed.** The Home "Pinned shortcuts"
      section head carried a second `Customize` button (`HomeShortcuts.jsx`)
      identical in behaviour to the page-head entry. Removed it; the section head
      now shows just its `<h2>`.
    - **Single primary entry kept:** the page-head **"Customize Shortcuts"**
      button. It calls `setCustomizeOpen(true)` → opens `CustomizeShortcutsModal`
      (the shortcut customization modal). **It does NOT route to Styles** — proven
      in the served bundle (exactly one "Customize Shortcuts" string; the modal is
      the shortcut editor, no Styles navigation on that handler).
    - **Smart Tools:** **already absent from Home** — no Smart Tools UI exists
      anywhere in the frontend (only orphaned `.sg-smart-*` CSS + an unrelated
      `Smartphone` icon import in the unused, never-rendered `TopBar.jsx`). Nothing
      to remove; it was not the sole entry point to anything. Orphaned CSS left
      untouched (cleanup-only, no behaviour change).
    - **Compare Styles:** **already lives in Styles, no move needed.** It is not a
      hardcoded Home button — it exists only as a `compare_styles` *shortcut tool
      type* (`shortcutMeta.js`) that routes to Styles via `TOOL_ROUTES`
      (`DesktopDashboard.jsx`). The Styles workspace **is** the compare surface
      ("Compare built-in prompt presets side by side…", `StylesWorkspace.jsx`,
      verified present in the served bundle).
    - **Home focus preserved:** pinned shortcuts + Recent Guides (`RecentJobsPanel`).
      No "continue last setup / continue last guide" feature exists on Home — there
      was nothing of that kind to preserve.
    - **Scope held:** diff is a single 3-line deletion in `HomeShortcuts.jsx`. No
      backend, Builder, Library, prompt assembly, shortcut store, provider model
      registry, Local Model Manager, provider settings, cancel, or rerender-preset
      code touched.
    - **Verified in Docker** (healthy): frontend build OK; `compose config/build/up`
      OK; `/api/health` ok; `/api/options` still lists **`qwen3.7-plus`** (C4c
      intact) + all three generator presets. Served bundle confirms **C3/C4b not
      regressed** — axes (Exhaustive/Exam-level), section toggles (Cram sheet/Worked
      examples), Save draft, preset cards ("Best for"), and the soft compat warning
      ("tuned for") all present. Release smoke **28/28** (flaky outline-ordering
      check passed).
    - **NOT automated — needs manual click-through:** Home layout/spacing after the
      button removal, the single Customize button opening the modal, Compare Styles
      functioning from the Styles tab, and overall visual polish.
    - **Stack merge preview (non-destructive, `git merge-tree --write-tree`
      chrome-renderer-v1 HEAD):** the stacked chain is **NOT cleanly mergeable** into
      `chrome-renderer-v1` yet — **5 pre-existing conflicts**: `Dockerfile`,
      `api/server.py`, `pipeline/extract.py`, `pipeline/llm_client.py`,
      `requirements.txt`. These are **stack-vs-target divergence, not introduced by
      C5** (C5 only touches `HomeShortcuts.jsx`, which is not in the conflict set).
      No merge was performed, no branch history rewritten, `chrome-renderer-v1`
      untouched. **Recommendation:** the conflicts need a deliberate review/resolve
      pass before merging the stack into `chrome-renderer-v1` — likely the Chrome
      renderer branch and the feature stack both edited the backend/runtime files.
      Group-C feature work itself is sound; this is an integration step, not a C5 bug.

20. **Slice C4d — generator preset card simplification + compatibility polish
    (FRONTEND ONLY)** — `0015e50` (branch `preset-card-polish`). A UI polish/
    correction pass on the C4b preset cards — not a redesign. Still consumes the
    C4a `/api/options.generator_presets` metadata (no hardcoded copy); **no backend,
    registry, prompt-assembly, or shortcut-store change**.
    - **Cards simplified:** removed the dense `description` paragraph and the entire
      **"Best for:" (`recommended_use`) block**. Each card now shows: a large
      provider icon + **bold model-name headline**, the **preset name** directly
      under it, and `purpose` as the single one-line subtitle. Shorter, scan-first.
    - **Identity made prominent:** `ProviderBadge` gained a `size="lg"` variant
      (icon chip `h-12 w-12`, was `h-6 w-6`) paired with the bold model name, so the
      "Gemma 4 → Claude-Exam / DeepSeek V4 Pro → Claude-Review / Qwen 3.7 Max/Plus →
      Claude-Cram" pairing is glanceable. Text-badge fallback kept + enlarged to
      match; missing/broken icon still never blocks the card (`onError`).
    - **`presetModelLabel(preset)`** (new, `presetMeta.js`): returns the backend
      `model` verbatim, except the Qwen 3.7 preset renders **"Qwen 3.7 Max / Plus"**
      (one preset covers both models).
    - **Qwen 3.7 Max/Plus compatibility:** added an explicit, conservative
      compatibility family `["qwen37max","qwen37plus"]` (normalised tokens) in
      `presetCompat`. When the preset's `model`/`model_hint` and the selected model
      are both in the family, the advisory warning is **suppressed**. **Not broadened**
      to other Qwen models (e.g. `qwen3.6-plus` still warns against the 3.7 preset).
      See `DECISIONS.md`.
    - **Advisory stays advisory:** the warning is display-only; Generate is still
      `disabled={running}` only, no auto-switch, the generate payload still sends the
      user's selected model + preset independently. Selection / save-as-shortcut /
      load-shortcut / C3 sections / C2 depth-difficulty / action bar / model badge /
      progress button / dirty-state all unchanged (card render is the only edit).
    - **Verified in Docker** (healthy): frontend build OK; `compose config/build/up`
      OK; `/api/health` ok; `/api/options` unchanged. An esbuild harness drove the
      **real** `presetCompat`/`presetModelLabel` through **9/9** cases — Qwen Max →
      no warn, Qwen Plus → no warn (the fix), `qwen3.6-plus` → warn (conservative),
      Qwen+DeepSeek → warn, DeepSeek/Gemma matches → no warn, empty selection → no
      warn; labels: qwen→"Qwen 3.7 Max / Plus", deepseek→"DeepSeek V4 Pro",
      gemma→"Gemma 4". Served bundle: **"Best for" gone (0 occurrences)**, "Qwen 3.7
      Max / Plus" present, compat "tuned for" warning present, C3/C4b markers
      (Exhaustive/Exam-level/Cram sheet/Worked examples/Save draft/Generator preset)
      intact. Release smoke **28/28** (flaky outline check passed).
    - **NOT automated — needs operator judgment:** whether the new icon size feels
      right, whether the cards are visually balanced, whether the reduced text feels
      appropriate, and whether the one-line `purpose` subtitles read well.

21. **Slice B4 — "Export selected" in the Library bulk bar (FRONTEND ONLY)** —
    `65b9b8f` (branch `library-export-selected`, now on trunk). The Library multi-select bulk toolbar
    (`BulkBar`) gained an **"Export selected"** action between *Move to Unfiled*
    and *Delete*. It reuses the existing `downloadExportBundle` client helper →
    `POST /api/exports/bundle` (the **same** endpoint/contract the Exports center
    uses); **no new export primitive and no backend change**. It sends the
    currently selected **active** Library job ids with `artifacts: ["pdf"]` (the
    `BundleRequest` default); the backend silently skips any selected guide
    lacking a PDF and only 404s if NONE are available. The helper streams the ZIP
    straight into a browser download (same pattern as Exports), so the result is
    surfaced the existing way. New `exporting` state disables the button while a
    bundle is building and when nothing is selected; the button shows a spinner +
    "Exporting…". Success/failure are reported through the existing **toast**
    convention (success names the downloaded filename); **selection is preserved
    on both success and failure** (never cleared on a failed export). Existing
    Move / Move-to-Unfiled / Delete (and Trash Restore/Purge) behavior is
    untouched. Trash exports were **not** added (out of scope). Verified in
    Docker: frontend build OK; `python -m compileall api pipeline` OK; `compose
    config/build/up` OK; `/api/health` ok; `/api/options` unchanged; release smoke
    **28/28**. Focused call-path check (no frontend test runner exists in-repo):
    posting the exact button payload (`{job_ids: <2 active ids>, artifacts:
    ["pdf"]}`) returns a `200 application/zip` with `Content-Disposition:
    attachment`, both guides' `final.pdf`, and `manifest.json`.

22. **Slice — cooperative server-side cancel (BACKEND + FRONTEND)** — `901d44b`
    (branch `server-side-cancel`, now on trunk). Adds a true server-side cancel for in-flight
    generations, completing the progress/cancel/retry triad (progress + retry
    already existed). **Design-first**, cooperative-only — **no process killing,
    no PDF/Chromium-pipeline rewrite.**
    - **Cancel state is a sidecar marker file** `jobs/<id>/cancel.requested`
      (`Job.request_cancel`/`cancel_requested`/`clear_cancel_request`/
      `raise_if_cancelled` in `pipeline/job_manager.py`), deliberately **not** a
      `job.json` field: the running job thread continuously read-modify-writes
      the manifest via `set_stage`/`update`, so a concurrent manifest write from
      the cancel request could be lost. The marker is write-once by the canceller,
      existence-checked by the pipeline → no shared-mutable-file race. Mirrors the
      existing trash-marker pattern.
    - **New terminal status `cancelled`** (distinct from `failed`; `error: null`).
      A new `JobCancelled` signal is raised at safe stage boundaries and caught at
      every pipeline entry point (`run_llm_job`, `run_pasted_text_job`,
      `run_markdown_job`) → set `cancelled`, clear the marker, return the job
      (never classified as a failure).
    - **Checkpoints (`raise_if_cancelled`) only at existing stage boundaries:**
      before extraction, **before the LLM call** (best early exit), **after the LLM
      returns / before render** (skip Chromium), and at the top of
      `run_raw_markdown_pipeline` + before `render_pdf`. **Never** mid-LLM-call,
      mid-Chromium-render, or mid-`save_clean_md`. Honest limitation: cancel = "stop
      at the next safe checkpoint," not instant abort; a cancel during the
      uninterruptible LLM/render wait takes effect when that call returns.
    - **Endpoint `POST /api/jobs/{job_id}/cancel`** (`api/server.py`): writes the
      marker for a running job (`cancelled: true`); **already-terminal jobs are a
      safe no-op** (`cancelled: false`, status echoed, **no marker, artifacts
      untouched**); unknown id → 404. It does **not** set status itself (the running
      thread owns the manifest).
    - **Partial artifacts preserved** — nothing is deleted on cancel; input/source
      stays. **Retry-from-cancelled is intentionally NOT wired** (`retry_failed_job`
      stays gated to `failed`); the Builder keeps its inputs/selections on cancel so
      the user simply re-generates. Documented, deferred.
    - **Frontend** (`BuilderWorkspace.jsx` + `api/client.js`): `cancelJob` client
      helper; the action bar shows a **Cancel** button only while running, enabled
      once the existing job-discovery poller learns the in-flight id (the create-job
      POST is blocking); `cancelled` added to `TERMINAL_STATUSES` so polling stops;
      a cancelled result shows a "Generation cancelled" state and **does not** clear
      the draft/inputs or present a guide.
    - **Verified:** host — `compileall` OK, frontend build OK, focused test
      `test_scripts/test_cancel_job.py` 14/14 (pipeline level). Docker (healthy,
      uid 10001) — same test **22/22** incl. the endpoint via TestClient
      (running→marker+true / done→no-op+no-marker / unknown→404); live curl proof on
      a real `done` paste job (no-op, no marker) + unknown→404; release smoke
      **28/28** (LLM/attachment/outline flows ran). **NOT automated — needs manual
      click-through:** clicking Cancel mid-generation in the live Builder and seeing
      the cancelled state + preserved inputs.

23. **Math/PDF fidelity Slice 1 — page-break guard for display math (CSS-ONLY)** —
    branch `math-display-breaks`. Added `break-inside: avoid;` +
    `page-break-inside: avoid;` to `.guide .katex-display` in **both** the base
    rule and the `@media print` block of `themes/claude_clean.css`, putting display
    math in the same break-protected family as `table`/`pre`/`blockquote`/`img`.
    **Strictly CSS-only** — no `pdf_renderer.py`, Chromium flags, KaTeX bridge /
    HTML renderer, sanitizer, prompts, `@page` geometry, or dependency change.
    Diff is 5 added lines in one file.
    - **New fixture `test_scripts/math_layout_fixture.md`** (inline + long-inline,
      short/long display, aligned block, arrows, display-in-list, display-in-table,
      and ~1 page of filler before a boundary equation). No external API calls.
    - **Honest verification (real Chromium PDF render, old vs. new CSS):** KaTeX
      display math in this pipeline **already renders atomically and never splits
      mid-equation** — a fitting block (incl. a 14-row `aligned`) jumps **whole** to
      the next page in both old and new CSS, at every filler offset tested. KaTeX's
      vlist/positioned-span output exposes no in-equation break points, and
      `.katex-display` already carries `overflow` (scroll container = monolithic).
      The only observed "split" is an equation **taller than the page** (45-row
      probe) — a *forced overflow* `break-inside` cannot prevent. So Slice 1 is
      **defensive/consistency hardening**, not a fix for a reproduced visible split;
      it becomes load-bearing if a later slice removes the overflow clipping.
    - **NOT fixed (deferred, not claimed):** long-equation overflow/clipping
      (cause B, Slice 2), math font-size rationalization (cause C, Slice 3), and
      prompt guidance for multi-line form (cause D, Slice 4). See
      `MATH_PDF_FIDELITY_INVESTIGATION.md` §10.
    - **Verified:** `npm --prefix frontend run build` OK; `python -m compileall api
      pipeline` OK; `docker compose config` OK; `docker compose build` OK; container
      recreated on the new image and **healthy** (`/api/health` `{"ok":true}`, new
      CSS confirmed baked in — 2× `page-break-inside`); `/api/options` OK, no secret
      leak; release smoke **28/28**; plus the before/after PDF render comparison
      above (HTML render shows 22 `.katex-display` blocks, the rule present in base
      + print, no raw LaTeX leaked into `<code>`).

24. **Math/PDF fidelity Slice 2 — long display math overflow/clipping (CSS-ONLY)** —
    branch `math-display-overflow`. Changed the **print** rule for
    `.guide .katex-display` from `overflow: hidden` to `overflow: visible` in
    `themes/claude_clean.css` (the only functional change; `0.9em` print font-size
    left untouched — font rationalization is Slice 3). **Strictly CSS-only** — no
    `pdf_renderer.py`, Chromium flags, KaTeX bridge / HTML renderer, sanitizer,
    prompts, `@page` geometry, or dependency change. Diff is one rule + an
    explanatory comment.
    - **Root cause (confirmed by real PDF renders):** a PDF page can't scroll, so
      the screen's `overflow-x: auto` becoming `overflow: hidden` in print **silently
      discarded** any display-equation content past the ~176 mm content box. KaTeX
      never auto-wraps display math (`white-space: nowrap`), so long single-line
      equations exceeded the box and lost their right tail. With `overflow: visible`
      a too-wide equation is **left-anchored** (readable start always kept) and
      extends into the empty side margin (`@page` has margins only — no
      header/footer/page-number to collide with). Only equations wider than the
      **whole A4 page** still clip, now at the physical edge, not the content box.
    - **Before/after (real markdown→HTML→PDF Chromium path, end-marker probes):**
      `overflow: hidden` clipped the right end-marker at **every** equation length
      tested; `overflow: visible` **keeps** moderate lengths (recovered into the
      margin) and only page-width-exceeding equations still clip. Real
      `test_scripts/math_layout_fixture.md` renders cleanly — long single-line
      equation no longer truncated within the content box; aligned block, arrows,
      display-in-list, and the **sanitized** table case verified **identical**
      before/after (no table/list regression).
    - **Improvement, not a full fix (not overclaimed):** arbitrarily long single-line
      equations cannot be made to fully fit CSS-only (KaTeX won't reflow; aggressive
      font shrink doesn't fit them and re-introduces cramping). Genuine semantic
      multi-line wrapping is **prompt-side (cause D / Slice 4)**; font-size
      rationalization is **cause C / Slice 3**. Both remain deferred. See
      `MATH_PDF_FIDELITY_INVESTIGATION.md` §11.
    - **Verified:** `npm --prefix frontend run build` OK; `python -m compileall api
      pipeline` OK; `docker compose config` OK; `docker compose build` OK; container
      recreated on the new image and **healthy** (`/api/health` `{"ok":true}`, new
      CSS confirmed baked in — print `.katex-display` now `overflow: visible`);
      `/api/options` OK; release smoke **28/28**; plus the before/after PDF render
      comparison above.

25. **Math/PDF fidelity Slice 3 — long-formula prompt guidance (PROMPT-ONLY)** —
    branch `math-formula-guidance`, commit `Guide long formulas into aligned math`.
    This is the **cause D / "Slice 4"** prompt-side work in
    `MATH_PDF_FIDELITY_INVESTIGATION.md` §7 (the doc numbers prompt guidance as
    Slice 4; this task tracked it as Slice 3 — same work). Extended
    `MARKDOWN_MATH_SYSTEM` in `pipeline/orchestrator.py` (the math/table contract
    appended **last** in both the default and generator-preset system messages)
    with a concise rule: avoid very long single-line display equations (they
    overflow PDF page width); break long equations/derivations across multiple
    lines inside `\begin{aligned} ... \end{aligned}`, one step per line, each line
    reasonably short; write prose explanations outside math delimiters — never
    wrap an explanatory sentence in `$...$`/`$$...$$`.
    - **Prompt-only.** No `pdf_renderer.py`, Chromium flags, KaTeX bridge / HTML
      renderer, sanitizer, CSS, `@page` geometry, or dependency change. The new
      text generalizes the existing "prose is not math" rule already in the
      `mcqs_with_answers` section fragment — it does not duplicate or contradict
      it, and does not weaken the existing aligned/table/matrix rules.
    - **Ordering preserved:** a preset's own system prompt stays first;
      `MARKDOWN_MATH_SYSTEM` stays the **final** appended block in both paths.
    - **Improvement, not a fix (not overclaimed):** this shapes model *output* so
      fewer equations are wide enough to hit the §11 clipping limit; it cannot
      reflow an over-wide equation the model still emits. That residual stays the
      deferred CSS/renderer limit. Font-size rationalization (**cause C**) remains
      untouched/deferred.
    - **Verified:** `python -m compileall api pipeline` OK; new
      `test_scripts/test_long_formula_guidance.py` **10/10** (default + preset +
      formula-heavy paths all carry the guidance, math block still last);
      `test_math_regressions.py` OK; `npm --prefix frontend run build` OK;
      `docker compose config`/`build` OK; container **healthy**
      (`/api/health` `{"ok":true}`, `/api/options` OK); release smoke **28/28**.

26. **Page-reference format standardization (PROMPT-ONLY)** — branch
    `page-reference-format`, commit `Standardize page reference prompts`. Manual
    PDF validation showed slide/page citations were inconsistent (`p.20`,
    `p. 20`, `pp. 20-21`, `p.96 − 100`, bare fragments, spaced-dash ranges).
    Tightened the **`slide_page_references`** include-section fragment in
    `pipeline/orchestrator.py` so the model always cites pages in one
    parenthesized format: `(page N)` for a single page, `(pages N-M)` for a
    continuous range, `(pages N, M, P-Q)` for multiple pages/ranges; a normal
    hyphen `-` for ranges (never an en dash or spaced dash). The old loose
    `(p. N)` recommendation was removed and `p.`, `pp.`, `pN`, and bare
    out-of-paren fragments are now explicitly banned.
    - **Prompt-only.** No renderer, sanitizer, CSS, dependency, or pipeline
      change. The fragment is injected via `build_include_sections_block`
      **before** `MARKDOWN_MATH_SYSTEM`; math guidance is untouched and stays the
      final appended block, so there is no conflict.
    - **Verified:** new `test_scripts/test_page_reference_format.py` **21/21**
      (fragment carries the exact format examples + bans; assembled default and
      preset prompts include them; ordering preset<axes<include<math preserved;
      math contract intact alongside page refs); `test_long_formula_guidance.py`
      **10/10** regression; `python -m compileall api pipeline` OK;
      `npm --prefix frontend run build` OK; `docker compose config`/`build` OK;
      container **healthy** (`/api/health` `{"ok":true}`, `/api/options` OK);
      release smoke pass.

27. **Large-PDF preflight Slice 1 — backend endpoint only** — branch
    `large-pdf-preflight-api`, commit `Add PDF preflight endpoint`. Implements the
    first slice of `docs/LARGE_PDF_PREFLIGHT_DESIGN.md` §10: a **read-only**
    `POST /api/preflight/pdf` that inspects ONE uploaded PDF *before* job creation
    and returns a lightweight verdict — **no UI, no job, no extractor change, no
    OCR, no limit change.**
    - **New helper `pipeline.extract.preflight_pdf`** — opens with `fitz`, reads
      `page_count`, probes a bounded, evenly spaced page sample
      (`_preflight_sample_indices`, default 20) with `get_text("text")` gated by the
      **existing** `_is_meaningful_page_text`, and reuses the **existing**
      `_ocr_available()`. **`_extract_pdf` is untouched** (no behavior change).
      Returns `PdfPreflightResult`; raises new `PdfEncryptedError` (encrypted) /
      existing `ExtractionError` (corrupt).
    - **Endpoint** (`api/server.py`, registered before the static mount): multipart,
      single `file`, **PDF-only** (non-PDF → `400`). Streams to a temp file reusing
      the **existing** `MAX_LLM_ATTACHMENT_BYTES` (15 MB) guard (over-limit → `400`,
      ceiling unchanged); temp file removed in `finally`; inspection runs in a
      threadpool. `_build_pdf_preflight_report` assembles `verdict` (`ok`/`warn`/
      `blocked`) + `warnings[]` + `allowed_actions[]` + echoed `limits{}`.
      **Encrypted/corrupt → `blocked` (with `ok: true`); any other failure (incl.
      PyMuPDF missing on host) → degrades to `ok`** so preflight never blocks a
      processable PDF. `allowed_actions` ∈ {`continue`, `process_first_n`,
      `choose_page_range`, `remove_file`}; **`split_automatically` never emitted**
      (deferred). No secrets/host temp paths in the response.
    - **Env knobs** (`os.getenv`, read once at import; the §4 names):
      `PREFLIGHT_SAMPLE_PAGES`/`PREFLIGHT_WARN_PAGES`/`PREFLIGHT_WARN_SIZE_MB`/
      `PREFLIGHT_OCR_PAGE_LIMIT`/`PREFLIGHT_DEFAULT_FIRST_N`/
      `PREFLIGHT_IMAGE_HEAVY_RATIO`/`PREFLIGHT_TEXT_RATIO`. `MAX_UPLOAD_MB` reported,
      not changed.
    - **Verified in Docker** (healthy): `python -m compileall api pipeline` OK;
      `npm --prefix frontend run build` OK; `docker compose config`/`build`/`up` OK;
      `/api/health` `{"ok":true}`; `/api/options` unchanged. New
      `test_scripts/test_pdf_preflight.py` **24/24** (helper + endpoint via
      TestClient: text/image-heavy/mixed/encrypted/corrupt/non-PDF-400/oversize-400/
      warn-by-pages; skips cleanly without PyMuPDF). Release smoke **28/28**. Live
      curl: text PDF → `ok`/`full`/`[continue]`; image-heavy → `warn`/`image_heavy`/
      `first_n` + first-N/range/remove actions; non-PDF → `400`; corrupt `.pdf` →
      `blocked`/`[remove_file]`.
    - **Deferred (unchanged):** frontend banner/actions (Slice 2), page-range flow
      into `_extract_pdf` (Slice 3), automatic split/chunk + hybrid OCR dedup
      (Slice 4+). See the design doc's Slice-1 implementation note.

28. **Large-PDF preflight Slice 2 — Builder warning UI** — branch
    `large-pdf-preflight-ui`, commit `Show PDF preflight warnings in Builder`.
    Wires the Slice-1 endpoint into the Builder so a large/scanned/problem PDF is
    surfaced **before** generation. **Frontend + API-client only — no backend,
    extractor, OCR, job, or limit change.**
    - **API client** (`frontend/src/api/client.js`): new `preflightPdf(file)` —
      multipart `POST /api/preflight/pdf`. A non-PDF/oversize/network failure
      rejects via `requestJson`; callers treat any failure as a **soft warning**
      and never block generation.
    - **`AttachmentsPicker`** (`BuilderWorkspace.jsx`): on adding a `.pdf`, calls
      preflight per file and stores `{status, report?}` in a new parent state map
      `attachmentPreflights`, keyed by a stable `attachmentKey` (name+size+
      lastModified). Lives **beside the selected files only** — never persisted to
      a job. Removing a file prunes its entry; "Continue anyway" marks it
      acknowledged.
    - **`PreflightCard`**: quiet for ordinary PDFs (verdict `ok`, no warnings);
      `checking` → spinner; `error` → soft "Could not inspect this PDF; it will be
      processed normally." For `warn` (amber) / `blocked` (red) it shows file size,
      page count, scanned flag, OCR-page estimate, the backend `warnings[]`, and a
      recommended action. Actions: **Continue anyway** (warn only) + **Remove
      file**; **Process first N pages** / **Choose page range** render **disabled
      with a "coming later" note** (Slice 3 builds the real flow).
    - **Generate gate**: `validateInputs` blocks generation when any attached PDF's
      verdict is `blocked` (corrupt/encrypted → must remove/replace). `warn`/`ok`
      never block. A preflight failure never blocks. Builder state/selections are
      preserved on warn/fail.
    - **Verified in Docker** (healthy): `npm --prefix frontend run build` OK;
      `python -m compileall api pipeline` OK; `docker compose config`/`build`/`up`
      OK; `/api/health` `{"ok":true}`; `/api/options` unchanged. Backend contract
      the UI consumes re-confirmed `test_scripts/test_pdf_preflight.py` **24/24**;
      release smoke **28/28**. Live curl: non-PDF → `400`; text PDF →
      `ok`/`text`/`[continue]`. No JS test runner exists in the repo (only an
      asset-verify script); adding vitest/jsdom would be out-of-scope dependency
      work, so the contract is covered by the existing backend test.
    - **Deferred (unchanged):** page-range flow into `_extract_pdf` (Slice 3),
      automatic split/chunk + hybrid OCR dedup (Slice 4+). The "first N" / "page
      range" buttons are intentionally inert affordances until Slice 3.

29. **Large-PDF Slice 3 — page-selection request plumbing** — branch
    `large-pdf-page-selection-plumbing`, commit `Plumb PDF page selections through
    jobs`. Makes PDF page selections **representable, validated, and persisted**
    without changing extraction. **Plumbing only — `_extract_pdf` untouched, no
    page filtering, no active page-range UI.**
    - **Field/shape:** new optional `page_selections` on the LLM request —
      `{filename: [[start, end], ...]}`, **1-based inclusive** (e.g.
      `{"deck.pdf": [[1, 20], [35, 42]]}`). Absent/null/empty ⇒ `{}` ⇒ all pages ⇒
      current behaviour. Chose the flat list-of-ranges form (task brief) over the
      design §5.1 `{mode, first_n, ranges}` object — "first N" is just `[[1, N]]`.
    - **Validation** (`_normalize_page_selections`, raises **400** on bad shapes):
      positive-int `[start, end]` pairs with `start <= end` (`bool` rejected);
      ranges sorted + overlapping/adjacent merged to a canonical spec; bounded by
      `MAX_PAGE_SELECTION_FILES`=20 / `MAX_PAGE_RANGES_PER_FILE`=50. Does **not**
      need the real page count (no clamp yet).
    - **Both paths wired** (DECISIONS.md rule): JSON body via `LLMJobRequest`
      (loose `dict[str, Any]`, normalized at handler) **and** multipart via a JSON
      string in `_parse_llm_request`, mirroring `include_sections`/`outline`.
    - **Persistence:** stored in `job.json` by `run_llm_job` (`page_selections`
      key, default `{}`), echoed by `job_response` (`_safe_page_selections`), and
      **preserved across retry** (re-normalized + re-stored); rerender never
      touches it. **Not** forwarded to `_attach_sources`/extraction.
    - **Frontend:** `buildLlmPayload` adds `page_selections` only when the Builder
      carries a selection; reserved internal `pageSelections` state (default `{}`,
      no control sets it) keeps default requests byte-equivalent; `client.js` sends
      it as a JSON string on the multipart path. No page-range UI yet.
    - **Verified:** `compileall api pipeline` OK; `npm … build` OK; `docker compose
      config`/`build`/`up` OK; `/api/health` `{"ok":true}`; `/api/options`
      unchanged. New `test_scripts/test_page_selections.py` **24/24** (offline:
      LLM + renderer stubbed) — normalizer validation/merge, JSON + multipart
      persistence, default-omits, invalid→400, retry-preserves. Release smoke
      **28/28** (flaky outline-ordering check green on re-run).
    - **Deferred (unchanged):** `pages=` filter into `_extract_pdf` + the picker
      that populates `pageSelections` + enabling the Slice-2 actions (next slice);
      automatic split/chunk + hybrid OCR dedup (Slice 4+).

30. **Large-PDF Slice 4 — PDF extraction honors selected pages** — branch
    `large-pdf-page-selection-extraction`, commit `Filter PDF extraction by
    selected pages`. Makes the persisted Slice-3 `page_selections` finally **change
    what is extracted**: matching PDF attachments are restricted to the selected
    ORIGINAL pages. **Backend/extraction only — no page-range UI, no split/chunk,
    no hybrid OCR dedup, no limit change; `_extract_pdf` extended surgically (not
    rewritten); non-PDF extraction untouched; default (no selection) byte-for-byte
    unchanged.**
    - **`extract_file(path, pages=None)` / `_extract_pdf(path, pages=None)`**
      (`pipeline/extract.py`): `pages` = optional iterable of **1-based ORIGINAL**
      page numbers, **PDF-only** (ignored for every other type). The filter is one
      `if selected is not None and index not in selected: continue` at the top of
      the existing per-page loop, **before** any `get_text`/OCR — so **OCR only ever
      runs on selected pages**. Per-page text-XOR-OCR fallback unchanged.
    - **Original anchors preserved:** the loop still enumerates from 1 and emits
      `## Page {index}` with the *original* number, so selecting pages 20-21 yields
      `## Page 20`/`## Page 21`, **never** renumbered `## Page 1`/`## Page 2`.
    - **Validated against real `document.page_count`:** requested pages are
      intersected with `[1, page_count]`; out-of-range pages are **dropped (not
      clamped)** with a warning naming them; if **no** selected page is in range →
      empty `ExtractionResult("", "pdf_text", [warning])` (no crash), and the caller
      reports "no text could be extracted" exactly as today.
    - **Mode over the subset:** `pdf_text`/`pdf_ocr`/`pdf_mixed` computed from the
      selected pages (text-only subset → `pdf_text`, image-only subset → `pdf_ocr`,
      etc.).
    - **Threading** (`pipeline/run_llm_job.py`): `run_llm_job` → `_attach_sources`
      passes `page_selections`; for **PDF attachments only** it looks the selection
      up by the attachment's **original filename** (`AttachmentSource.filename` =
      the `original_filename` in attachment metadata = the Slice-3/frontend key),
      flattens the normalized `[[start,end],...]` ranges (`_expand_page_ranges`),
      and calls `extract_file(path, pages=...)`. Exact `dict.get` match — no
      fuzzy/index guessing; a selection for an unmatched filename is unused; same
      original filename on two attachments both legitimately get that selection.
    - **Verified in Docker** (healthy): `python -m compileall api pipeline` OK;
      `npm --prefix frontend run build` OK; `docker compose config`/`build`/`up` OK
      (no secret output pasted); `/api/health` `{"ok":true}`; `/api/options`
      unchanged. New `test_scripts/test_pdf_page_selection_extract.py` **39/39**
      (text pages 2-3 → original anchors, no page 1; no-selection == select-all;
      out-of-range safe warning; OCR-gated scanned-subset OCR-only; mixed-subset
      mode correctness; `_attach_sources` filename-keyed threading). Existing
      `test_mixed_pdf_ocr.py` and `test_page_selections.py` both still pass
      (24/24). Release smoke **28/28** (flaky outline check green on re-run). Live
      Docker generation with `page_selections={"sel.pdf": [[2, 3]]}` → the job's
      `input/source.txt` carries only `## Page 2`/`## Page 3` (not `## Page 1`) and
      the manifest persists the selection.
    - **Deferred (unchanged):** the active page-range **UI** picker that populates
      `pageSelections` + enabling the Slice-2 actions (Slice 5); automatic
      split/chunk + hybrid embedded-text + OCR dedup (still §9 deferred).

31. **Large-PDF Slice 5 — page-selection UI is live** — branch
    `large-pdf-page-selection-ui`, commit `Enable PDF page selection UI`. Turns the
    Slice-2 inert "Process first N pages" / "Choose page range" affordances into
    **working** Builder controls that populate `pageSelections`, which the Slice-3
    plumbing already sends and the Slice-4 extractor already honors. **Frontend/UI
    only — no backend, `_extract_pdf`, page-selection validation, upload-limit, or
    dependency change.**
    - **`PreflightCard` actions enabled** (`BuilderWorkspace.jsx`, `warn` PDFs;
      `blocked` still Remove-only). **Process first N** → `{ "<file.name>": [[1, N]] }`
      with `N = limits.default_first_n` (20) **capped by `page_count`** when known.
      **Choose page range** → inline editor parsing `1-20` / `1-20, 35-42` via new
      `parsePageRanges` to `[[1,20],[35,42]]` (**1-based inclusive**, validated:
      positive ints, `start <= end`, sorted; bad token → inline error, no apply;
      exceeding a known `page_count` applies with a soft note — backend/extractor
      drop the extras safely).
    - **Active-selection bar:** a calm green **"Using pages 1-20"** (`formatPageRanges`)
      replaces the amber warning once a selection is set, with **Edit range** +
      **Use all pages** (clears → all pages). The **"coming later"** note/disabled
      buttons are removed.
    - **Per-file, keyed by `file.name`** — the exact backend match key
      (`original_filename`); multiple PDFs each carry their own selection.
      **Removing a file clears its selection** unless a duplicate-named sibling
      remains.
    - **Default unchanged / opt-in:** no selection ⇒ `pageSelections` `{}` ⇒
      `buildLlmPayload` omits `page_selections` ⇒ "all pages" ⇒ byte-equivalent
      request. **Not** persisted to drafts/shortcuts (the attachments it refers to
      aren't either, so it would be orphaned); preflight report still not persisted
      to `job.json`.
    - **Verified** (Docker healthy): `npm … build` OK; `compileall api pipeline` OK;
      `compose config`/`build`/`up` OK (no secret output); `/api/health` `{"ok":true}`,
      `/api/options` unchanged. `buildLlmPayload` payload harness **5/5** (default &
      empty omit; first-N, multi-range, multi-PDF included verbatim); parse-rule
      check **12/12**; served bundle carries the new strings and **no** "coming
      later". `test_page_selections.py` **24/24**, `test_pdf_page_selection_extract.py`
      **39/39**, release smoke **28/28** (transient provider/host hiccups on
      overlapping runs cleared on a clean run after a container restart). Live Docker
      generation with `page_selections={"multi.pdf": [[2, 3]]}` → manifest persists
      the selection and `input/source.txt` carries only `## Page 2`/`## Page 3` (not
      pages 1/4).
    - **NOT automated — needs manual browser click-through:** the warn card's First-N
      button, the inline range editor (valid + invalid input), the "Using pages …"
      bar + Use-all-pages reset, per-file selection with two PDFs, and clearing on
      file removal. DOM strings + payload/extraction wiring are proven; pixel
      layout/hover is not.
    - **Deferred (unchanged):** automatic split/chunk processing + hybrid
      embedded-text + OCR dedup (§9).

32. **Provider Settings Slice 1 — backend store + safe endpoints (BACKEND ONLY)** —
    branch `provider-settings-backend`, commit `Add backend provider settings store`.
    Server-side foundation for in-app provider settings per
    `docs/PROVIDER_SETTINGS_DESIGN.md` §18. **No frontend UI, no Local Model
    Manager, no provider auto-switching, no generator-preset hard-pinning.**
    - **New store** `pipeline/provider_settings_store.py` mirroring the existing
      JSON stores (atomic temp-file + `os.replace`, whitelist parsing, defensive
      load). Two files under a gitignored `config/`: `provider_settings.json`
      (NON-SECRET, `0644`) and `secrets.json` (raw API keys ONLY, `0600`). Raw keys
      live **only** in `secrets.json` — never in the public file, a response DTO, a
      log line, a job manifest, or an export.
    - **Resolver layer** in `pipeline/provider_config.py`: a single
      settings-store → `.env` → built-in-default chain (`_effective_api_key` /
      `_effective_base_url` / `_effective_default_model` + custom-model merge) used
      by both the registry entries and `build_provider_config`. **No store files ⇒
      byte-identical to the old env path** (the migration guarantee). Per-job
      request provider/model still wins; the store only supplies defaults; sampling
      precedence is preset pin → store → env/default (§4b).
    - **Endpoints** (registered before the static mount): `GET /api/provider-settings`,
      `PATCH /api/provider-settings/{provider}` (partial; `api_key` write-only —
      blank = unchanged), `POST /api/provider-settings/{provider}/clear-key`, and
      `POST /api/provider-settings/{provider}/test` (tiny `max_tokens:1` probe, 10s
      timeout, no retries, **no job/artifacts**, classified+redacted errors). All go
      through one redacting serializer (`_settings_to_public_dict`) that has **no key
      field by construction** — it exposes only `configured`, a `key_source`
      (`store`/`env`/`none`), a last-4 `key_hint` (only when len > 4), `base_url_host`
      (host only, userinfo stripped), models, sampling, and `last_test`.
    - **`/api/options` unchanged in shape**; it now derives values from the resolver
      (store → env), so a saved key flips `configured` without any Builder change.
    - **Docker:** `config/` added to `.gitignore` + `.dockerignore`; `./config`
      volume added to compose; `docker-entrypoint.sh` chowns `/app/config` to
      `appuser` so the non-root process can write the store.
    - **Verified** (Docker healthy, uid 10001/appuser): `test_provider_settings_store.py`
      **26/26** (no-store byte-identical; PATCH non-secret → settings.json, key →
      secrets.json `0600` only; blank=no-op; clear-key flips `configured`; bounds
      400s; preset sampling override never repins provider/model). `npm … build` OK;
      `compileall api pipeline` OK; `compose config`/`build`/`up` OK (no secret
      output); `/api/health` `{"ok":true}`; release smoke **28/28**. **Secret-leak
      scan**: the three real configured keys appear in **none** of `/api/options`,
      `/api/provider-settings`, or live PATCH/test responses; live PATCH→GET→test→
      clear-key proven end-to-end against DeepSeek (test probe returns a redacted
      `provider_auth` for a bad key, no raw key in the body).
    - **Deferred (not started — need an explicit slice):** the frontend Providers
      settings page (§11); wiring store `timeout_seconds`/`retry_count`/
      `thinking_default` into the live client (stored + displayed only this slice);
      `fetch-models`; encrypted-at-rest secrets / OS keyring; `.env` import.

33. **Provider Settings Slice 2 — frontend settings UI (FRONTEND + API CLIENT ONLY)** —
    branch `provider-settings-ui`, commit `Add provider settings UI`. The §11
    Providers page consuming the Slice 1 endpoints. **No backend resolver/security
    change, no Local Model Manager, no provider auto-switching, no preset
    hard-pinning, no dependency/lockfile change.**
    - **API client** (`frontend/src/api/client.js`): added `getProviderSettings`,
      `updateProviderSettings(provider, patch)`, `setDefaultProvider(provider)`,
      `clearProviderKey(provider)`, `testProviderSettings(provider, payload?)`. The
      patch is partial; `api_key` is included **only when non-empty** (blank = keep
      current). Nothing reads a raw key back.
    - **New workspace** `frontend/src/components/ProviderSettingsWorkspace.jsx`,
      routed from the existing **Models** sidebar item (the old read-only
      `ModelsPage`/`ProviderCard`/`normalizeModelProviders` in `DesktopDashboard.jsx`
      were removed — that page only read `/api/options`; the new page is the editor).
      One card per provider showing safe fields only (configured pill, `key_source`,
      last-4 `key_hint`, `base_url_host`, default model, custom models, temperature/
      top_p/max_tokens/timeout/retries, qwen thinking, `last_test`).
    - **API key field is write-only**: a password input, never prefilled, empty =
      unchanged, sent only on Save, cleared after Save. **Remove key** button calls
      `clear-key` behind a `window.confirm` (disabled unless `key_source==="store"`).
      **Test connection** shows loading/OK/failure with the server's already-redacted
      message + category + latency only — never a raw key or request body. Base URL is
      a blank-keeps-current override (only the host is ever exposed by the backend).
    - **Resilience:** the Builder still reads `/api/options` independently, so a failed
      `GET /api/provider-settings` only shows a recoverable error + Retry on the
      settings page; generation is unaffected.
    - **Verified:** `npm … build` OK; `compileall api pipeline` OK; `compose config`
      PASS (no secret output); `compose build`/`up` OK; `/api/health` `{"ok":true}`;
      `/api/options` OK; release smoke **27/28** (the one fail is the non-deterministic
      "outline followed in order" LLM-output assertion, unrelated — no backend/pipeline
      code changed). **Secret-leak proof:** PATCHed a sentinel key
      `sk-FAKE-LEAKCHECK-…` on `local` → it appears in **none** of `/api/provider-settings`,
      `/api/options`, the PATCH/test responses, the served `frontend/dist` JS, or the
      non-secret `config/provider_settings.json`; it lived **only** in `secrets.json`
      (`0600`, uid 10001/appuser) and host `cat config/secrets.json` is **Permission
      denied** (expected, supports the model). `clear-key` reverted `local` to
      `key_source:"env"` and removed the sentinel from `secrets.json`.
    - **Deferred (unchanged from Slice 1):** wiring store `timeout_seconds`/
      `retry_count`/`thinking_default` into the live client (now DONE — see #34);
      `fetch-models`; encrypted-at-rest secrets / OS keyring; `.env` import.

34. **Provider Settings Slice 3 — runtime defaults wired into live generation
    (BACKEND ONLY)** — branch `provider-settings-runtime`, commit `Apply provider
    runtime settings` (commit `40df617`). The stored `timeout_seconds`,
    `retry_count`, and `thinking_default` now reach the live model call. **No
    Local Model Manager, no provider auto-switching, no generator-preset
    hard-pinning, no new env knob.**
    - **Mechanism:** `LLMConfig` gained `timeout`/`retry_count` fields, resolved
      in `build_provider_config` (store → default) and consumed in
      `generate_chat_completion`, so **every** path that builds a config via
      `build_provider_config` (study-guide, style, outline, section-regen, quiz)
      picks them up. Timeout: an explicit caller `timeout=` (the test probe's
      short fail-fast value) wins over `config.timeout`; the probe also forces
      `retries=0`.
    - **Retry is transient-only:** bounded `[0,10]`, retries only transient
      API/transport failures (429, 5xx, connection/timeout type-names); **never**
      4xx (auth/model/bad-request), missing config, unsupported provider, or
      cancel. Retry is internal to the single model call (no duplicate
      jobs/artifacts).
    - **Thinking precedence (qwen-only):** explicit request/preset value wins,
      else store `thinking_default` fills, else `True`. `LLMJobRequest.qwen_thinking`
      / the multipart default became `None` so an "unset" field lets the store
      fill, while the Builder still sends an explicit bool ⇒ unchanged UI. This is
      the rule "a preset's explicit sampling/thinking can override the stored
      runtime default; provider/model is never hard-pinned."
    - **Migration guarantee:** no store files ⇒ byte-identical to trunk (timeout
      `None`, 0 retries, thinking `True`).
    - **Verified:** `test_scripts/test_provider_runtime_settings.py` (22 checks) +
      existing `test_provider_settings_store.py` (26) + `smoke_release.py`
      (28/0/0). See `DECISIONS.md` → "Provider runtime settings: timeout/retry at
      the call boundary, transient-only retry".
    - **Deferred (unchanged):** `fetch-models` endpoint; encrypted-at-rest secrets
      / OS keyring; `.env` import; the **Local Model Manager** (separate
      design-first feature); optional Builder "Provider default" thinking UI polish.

35. **Provider Settings Slice 4 — backend fetch-models endpoint (BACKEND ONLY)** —
    branch `provider-settings-fetch-models`, commit `Add provider fetch-models
    endpoint`. Adds the long-deferred read-only model-discovery endpoint. **No
    frontend UI, no Local Model Manager, no provider auto-switching, no
    generator-preset hard-pinning, no dependency/lockfile change.**
    - **Endpoint:** `POST /api/provider-settings/{provider}/fetch-models`,
      registered **before** the static mount, run in a threadpool. Unknown provider
      → **HTTP 400** (existing `_resolve_known_provider`). Returns the stable schema
      `{provider, ok, models, source, base_url_host, error}` — `error` is `null` on
      success or `{category, message}` (redacted) on failure. `base_url_host` is
      host-only (never the full URL).
    - **Fetch (`provider_config.fetch_provider_models`):** resolves the **effective**
      base URL + key (store → `.env` → built-in default) and **reuses the existing
      `_discover_openai_models` `/models` discovery** (the same path `local` already
      used) for **all** providers — DeepSeek/Qwen hit `…/v1/models`, local hits
      `{base_url}/models` (keeping the `host.docker.internal`-only-in-Docker guard).
      A short fail-fast `PROVIDER_FETCH_MODELS_TIMEOUT` (10s) is used; the list comes
      back sorted + de-duplicated. It does **not** call `build_provider_config`, so a
      model-less provider can still list.
    - **READ-ONLY / no auto-persist:** no job, no artifacts; writes neither
      `provider_settings.json` nor `secrets.json`; does **not** add fetched ids to
      `custom_models` (returns them only — saving belongs to the future frontend
      "Refresh models" slice). Provider/model precedence + preset `model_hint`
      advisory behavior unchanged.
    - **Redaction:** the raw key never appears in the response; errors are mapped to
      a coarse category (`provider_auth`/`provider_ratelimit`/`provider_model`/
      `provider_network`/`local_offline`/`provider_error`) and stripped of the key +
      full URL. Unconfigured / no base URL → a **safe non-OK** result (not a 400,
      never the missing-key specifics).
    - **Verified:** new `test_scripts/test_provider_fetch_models.py` **16/16**
      (sorted/deduped success; local uses `/models`; unconfigured safe error;
      401 + network failures classified + redacted, no key leak; sentinel key absent
      from fetch / `/api/provider-settings` / `/api/options`; no file writes / no
      `custom_models`; precedence + preset advisory intact). `compileall` OK; frontend
      build OK; `docker compose config`/`build`/`up` OK, container healthy. Live
      Docker: unknown → 400; local → safe `provider_network` timeout; DeepSeek
      (env-configured) → `ok:true` with the real provider list; a fake key PATCHed on
      `local` appeared in **none** of the fetch / `/api/provider-settings` /
      `/api/options` responses or the container logs (cleared afterward).
      `test_provider_settings_store.py` 26/26, `test_provider_runtime_settings.py`
      22/22, release smoke **28/28**. See `DECISIONS.md` → "Provider fetch-models is
      read-only and does not auto-persist".
    - **Deferred (unchanged):** the frontend "Refresh models" button +
      save-to-`custom_models`; encrypted-at-rest secrets / OS keyring; `.env` import;
      the **Local Model Manager**.

36. **Provider Settings Slice 5 — frontend Refresh Models UI (FRONTEND + API CLIENT
    ONLY)** — branch `provider-settings-fetch-models-ui`, commit `Add provider model
    refresh UI`. Wires the DONE #35 read-only endpoint into the Providers page.
    **No backend resolver/security/store change, no Local Model Manager, no provider
    auto-switching, no generator-preset hard-pinning, no dependency/lockfile change.**
    - **API client (`frontend/src/api/client.js`):** new `fetchProviderModels(provider)`
      → `POST /api/provider-settings/{provider}/fetch-models` (no body). Returns the
      redacted `{provider, ok, models, source, base_url_host, error}` verbatim; never
      reads a raw key.
    - **UI (`ProviderSettingsWorkspace.jsx`):** each provider card gains a **Refresh
      models** button with a loading state. Success renders the fetched ids in a panel
      (`{n} fetched · {m} new`); failure shows only the backend's redacted
      `{category, message}`; an empty list shows a calm "No models returned" state.
      Fetched ids are **review-only** — each *new* id (not already in registry ∪ draft
      custom models) gets a per-model **Add** button, plus **Add all new**; ids already
      present render a non-actionable "in list"/"added" tag (dedupe).
    - **No auto-persist / no auto-switch:** adding only stages an id into the draft
      `custom_models`; nothing is saved until the existing **Save**
      (`PATCH /api/provider-settings/{provider}`) runs. A successful fetch never saves,
      never changes the default model/provider, and editing/refresh/clear invalidates a
      shown fetch list. Builder dropdowns keep reading `/api/options`, which includes
      the saved custom models after Save.
    - **Verified:** frontend build OK; `compileall api pipeline` OK; `docker compose
      config` exit 0 / no stderr (no secret expansion printed); `docker compose
      build`/`up` OK, container healthy; `/api/health` ok, `/api/options` shape intact.
      `test_provider_fetch_models.py` **16/16**, `test_provider_settings_store.py`
      **26/26**, release smoke **28/28** (no outline flake). Live Docker: DeepSeek
      (env-configured) fetch → `ok:true` real list; unconfigured local → safe
      `provider_network`/`provider_config`; a sentinel key PATCHed on `local` appeared
      in **none** of the fetch / `/api/provider-settings` / `/api/options` responses or
      the served JS bundle (cleared afterward); add-a-custom-model → Save → it appears
      in `/api/options` (then restored).
    - **Deferred (unchanged):** encrypted-at-rest secrets / OS keyring; `.env` import;
      the **Local Model Manager**.

37. **Fix — Provider "Test connection" false-negative on empty content (BACKEND
    ONLY)** — branch `fix-provider-test-empty-content`. Resolves validation
    **Finding #1**: `POST /api/provider-settings/{provider}/test` reported
    `ok:false` for reasoning/thinking models (Qwen with thinking, DeepSeek V4 Pro)
    because the `max_tokens=1` probe gets a valid choice with **empty visible
    content**, and `generate_chat_completion` raised "LLM returned an empty
    response."
    - **Fix (narrow):** added an `allow_empty_content: bool = False` kwarg to
      `generate_chat_completion` (`pipeline/llm_client.py`). When `True`, a choice
      with empty/null content returns `""` instead of raising; a response with **no
      choices** still raises on both paths. `test_provider`
      (`pipeline/provider_config.py`) now passes `allow_empty_content=True` —
      nothing else on the probe changed (still `max_tokens=1`, `retries=0`,
      `PROVIDER_TEST_TIMEOUT`).
    - **Scope guard:** normal study-guide generation is **unchanged** — default
      `allow_empty_content=False` keeps it strict so empty/bad model output is
      never silently accepted. No change to provider/model precedence, fetch-models,
      or the frontend.
    - **Verified:** `compileall api pipeline` OK; `test_provider_runtime_settings.py`
      **28/28** (added section 9: probe accepts empty/null content & reports
      `ok:true`; normal generation still rejects empty; a probe 401 still
      `ok:false`; probe result JSON carries no raw key), `test_provider_settings_store.py`
      **26/26**, `test_provider_fetch_models.py` **16/16**, release smoke **28/28**.
      See `DECISIONS.md` → "Provider Test Connection accepts empty content".

38. **Fix — stored `default_provider` precedence was inert (BACKEND ONLY)** —
    branch `fix-default-provider-precedence`. Resolves validation **Finding #2**:
    with no per-request provider, `api/server.py:_pick_generate_provider(None)`
    always picked the **first configured** provider (DeepSeek) and ignored the
    stored provider-settings `default_provider` (e.g. Qwen).
    - **Fix (narrow):** new pure helper
      `provider_config.stored_default_provider_entry(registry)` resolves the stored
      `default_provider` against the registry and returns its public entry **only**
      when it is set, known, and **configured** (else `None`). `_pick_generate_provider`
      consults it in the no-request-provider branch, **before** the first-configured
      fallback. Precedence ladder is now **explicit per-request provider > stored
      `default_provider` > first-configured fallback**.
    - **Scope guard:** an explicit per-request provider still wins (the
      `if provider:` branch is untouched); an unset / unknown / unconfigured stored
      default falls straight through to the historical first-configured behavior.
      The stored `default_model` path is unchanged (request model still wins, else
      the selected provider's effective default_model). Generator presets stay
      advisory — sampling only, never repinning provider/model. No raw key is read
      or exposed by the new path; `/api/options` Builder pre-select left out of scope.
    - **Verified:** `compileall api pipeline` OK; new
      `test_scripts/test_default_provider_precedence.py` **14/14** (stored default
      picked over first-configured; request provider wins; unconfigured/unknown/unset
      default → first-configured fallback; stored default_model used when request
      model absent; request model wins; preset stays advisory; leak-scan clean),
      `test_provider_settings_store.py` **26/26**, `test_provider_runtime_settings.py`
      **28/28**, `test_provider_fetch_models.py` **16/16**. See `DECISIONS.md` →
      "Stored default_provider is a default only".

39. **Shortcut Inspector Slice 1 — backend inspector (BACKEND ONLY, read-only)** —
    branch `shortcut-inspector-backend`. Adds a richer, additive read-only
    validity layer for shortcuts that fixes the three known gaps without changing
    any existing behavior.
    - **Engine (`pipeline/shortcut_store.py`):** `_collect_findings(record)` →
      the **full** list of findings (provider/model/style/preset/section/axis/
      tool/view/legacy/payload-shape), `_status_from_findings` → 3-tier status
      (`error`⇒`broken`, `warning`⇒`degraded`, else `valid`), and `_validity` →
      `{status, findings[], repairable}`. Each finding is
      `{code, severity, field, message, current_value, repairable, candidates?}`
      with stable codes (`provider_missing`, `provider_unconfigured`,
      `model_unavailable`, `style_missing`, `generator_preset_missing`,
      `section_unknown`, `output_depth_invalid`, `difficulty_invalid`,
      `tool_route_missing`, `legacy_field_ignored`, `payload_shape_invalid`,
      `inspection_error`). Candidates come from live **redacted** registries only
      (provider ids/labels/`configured`, provider `available_models`, style ids,
      preset ids, canonical section keys, axis enums) — never a raw key.
    - **Additive field:** `validity` is attached in `_public`, so it rides on
      `GET /api/shortcuts`, `GET /api/shortcuts/{id}`, and import-preview. Legacy
      `valid`/`reason` (from the untouched `_evaluate_validity`) stay byte-compatible.
    - **New route:** `GET /api/shortcuts/{id}/inspect` (read-only) returns
      `{id,name,type,valid,reason,validity,repair_candidates}`; unknown id → 404.
    - **Deliberate divergence (documented):** the new model/section/axis checks
      raise `validity.status` to `degraded` but **do not** flip the legacy
      `valid:true` those shortcuts have today, so the existing activation guard is
      unchanged (see `DECISIONS.md` → "Shortcut inspector Slice 1: legacy `valid`
      stays true for new degraded findings"). Invalid axes are treated as
      **degraded** (ignored/defaulted at load), not broken.
    - **Verified:** `compileall api pipeline` OK; new
      `test_scripts/test_shortcut_inspector.py` **19/19** (valid/degraded/broken
      tiers, model-unavailable degraded with legacy `valid` still true, missing
      style/preset, unknown section, invalid axes, tool/view broken, multiple
      simultaneous findings, `…/inspect` 404, read-only sha256 unchanged, sentinel
      no-key-leak); existing `test_shortcut_store.py` **39/39**,
      `test_provider_settings_store.py` **26/26**. Live in Docker (healthy):
      `…/inspect` on a valid shortcut → `valid`/empty findings; on an injected
      broken+degraded shortcut → `broken` + `[provider_missing, style_missing,
      section_unknown]` with `shortcuts.json` sha256 unchanged; unknown id → 404;
      `smoke_release.py` **28/28**; secret scan clean across
      inspect/list/options/provider-settings + container logs. **No frontend, no
      repair preview/apply, no store refactor in this slice.**

40. **Shortcut Inspector Slice 2 — frontend badges + read-only Inspector drawer
    (FRONTEND + API client + node harness + docs)** — branch
    `shortcut-inspector-ui`. Surfaces Slice 1's `validity` data in the UI.
    **Read-only: no mutation, no preview/apply, no provider/model auto-switch, no
    raw keys; backend behaviour unchanged** (the Slice 1 response shape was
    already correct).
    - **API client (`frontend/src/api/client.js`):** `inspectShortcut(id)` →
      `GET /api/shortcuts/{id}/inspect` via the shared `requestJson` helper (404 /
      network errors surface the server `detail` like the other helpers; the
      already-redacted response never carries a raw key).
    - **Status helpers (`frontend/src/shortcutStatus.js`, pure / no React):**
      `shortcutStatus` prefers `validity.status` and **falls back** for old
      payloads with no `validity` (`valid:false`⇒broken, else valid);
      `statusBadge` (valid→"Valid", degraded→"Needs attention", broken→"Broken"),
      `countFindingsBySeverity`, `issueCount`, `shortcutFindings`. Tolerates
      missing validity, unknown status, non-array findings, null shortcut.
    - **Home cards (`HomeShortcuts.jsx`):** valid stays quiet (no badge); degraded
      → amber "Needs attention" chip, broken → red "Broken" chip; the chip + a
      small Info button open the Inspector (`stopPropagation`, so card activation
      is not triggered). **Activation unchanged** — still gated on the legacy
      `valid` boolean and routed by `DesktopDashboard.handleActivateShortcut`
      exactly as before; broken shortcuts are never auto-routed to Builder/Tools.
    - **Customize rows:** per-row tiered status chip + issue count + an **Inspect**
      icon-button. Create/edit/import/export/reorder/pin/delete untouched; import-
      preview rows left as-is (no saved id to inspect).
    - **Inspector drawer (`ShortcutInspector.jsx`, new):** right-side read-only
      panel; calls `inspectShortcut(id)` on open (seeds header from the list view
      while loading); loading / 404 / network-error states; renders name, type,
      status pill, legacy `valid/reason` (when blocked), every finding
      (code/field/severity/message/current_value/repairable + candidate count), and
      a redacted candidates **summary** (configured-vs-total providers, models per
      provider, style/preset/section/axis counts). States plainly *"Repair actions
      are not available yet. This inspector is read-only."*; the only repair
      control is a **disabled** "Repair (coming next)" button — no Save/Apply.
    - **Verified:** node harness `frontend/scripts/verify-shortcut-status.mjs`
      **25/25** (status normalization, old-payload fallback, finding counts, badge
      labels), wired into `npm --prefix frontend test`. `npm … build` OK;
      `compileall api pipeline` OK; backend `test_shortcut_inspector.py` **19/19** +
      `test_shortcut_store.py` **39/39** unchanged. Docker (healthy): `/api/health`
      ok, `/api/options` ok, live `…/inspect` shape/404 confirmed; real Chromium
      drove the degraded badge → Inspector (findings + candidates + read-only note
      + disabled repair, **no Apply/Save**), the Customize-row Inspect button, and a
      valid shortcut's "No problems found". `smoke_release.py` **28/28**; full
      secret scan (served bundle + inspect/list/options/provider-settings + logs)
      **clean**. **NOT automated — operator judgment:** badge/drawer visual
      polish, spacing, colour legibility.

41. **Shortcut Inspector Slice 3A — backend repair preview + apply endpoints
    (BACKEND ONLY)** — branch `shortcut-inspector-repair-backend`. Adds the safe
    mutation surface the read-only Inspector (Slices 1+2) was built against. **No
    frontend repair UI in this slice — that is Slice 3B.**
    - **Store logic (`pipeline/shortcut_store.py`):** one shared, read-only
      normalizer `_prepare_repair(id, body)` feeds both `preview_repair` (pure —
      returns original + proposed summaries, a field-level `diff`, and the
      resulting `validity`, writing nothing) and `apply_repair` (the **only**
      write). Apply reuses the existing CRUD: `update_shortcut` for `in_place`,
      `create_shortcut` for `clone` — so the whitelist + atomic write + id
      generation all come for free; **no new raw write to `shortcuts.json`**.
    - **Explicit whitelisted patch (NOT arbitrary merge-patch):** body is
      `{mode: in_place|clone, changes{…}, clone_name?}`. `changes` whitelist:
      `provider`, `model`, `style`, `generator_preset`, `output_depth`,
      `difficulty`, `include_sections{remove:[…], set:{k:bool}}`, and
      `remove_fields:[…]` (removable = `model`/`style`/`generator_preset`/
      `output_depth`/`difficulty` — **provider is not removable**). Any unknown
      top-level or change key is **rejected (HTTP 400)** — a mutation boundary, not
      silently ignored. The proposed payload runs through the same
      `_normalize_payload`, so preview == apply and unknown fields never persist.
    - **Validation against LIVE config:** replacement provider must resolve **and**
      be configured; a replacement model is validated against the **repaired**
      provider (provider-in-same-repair wins, else the existing provider; a
      model-only repair with no provider context → 400); style/preset checked for
      existence; axes validated by the store enum; `include_sections.set` keys must
      be canonical/alias keys. All invalid → 400, nothing written.
    - **Routes (`api/server.py`):** `POST /api/shortcuts/{id}/repair/preview` +
      `POST /api/shortcuts/{id}/repair/apply`, registered with the other
      `/api/shortcuts/*` routes (before the static catch-all). Unknown id → 404;
      bad request → 400, both via the existing `_shortcut_error` mapper. Repair
      currently supports `builder_setup` shortcuts only; others → safe 400.
    - **Safety guarantees:** read-only preview (sha256 unchanged), no auto-repair,
      no migration-on-read, no silent overwrite, no provider/model auto-switch
      (preset `model_hint` stays advisory — a model only changes when the caller
      explicitly asks), clone never overwrites (new id; original untouched), and
      **no raw key** read or returned.
    - **Tests:** `test_scripts/test_shortcut_repair.py` **29/29** (preview
      read-only; in-place provider/model repair; clone new-id + original-unchanged;
      unknown-field / invalid provider/style/preset/model/axis/section → error;
      model-provider context; model-only-no-provider → error; remove optional
      field; unknown-section removal; validity recompute; no migration-on-read;
      no key leak). `test_shortcut_store.py` **39/39** + `test_shortcut_inspector.py`
      **19/19** + `test_provider_settings_store.py` **26/26** unchanged.

42. **Shortcut Inspector Slice 3B — frontend repair UI wiring (FRONTEND + API
    client + harness + docs)** — branch `shortcut-inspector-repair-ui`. Wires the
    read-only Slice 2 Inspector drawer to the Slice 3A repair endpoints. **No
    backend change** (the 3A contract was correct as-is).
    - **API client (`frontend/src/api/client.js`):** `previewShortcutRepair`
      (READ-ONLY) + `applyShortcutRepair` (the only write), shared `requestJson`
      conventions, sending the 3A whitelisted patch `{mode, changes, clone_name?}`.
    - **Pure helpers (`frontend/src/shortcutRepair.js`):** `emptyRepairDraft`,
      `buildRepairPayload` (drops empty `replace` values so a half-finished choice
      never mutates), `draftSignature` (preview-staleness), `draftHasChanges`,
      `modelCandidatesForProvider`, `effectiveProvider`, `defaultCloneName`,
      `repairFieldKey`. The frontend never widens the backend field/op vocabulary.
    - **Inspector (`ShortcutInspector.jsx`):** the disabled "Repair (coming next)"
      footer becomes an enabled repair panel **only** for a repairable
      `builder_setup` with a supported action — else "No repair needed." / "No
      supported repair action for these findings." (no Apply). Per repairable
      finding: provider/model/style/preset/depth/difficulty Keep / Replace /
      Remove selects (model filtered by the selected/repaired provider; **provider
      not removable**) + per-key Remove toggles for unknown `include_sections`
      keys. Mode selector (in-place / clone) + clone-name input (default `"{name}
      (repaired copy)"`). **Preview** shows the proposed mode, field diff, resulting
      status, warnings, and "original unchanged until apply". **Apply** is disabled
      until a **fresh** preview exists for the current draft (editing the draft
      marks the preview stale → Apply re-disabled) and requires an explicit confirm
      whose copy differs in-place vs clone. On success: refresh the parent list
      (`onRepaired` → `reload`/`refresh`) + re-inspect in place.
    - **Safety held:** no repair call on open; draft starts empty; no apply without
      a fresh preview + explicit confirm; no provider/model auto-switch; tolerant
      of missing candidates / unknown codes / old payloads. **Activation behaviour
      unchanged** (still gated on legacy `valid`; broken never auto-routed; degraded
      still launchable).
    - **Verified:** `python -m compileall api pipeline` OK; backend
      `test_shortcut_repair.py` **29/29** + `test_shortcut_inspector.py` **19/19** +
      `test_shortcut_store.py` **39/39** (unchanged); `verify-shortcut-repair.mjs`
      (new) + `verify-shortcut-status.mjs` green (`npm --prefix frontend run
      test:shortcuts`); frontend build OK; Docker healthy. Live repair flow proven
      via the API in-container (broken → inspect broken/repairable → preview leaves
      the list byte-identical → apply in-place keeps id + flips to valid → clone
      makes a new id and leaves the original broken → invalid provider → 400).
      Release smoke **28/28**. Secret scan (served bundle + inspect/preview/apply/
      list/options/provider-settings + container logs) clean — 0 API-key leaks.
    - **NOT automated — needs manual click-through:** the drawer's visual layout,
      the live Preview→Apply UX in a browser, and the degraded-activation
      confirm/"Repair instead" Home path (deferred — see below).

43. **Shortcut Inspector — degraded-activation confirm + "Repair instead"
    (FRONTEND ONLY + harness + docs)** — branch
    `shortcut-inspector-degraded-activation`. Closes the design §5.5 gap that
    Slice 2/3B deliberately deferred: a **degraded** shortcut used to launch
    silently because legacy `valid === true`. **No backend change, no new repair
    logic, no bulk/auto repair.**
    - **Pure gating (`frontend/src/shortcutStatus.js`):** new `activationDecision`
      → `"launch" | "confirm" | "blocked"`. Legacy `valid === false` is still the
      hard guard (always `blocked`); `validity.status === "broken"` blocks; a
      degraded-yet-launchable shortcut (`status === "degraded"`, `valid !== false`)
      returns `confirm`; everything else (valid / old payload with no `validity`)
      returns `launch`. Pure + node-testable; the component duplicates no status
      logic.
    - **Home wiring (`HomeShortcuts.jsx`):** every card launch routes through a
      `requestActivate` gate. **Valid → launches immediately** via the unchanged
      `onActivateShortcut` path (no prompt). **Degraded → a confirm dialog**
      (shortcut name, "Needs attention · N issues found", top finding messages
      capped at 3, "some saved settings may be ignored or replaced by defaults")
      with **Continue anyway** (calls the original launch path, **no mutation**) /
      **Repair instead** (opens the existing `ShortcutInspector` drawer focused on
      that shortcut — **no preview/apply** until the user acts) / **Cancel** (no
      launch). **Broken → a "This shortcut is broken." dialog** offering **Inspect /
      Repair** (opens the Inspector) or Cancel — it no longer silently routed
      anywhere, and never routes to Builder/Tools.
    - **Safety held:** Continue anyway never repairs/modifies; Repair instead only
      opens the Inspector (reusing the single existing drawer, not a second
      system); no preview/apply call happens until the user uses the existing
      repair UI. Existing Home/Customize 3-tier badges + the repair preview/apply
      flow are unchanged.
    - **Verified:** `python -m compileall api pipeline` OK; backend
      `test_shortcut_store.py` **39/39** + `test_shortcut_inspector.py` **19/19** +
      `test_shortcut_repair.py` **29/29** (unchanged); new node harness
      `verify-shortcut-activation.mjs` (10/10, wired into `npm --prefix frontend
      run test:shortcuts` alongside the status + repair harnesses) covers
      valid→launch, degraded→confirm, broken→blocked, the legacy-guard-wins cases,
      and the missing-`validity` fallback; frontend build OK; `docker compose
      config/build/up` OK; `/api/health` ok; `/api/options` unchanged; release
      smoke **28/28**. Secret scan (served bundle + shortcut list/inspect + repair
      preview/apply + `/api/options` + `/api/provider-settings` + container logs)
      clean — the only env-value matches are **non-secret** model ids / base URLs,
      **0 API-key leaks**.
    - **NOT automated — needs manual click-through:** clicking a degraded card and
      seeing the confirm before launch, Continue anyway launching, Repair instead
      opening the Inspector repair UI, Cancel doing nothing, and the broken dialog.

44. **Shortcut Edit modal generator-preset fix + opt-in "Save prompt with
    shortcut" (FRONTEND + backend whitelist + tests + docs)** — branch
    `shortcut-prompt-save-and-preset-fix`.
    - **Part A — bugfix (root cause):** the Shortcut Edit modal's **Generator
      Preset** dropdown was sourced from `getPresets()` → `/api/presets`, which is
      the **Outline quick-template** registry (`pipeline/presets.py`: Exam Cram /
      Academic Report / Presentation / Chapter Summary / Final Revision) — a
      *different* registry from the real **generator presets**
      (`pipeline/generator_presets.py`: `claude_exam` / `claude_review` /
      `claude_cram`, exposed at `/api/options.generator_presets` and used by the
      Builder Style tab). The modal therefore saved outline-template ids into
      `payload.generator_preset`, which the Inspector then flagged
      `generator_preset_missing`. **Fix:** the modal now loads
      `options.generator_presets` (canonical source, same as Builder) and renders
      via a new pure `generatorPresetOptions(presets, current)` helper in
      `shortcutMeta.js` — leads with **None** (empty id → clears), shows the real
      presets, and appends any **legacy/invalid stored id** (incl. a mis-saved
      outline id) as a trailing **"… — unavailable"** option so old shortcuts load
      without crashing and **without being rewritten on read** (only changes if the
      user picks another option and saves). Builder Style preset cards and Builder
      Outline quick-templates are **unchanged** (the Outline flow still uses
      `getPresets()`).
    - **Part B — opt-in saved prompt/source text:** a builder_setup shortcut may
      now optionally carry the typed **source prompt/text** under a whitelisted
      `saved_prompt` field. **Opt-in only, default OFF.** The Builder "Save as
      shortcut" button opens a small dialog (name + checkbox *"Save prompt/source
      text with this shortcut"*, with a live char count); the Home Customize edit
      modal shows/edits/removes an existing saved prompt and badges rows + import
      preview with **"Saved prompt"**. Only **typed source text** is saved — never
      uploaded files / attachments / page selections / file paths. Size limit
      **100 000 chars** (`MAX_SAVED_PROMPT_CHARS`, mirrored in front+back); oversized
      is **rejected** (HTTP 400 on create/update, skipped on import), not truncated
      silently. Backend (`pipeline/shortcut_store.py`): `_clean_saved_prompt` +
      whitelist add (key **omitted** when empty so config-only shortcuts never grow
      it), an **info-only** inspector finding `saved_prompt_included` (carries the
      **length, never the text**; does **not** affect validity), and export/import/
      repair round-trip (bridge copies the key, repair re-runs the same whitelist).
      **Builder prefill is implemented:** applying a shortcut with `saved_prompt`
      prefills the Builder source text.
    - **Verified:** `python -m compileall api pipeline` OK; `test_shortcut_store.py`
      **53/53** (extended: omit-when-absent, persist, export/import + preview
      round-trip, oversized-reject, at-limit-accept, remove-on-update, info-marker
      length-not-text), `test_shortcut_inspector.py` **19/19**,
      `test_shortcut_repair.py` **29/29**; new node harness
      `verify-shortcut-form.mjs` (wired into `test:shortcuts`) covers the preset
      source/canonical-id/legacy-safe cases + saved-prompt opt-in/clamp/strip;
      frontend build OK; `docker compose config/build/up` OK; `/api/health` ok;
      `/api/options.generator_presets` = `['claude_exam','claude_review','claude_cram']`
      (no outline ids); release smoke **28/28**; live API round-trip of a shortcut
      with `saved_prompt` (valid:true, info marker, export carries it, inspect does
      **not** echo the text). Secret scan (served bundle + `/api/options` +
      `/api/provider-settings` + shortcut list/inspect + container logs) clean —
      **0 API-key leaks**; saved prompt is **user content**, opt-in, never silent.
    - **NOT automated — needs manual click-through:** the Builder save dialog
      checkbox (off by default; export with/without prompt), the edit-modal
      "Saved prompt" badge + remove, and the dropdown showing only real presets.

45. **Local Model Manager — DESIGN (LMM Slice 1, DOCS-ONLY)** — branch
    `local-model-manager-design`. A design-first slice for a *Local Model Manager*
    (LMM) that helps the operator run and use a local OpenAI-compatible model server
    (llama.cpp / `llama-server`) from inside the app. **No code written** — design
    doc + doc reconciliation only.
    - **New `docs/LOCAL_MODEL_MANAGER_DESIGN.md`** covering: (§1) the **current
      `local` provider behavior** read from live code — base-URL resolution chain
      (`_effective_base_url("local")` = store → `LOCAL_LLM_BASE_URL`/`LLM_BASE_URL`,
      **no built-in fallback** so an unset base URL ⇒ not-configured), how
      `/api/options` discovers local models (`_discover_openai_models` GET
      `{base}/models`, 1.5 s), how `fetch-models` reuses the same discovery (10 s,
      read-only, no persist), the offline behavior (discovery returns `([], str(exc))`;
      the `host.docker.internal`-outside-Docker guard), and the **`local_offline`**
      error category (generation path via `classify_exception`; fetch-models via
      `_classify_fetch_error`). (§2) **Architecture options A–D**: A detection-only,
      B host companion launcher, C in-container llama-server, D direct Docker→host
      spawn. (§3) **Recommended staged approach** — Phase 1 detection-only, Phase 2
      optional host companion, Phase 3 optional packaged desktop. (§4) **Phase 1
      backend API** — read-only `GET /api/local-model/status` + `POST
      /api/local-model/check` with a safe DTO (base-URL host, reachable, latency,
      model count/list, default model, classified error, start instructions). (§5)
      **Phase 1 frontend** — a Local Models view (status card, host display + link to
      Providers, Refresh, discovered models, "how to start llama-server" copy
      command, offline/troubleshooting states, Start/Stop omitted or disabled
      "Planned"). (§6) model-file management deferred (no GGUF browsing in Phase 1).
      (§7) security model. (§8) process lifecycle for Phase 2/3. (§9) a llama.cpp
      **command-profile schema** (not a hardcoded command). (§10) future Ask Your
      Guide local-only chat dependency. (§11) the LMM Slice 1→6+ plan. (§12) risks.
      (§13) recommendation.
    - **Recommendation: detection-first.** Phase 1 (Option A) reuses the existing
      local provider + fetch-models and crosses **no** container boundary;
      **Option D (direct Docker→host process spawn) is REJECTED** (a non-root,
      `no-new-privileges` container cannot safely/reliably manage host processes —
      it would need the Docker socket / `--privileged` / host PID namespace, which
      destroys the security model); process control, if ever wanted, goes through a
      host companion (Option B). Option C (in-container llama-server) is not the
      default (GPU passthrough / image size / mounts). **No second writer for
      provider config** — config edits stay on `PATCH /api/provider-settings/local`.
    - **Scope held:** no backend process spawning, no frontend UI, no provider-
      settings change, no generation-pipeline change, no Docker-config change, no
      llama.cpp integration code touched (read-only investigation), no dependencies,
      no raw key / full URL anywhere. Diff is **docs-only**.
    - **Doc reconciliation:** `CURRENT_TASK.md` (this entry + the NEXT block →
      LMM Slice 2), `NEXT_CHAT_HANDOFF.md` (LMM is design-only; next slice is
      detection-only backend status), `PROJECT_CONTEXT.md` (LMM is planned/design-
      first, not implemented), `DECISIONS.md` (detection-first + Option D rejection).
    - **Verified:** docs-only diff (`git diff --name-only` lists only the five docs);
      `python -m compileall api pipeline` OK (code opened read-only for the §1
      investigation; **none changed**). No Docker run required (no code touched).

46. **Local Model Manager — Slice 2: detection-only backend status endpoint
    (BACKEND ONLY)** — branch `local-model-status-api`. A safe, **read-only** status
    API for the configured `local` OpenAI-compatible server. Per design §4 + §11.
    - **New route `GET /api/local-model/status`** (+ a thin `POST
      /api/local-model/check` alias for the frontend "Refresh" verb — same probe,
      no new behavior). Both registered in `api/server.py` **before** the static SPA
      mount and run through `run_in_threadpool` like the existing test/fetch routes.
    - **New `get_local_model_status()` in `pipeline/provider_config.py`** — resolves
      the effective local base URL via the existing `_effective_base_url("local")`
      chain (store → `LOCAL_LLM_BASE_URL`/`LLM_BASE_URL`, no built-in default),
      probes `{base}/models` with a fail-fast 10 s timeout reusing
      **`_discover_openai_models`** (the same single discovery path as fetch-models),
      and returns the §4.2 DTO: `{ok, provider, configured, base_url_host,
      base_url_configured, in_docker, reachable, models, model_count, default_model,
      selected_model, latency_ms, error, actions, notes}`. Models are merged with
      stored `custom_models` exactly like `_local_entry`; `selected_model` resolves
      `default → first discovered`.
    - **`ok` ≠ reachable.** `ok:true` means the **status request** succeeded; the
      live server state is in `reachable`/`error`. Offline, no-base-URL, and
      malformed-URL are all **normal status results** (HTTP 200), never a crash.
    - **Error normalization:** a new `_classify_local_status_error` collapses **all**
      connection failures (refused / timed out / DNS / the out-of-Docker
      `host.docker.internal` guard) to a single **`local_offline`** (design §1.6),
      while genuine auth/model errors keep `provider_auth`/`provider_model`. No-base-
      URL uses `provider_config` (matching fetch-models). Messages pass through the
      existing `_safe_fetch_message` (raw key redacted, full URL collapsed to host,
      length-capped).
    - **Safety held:** no process spawn / start / stop / PID; no file or GGUF
      browsing; no command execution; **no writes** (provider settings, secrets,
      jobs, artifacts all untouched — provider config writes stay on
      `PATCH /api/provider-settings/local`); **no raw key** (no key field by
      construction); **host-only URL** via `_base_url_host` (drops userinfo/port/
      path/query). `actions` advertises `open_provider_settings` (enabled) and
      `copy_start_command` (**disabled**, "planned for a later slice" — no enabled
      control that does nothing); `notes` surfaces the `--host 0.0.0.0` gotcha only
      when the host is `host.docker.internal`. No new dependencies; no Docker-config,
      renderer, prompt, or pipeline changes.
    - **Tests:** new `test_scripts/test_local_model_status.py` (**17/17**) — reachable
      (sorted/de-duped models + count + latency), offline → `local_offline` + null
      latency, unconfigured (no base URL), malformed URL (redacted, no crash),
      host-only (no full URL/userinfo/query), sentinel key never in the response,
      no-write (settings/secrets unchanged, id not auto-persisted), and the action
      descriptors. Existing `test_provider_fetch_models.py` (16/16),
      `test_provider_settings_store.py` (26/26), `test_provider_runtime_settings.py`
      (28/28) all still pass.
    - **Verified:** `compileall` OK; `npm run build` OK; `docker compose config`
      exit 0; image built; container **healthy**. Live with **no** local server:
      `GET /api/local-model/status` and `POST /api/local-model/check` return HTTP 200
      with `reachable:false`, `error.category:"local_offline"`, `latency_ms:null`,
      and the `--host 0.0.0.0` note. `/api/options` 200; release smoke **28/28**.
      Secret scan clean — no configured key, `sk-` token, full URL, or userinfo in
      `/status`, `/options`, or `/provider-settings`; container logs carry 0 key
      tokens. **No live local server required for the automated tests** (urllib
      `urlopen` is monkeypatched; `/.dockerenv` faked).

47. **Local Model Manager — Slice 3: Local Models status panel (FRONTEND)** —
    branch `local-model-status-ui`. The §5 read-only operational view over the
    Slice 2 endpoints. Frontend + API client + docs/tests only; **no backend,
    Docker, pipeline, renderer, prompt, or provider-write changes.**
    - **API client helpers** (`frontend/src/api/client.js`): `getLocalModelStatus()`
      (`GET /api/local-model/status`, page-open read) and `checkLocalModelStatus()`
      (`POST /api/local-model/check`, the "Refresh" verb). Both go through the
      existing `requestJson`; neither sends a body, writes, or mutates settings.
    - **Pure status helpers** (`frontend/src/localModelStatus.js`, mirrors
      `shortcutStatus.js`): `localServerState` normalizes the DTO into
      `reachable | offline | not_configured | error | unknown` (reachable wins;
      `base_url_configured:false` or `provider_config` → not_configured;
      `local_offline` → offline; other classified error → error; not-reachable with
      no info → calm offline; missing/garbage status → unknown). Plus `stateBadge`
      (label + CSS-agnostic `tone`), `statusModels`/`statusModelCount`,
      `modelChips(limit=12)` (bounded list + overflow count), `statusLatencyMs`,
      `statusErrorMessage`, `statusNotes`, `statusActions` (enabled **only** when
      explicitly `true`), `findAction`, and `hasEnabledProcessControl` (the
      invariant guard). **Tolerates missing fields and an old backend.**
    - **Panel** (`frontend/src/components/LocalModelsPanel.jsx`): a rounded card
      with a live status pill, host-only base URL + in-Docker flag, a 4-up metrics
      strip (latency / models / default / selected), bounded model chips
      (selected highlighted, `+N more` overflow), a redacted offline/error message,
      a **first-class** offline/not-configured troubleshooting block (start the
      server, confirm `…/v1/models`, the `--host 0.0.0.0` Docker-host note, then
      Refresh), backend `notes`, a **Refresh status** button (loading state, calls
      `/check`, never saves/starts), an "Edit local provider settings" link, and the
      disabled **Copy start command — Planned** chip from the backend `actions`. If
      the status **request** itself fails (e.g. an old backend with no endpoint) it
      shows a calm "status unavailable" state instead of crashing.
    - **Providers integration** (`ProviderSettingsWorkspace.jsx`): the panel mounts
      under the provider cards; the edit link scrolls the `#provider-card-local`
      card into view with a brief `sg-card-flash` highlight (cosmetic CSS only).
      Providers stays the **single writer** — the panel never edits the base URL or
      model inline. No second nav item; lives on the existing **Models** page.
    - **Safety:** read-only; no start/stop/restart/process control anywhere
      (`hasEnabledProcessControl` is asserted false); no raw key or full URL (only
      the backend's host-only `base_url_host`); no stack traces; status never stored
      in shortcuts/jobs; selected provider/model never auto-changed. No new deps.
    - **Tests:** new `frontend/scripts/verify-local-model-status.mjs` (**47/47**,
      wired as `npm run test:local-model-status`) — state normalization (incl.
      missing-fields fallbacks), badge label/tone, model count + 12-chip display
      limit/overflow, latency/error/notes accessors, action enabled/disabled
      mapping, and the no-enabled-process-control invariant. Backend suites
      unchanged: `test_local_model_status.py` (17/17),
      `test_provider_fetch_models.py` (16/16), `test_provider_settings_store.py`
      (26/26).
    - **Verified:** `compileall` OK; `npm run build` OK (1601 modules); harness
      47/47; `docker compose config` exit 0; image built; container **healthy**.
      Live with **no** local server: `GET /api/local-model/status` returns HTTP 200
      `reachable:false`, `error.category:"local_offline"`, `latency_ms:null`,
      host-only `host.docker.internal`, and the `--host 0.0.0.0` note (panel renders
      the calm offline state). `/api/options` 200; release smoke **28/28**. Secret
      scan **clean** — no `.env` key value in the served JS bundle, `/status`,
      `/options`, or `/provider-settings`; container logs carry 0 key tokens.

48. **Local Model Manager — Slice 4: command-helper profiles / Copy start command**
    — branch `local-model-command-helper`. The §9 command-profile helper: a safe,
    copyable `llama-server` start command the operator runs **manually** outside the
    app. **Command helper only — the app never executes it; no process spawn,
    start/stop, host companion, GGUF scan, or arbitrary shell.** No Docker, pipeline,
    renderer, prompt, large-PDF, or Shortcut Inspector changes; no provider-write
    behavior change; no new deps.
    - **Backend** (`pipeline/provider_config.py` + `api/server.py`): read-only
      `GET /api/local-model/command-profile` → `get_local_model_command_profiles()`.
      Response: `{ok, provider, in_docker, base_url_host, profile, profiles[],
      notes[]}`; each profile `{id, label, description, command, argv[],
      placeholders{model_path}, warnings[]}`. Two static profiles:
      `llama_server_default` (GPU offload, `--n-gpu-layers 999`, `-c 8192`) and
      `llama_server_cpu` (CPU only, `-c 4096`), both `--host 0.0.0.0 --port 8080`.
      `argv` is built from a **fixed flag whitelist** with literal values; the only
      substitution token is `{model_path}` → the placeholder `/path/to/model.gguf`
      (no host filesystem read, no request input). The display `command` is rendered
      from `argv` via `shlex.quote`. **No subprocess/spawn anywhere; no raw key;
      host-only URL.** `--threads`/`--flash-attn` intentionally omitted from defaults.
    - **Frontend**: `getLocalModelCommandProfile()` client helper + pure
      `frontend/src/localModelCommand.js` (`normalizeProfile`, `commandProfiles`,
      `defaultProfile`, `profileById`, `commandAvailable`, `copyButtonLabel`,
      `commandNotes`) + a `CommandHelper` block in `LocalModelsPanel.jsx`: profile
      chips (when >1), a selectable command code block, a **Copy command** button
      (`navigator.clipboard` + manual "select & copy" fallback on failure), the
      static warnings, and "run on your host… then Refresh status." **Prominent**
      (expanded) when offline/not-configured, **secondary** (collapsed `<details>`)
      when reachable. The deferred `copy_start_command` "Planned" chip is suppressed
      (the real helper supersedes it); the Slice 2 status DTO is unchanged. **No
      Start/Stop button; nothing executes.**
    - **Tests:** new `test_scripts/test_local_model_command_profile.py` (**13/13**) —
      shape, placeholder path, host/port, warnings, no-key + no-URL leak with a stored
      key, no-write, no-spawn (source inspection + `subprocess.Popen` monkeypatch
      trip), status unchanged. New `frontend/scripts/verify-local-model-command.mjs`
      (wired as `npm run test:local-model-command`) — normalization/selection, copy
      gating, deterministic command, warnings/notes, label states, no execute/start
      export. Slice 2/3 suites unchanged: `test_local_model_status.py` (17/17),
      `verify-local-model-status.mjs` (47/47), `test_provider_fetch_models.py`
      (16/16), `test_provider_settings_store.py` (26/26).
    - **Verified:** `compileall` OK; `npm run build` OK; harnesses green; Docker
      build + container **healthy**; `GET /api/local-model/command-profile` 200 with
      the placeholder command; `/api/local-model/status` + `/api/options` 200;
      release smoke green. Secret scan **clean** — no key in the endpoint, served JS,
      `/options`, `/provider-settings`, or container logs.

49. **Local Model Manager — Slice 5: Phase-1 validation / docs reconciliation
    (DOCS-ONLY)** — branch `docs-validate-local-model-manager-phase1` (cut from
    `chrome-renderer-v1` @ `e399f09`). A verification + docs pass over the whole LMM
    Phase 1 (Slices 1→4). **No feature work, no refactor, no process spawn, no
    start/stop, no host companion, no GGUF browsing, no Docker config change, no
    provider-settings write-behavior change. No code changed.**
    - **Deliverable:** new `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md` +
      reconciled `CURRENT_TASK.md`, `NEXT_CHAT_HANDOFF.md`, `PROJECT_CONTEXT.md`,
      `LOCAL_MODEL_MANAGER_DESIGN.md`. No `DECISIONS.md` change — validation surfaced
      no non-obvious rule not already recorded.
    - **Static checks PASS:** `compileall` OK; `test_local_model_status.py` 17/17;
      `test_local_model_command_profile.py` 13/13; `test_provider_fetch_models.py`
      16/16; `test_provider_settings_store.py` 26/26; `npm run build` OK;
      `npm run test:local-model-status` + `npm run test:local-model-command` green.
    - **Docker/smoke PASS:** `compose config`/`build`/`up` OK (container **healthy**);
      `/api/health` `{"ok":true}`; `/api/local-model/status`, `/command-profile`, and
      `/api/options` all 200; release smoke **28/28**.
    - **Live API PASS (no local server running):** `/status` → 200, `ok:true`,
      `reachable:false`, `error.category:"local_offline"` (redacted message), no raw
      key, host-only URL, `copy_start_command` disabled. `/command-profile` → 200 with
      both whitelisted profiles, the `/path/to/model.gguf` placeholder, `--host
      0.0.0.0 --port 8080`, no real host paths, no secrets, no execution.
    - **No-process-execution PROOF:** the only `subprocess`/`spawn`/`os.system`
      matches in the LMM code are **comments asserting absence**; the one real
      `subprocess` reference is the pre-existing PDF/render pipeline, untouched. The
      command helper returns strings/argv only (`shlex.quote` is display-quoting).
    - **Secret-leak scan CLEAN:** real `.env` keys (never printed) + a generic `sk-`
      pattern found **0** hits in `/local-model/status`, `/command-profile`,
      `/options`, `/provider-settings`, container logs, and changed docs. The lone JS
      match was an investigated **false positive** — `LOCAL_LLM_API_KEY` is a 4-char
      placeholder (`none`) coinciding with minified React's `display:"none"`; the real
      DeepSeek/Qwen keys appear nowhere.
    - **UI (source + harness + smoke) PASS:** the panel mounts in Providers/Models;
      offline state is safe/readable; Refresh works; Edit-settings scrolls/highlights
      `#provider-card-local`; the command helper appears and is clearly manual; Copy
      has a manual fallback; **no Start/Stop/Restart**, **no file/GGUF picker**;
      existing provider settings unaffected. (Full pixel-level browser click-through
      not run — proven structurally; optional human polish pass deferred.)
    - **Outcome:** **Phase 1 COMPLETE + validated; no bugs found; no code changed.**
      Recommended next: **Ask Your Guide local-only chat**, or host-companion DESIGN
      (sign-off-gated). Safe to merge (docs-only).

50. **Ask Your Guide — Slice 1: design (DOCS-ONLY)** — branch `ask-your-guide-design`
    (cut from `chrome-renderer-v1` @ `95132fe`). A design-first definition of a
    dedicated **Ask Your Guide** workspace where the user selects a generated
    guide/job and chats with it using a **local** model. **No backend endpoint, no
    frontend UI, no pipeline/extraction change, no provider-settings change, no LMM
    change, no new dependency. No code changed.**
    - **Deliverable:** new `docs/ASK_YOUR_GUIDE_DESIGN.md` + reconciled
      `CURRENT_TASK.md`, `NEXT_CHAT_HANDOFF.md`, `PROJECT_CONTEXT.md`, and three
      `DECISIONS.md` entries.
    - **Dedicated workspace, not a Library button.** `AskGuideWorkspace` is a
      first-class page/tab alongside Builder/Library/Styles/Providers — guide+session
      picker (left), chat (center), sources/context/citations panel (right/drawer).
      Library/Job Details may *later* deep-link "Open in Ask Your Guide"; the
      workspace is primary.
    - **Local-only in v1.** Resolves the **`local` provider only**, **status-gated**
      on LMM Phase 1 (`GET /api/local-model/status`); offline → first-class offline
      state + the LMM command helper, chat disabled. **No DeepSeek/Qwen/cloud
      fallback**; a hosted "ask any provider" mode is a future **explicit** opt-in.
      Model-agnostic (any OpenAI-compatible local server); long-context / thinking /
      multimodal used only when the server advertises them (multimodal deferred).
    - **Context manager is mandatory** (no "send the whole guide + all attachments +
      all history every turn"): chunk `clean.md`/`extracted.txt` with `## Page N` /
      heading **citation anchors**, a **dependency-free lexical** index cached per
      `(job_id, content_hash)`, **budgeted retrieval** (reserve answer + system rules
      + recent chat, fill the remainder), a **rolling chat summary** + recent-turn
      window + pinned facts, visible prep progress, and graceful "too large for this
      model" failure.
    - **Accuracy/citation contract:** answer from guide/source/uploads first; cite
      page/section; say so when not in the material; never invent
      facts/formulas/pages/dates; distinguish "from your guide" vs general knowledge;
      explain conflicts; ask when ambiguous; show + check calculations; mark
      high-vs-uncertain exam advice. A later slice **validates** emitted citations
      against in-context labels.
    - **Storage (conservative):** per-guide sessions under
      `jobs/<id>/ask/sessions/<sid>/` (metadata + history + uploads + cache);
      extra uploads **session-scoped** (never merged into the original job); chat
      history clearable/deletable; **never** auto-exported; **no secrets stored**.
    - **Endpoints proposed (sliceable, all local-only + redacted):** `GET
      /api/ask/jobs`, `GET /api/ask/jobs/{id}/context`, `POST …/prepare`, `POST
      …/sessions`, `GET /api/ask/sessions/{sid}`, `POST …/message`, `POST
      …/attachments`, `DELETE …/sessions/{sid}` + `…/history`. Every route reads job
      artifacts **read-only** (never `save_clean_md`, never creates a generation
      job), reuses `extract.py` for extra uploads, and leaks no key/full URL.
    - **10-slice build plan** (design → context inventory → chunking → local chat →
      workspace shell → chat UI → extra uploads → long-chat memory → accuracy/polish →
      optional multimodal), each with scope/files/tests/acceptance/non-goals.
    - **Outcome:** design complete; **NEXT = Ask Slice 2 (backend context inventory
      endpoint)**. Safe to merge (docs-only).

51. **Ask Your Guide — Slice 2: backend context inventory endpoint (BACKEND ONLY)**
    — branch `ask-context-inventory` (cut from `chrome-renderer-v1`, trunk incl.
    `95132fe` + `af0ec0e`). Two **read-only** inventory/context-summary endpoints for
    generated guides — **no chat, no chunking, no retrieval/indexing, no model call,
    no local-model call, no cloud fallback, no session storage, no extra uploads, no
    frontend, no mutation of any original job artifact.**
    - **New thin reader `pipeline/ask_inventory.py`** — read-only artifact reader:
      `has_generated_guide(job)` (eligibility = `clean.md` exists),
      `guide_inventory(job)` (`clean_md_present` + char count + ATX heading count),
      `source_inventory(job)` (`extracted_txt_present` + char count + `## Page N`
      anchor count). Returns **counts/booleans only — never a guide/source body**;
      never writes, never calls `save_clean_md`, no secret surface.
    - **`GET /api/ask/jobs`** lists **only Ask-eligible jobs** (those with a generated
      `clean.md`); guide-less / failed / incomplete jobs (no `clean.md`) are **filtered
      out**, not returned as ineligible. Reuses the existing `JOBS_DIR.glob("*/job.json")`
      manifest listing + the same newest-first / favorites-float ordering as `/api/jobs`.
      Each row is a curated, redacted picker summary: `id`, `title`, `status`,
      `created_at`, `updated_at`, `style` (`prompt_name`), `generator_preset`,
      `provider`, `model`, `favorite`, `attachment_summary`, `guide_available`,
      `source_available`.
    - **`GET /api/ask/jobs/{id}/context`** returns a per-job readiness + source
      inventory: `guide{clean_md_present,char_count,heading_count}`,
      `source{extracted_txt_present,char_count,page_anchor_count}`, redacted
      `attachments[]` (filename/extension/mode/status/extracted_chars/truncated/
      warnings), `attachment_summary`, `page_selections`, and a
      `readiness{status:"ready"|"not_ready", ready:bool, reasons:[]}` object. An
      **unknown job → 404** (via the existing `_get_job` guard); an existing but
      guide-less job → `200` `not_ready` (not a 404).
    - **Redacted by construction.** Both routes build on the existing
      `_safe_manifest` / `_safe_attachment_metadata` / `_attachment_summary` /
      `_safe_page_selections` helpers and emit an **explicit field whitelist** —
      nothing from the manifest is passed through verbatim — so **no raw API key,
      `api_key`/`Authorization` field, `sk-` value, full base URL (scheme/host), or
      filesystem path** can ride along, and **no guide/source body** is ever returned.
      Registered well before the SPA mount (and the parametric `/api/jobs/{job_id}`
      catch-all — different prefix), so `/api/*` keeps winning.
    - **Verified** (`python -m compileall api pipeline` OK; `docker compose config`
      exit 0; image rebuilt + container healthy): focused
      `test_scripts/test_ask_context_inventory.py` **50/50 in Docker** (pure reader +
      both endpoints: eligible appears / guide-less absent / counts + page-anchor +
      attachment fields + page selections / unknown→404 / redaction scan / read-only
      sha256 of `clean.md`+`extracted.txt`+`job.json` unchanged). **Live** seeded-job
      proof: `/api/ask/jobs` + `/context` return the curated fields; a raw-response
      secret scan over both endpoints found **no** `sk-`/`api_key`/`Authorization`/
      `https://`/`/home/secret`/`base_url` leak even though the seeded manifest +
      attachment carried a planted `sk-live-…` key, a full base URL, and a host path.
      Release smoke unchanged. **No frontend file touched** (build not needed).

52. **Ask Your Guide — Slice 3: backend context preparation / chunking (BACKEND
    ONLY)** — branch `ask-context-prepare` (cut from `chrome-renderer-v1`, trunk
    incl. `af0ec0e` + `2634f63`). Turns a job's generated `clean.md` + optional
    `extracted.txt` into a deterministic, citation-labelled chunk index plus a
    dependency-free lexical index, cached per `(job_id, content_hash)`. **No chat,
    no retrieval/query endpoint, no model call, no local-model call, no cloud/key
    read, no sessions, no extra uploads, no frontend, no new dependency, no mutation
    of any original job artifact.**
    - **New helper `pipeline/ask_context.py`** (stdlib only). `prepare_context(job)`
      reads `clean.md` (required) + `extracted.txt` (optional), computes a content
      hash over their bytes, and builds OR reuses the cache. Chunking is
      **deterministic**: split on markdown heading boundaries (guide) / `## Page N`
      anchors (source), then pack paragraphs up to ~650-token (`chars/4`) targets
      with an ~800-token hard ceiling; a single oversized paragraph hard-splits.
      **No overlap in v1** (paragraph/heading boundaries only) — recorded in
      `DECISIONS.md`. Each chunk carries `id`, `source_type` (`guide`|`source`),
      `label` (**nearest heading** for guide / **`Page N`** for source), `page`,
      `char_count`, `approx_tokens`, lexical `terms` (freq map), and `text` (cache
      only). Index also stores `doc_freq` for later BM25-style scoring.
    - **`POST /api/ask/jobs/{id}/prepare`** (registered before the SPA mount). Unknown
      job → **404** (`_get_job` guard). Guide-less existing job → **200 `ready:false`**
      with a reason (mirrors the Slice 2 context endpoint, not a 404). Eligible job →
      builds/reuses the cache and returns an **explicit whitelist**: `job_id`, `ready`,
      `cache_status` (`built`/`hit`/`rebuilt`), `content_hash`, guide/source/total
      chunk counts, a `citation_summary` (bounded heading + page-number samples), and
      a **job-relative** `cache_relpath`. **Idempotent**: an unchanged guide+source is
      a `hit` that rewrites nothing; a content change (`clean.md` OR `extracted.txt`)
      rebuilds; a corrupt/stale cache rebuilds safely instead of crashing.
    - **Cache layout:** `jobs/<job_id>/ask/cache/context_index.json` — fenced inside
      the job dir (`_ensure_fenced`), written atomically (temp file + `os.replace`),
      safe to delete/rebuild. The cache file holds chunk text + terms (Slice 4 needs
      them) but **only** the whitelisted top-level keys — it never touches the manifest,
      so no secret/key/URL/host-path/unrelated field can enter it. The prepare response
      never returns guide/source body, chunk `text`, keys, URLs, or host paths.
    - **Verified** (`python -m compileall api pipeline` OK; `docker compose config`
      exit 0; container healthy): focused `test_scripts/test_ask_context_prepare.py`
      **58/58 in Docker** (pure chunker + endpoint: build→hit→rebuild on guide/source
      change, heading + `## Page N` label preservation, corrupt-cache recovery, 404,
      guide-less, cache-key whitelist, response + cache secret scans, and sha256
      immutability of `clean.md`/`extracted.txt`/`job.json`). **Slice 2 regression**
      `test_ask_context_inventory.py` **50/50** unchanged. **Live** proof on a real
      eligible job: `prepare` built 20 guide chunks, second call returned `hit`, raw
      response + on-disk cache secret-scanned clean (no `sk-`/`api_key`/`Authorization`/
      `https://`/host path/chunk `text`). **No frontend/shared file touched** (build not
      required).

53. **Ask Your Guide — inserted Slice 4: first-class workspace shell (FRONTEND
    ONLY)** — branch `ask-workspace-shell` (cut from `chrome-renderer-v1` at
    `a29a405`). Inserts the visible product shell before backend chat/session
    complexity: a top-level `Ask Guide` workspace in the sidebar with left guide
    picker, center disabled chat/readiness panel, and right context/local-model rail.
    **No backend route changed. No chat endpoint, no `/api/ask/sessions`, no model call,
    no local-model call, no cloud fallback, no extra uploads, no chat history
    persistence, no artifact mutation, no dependency.**
    - **Frontend API helpers** in `frontend/src/api/client.js`: `getAskJobs`,
      `getAskJobContext`, `prepareAskJobContext`, consuming the existing
      summary-only endpoints from Ask Slices 2/3. Existing LMM helpers continue to
      consume `GET /api/local-model/status` and `GET /api/local-model/command-profile`.
    - **New `frontend/src/components/AskGuideWorkspace.jsx`**: fetches eligible
      generated guides from `GET /api/ask/jobs`, selects a guide and loads
      `GET /api/ask/jobs/{id}/context`, shows guide/source readiness counts
      (guide chars/headings, source chars/page anchors), attachment filenames/modes/
      warnings, page selections, provider/model/preset/style metadata, and reasons
      for not-ready jobs. The center panel has a disabled composer and explicit
      "chat lands next" copy. `Prepare context` calls
      `POST /api/ask/jobs/{id}/prepare` and shows cache status (`built`/`hit`/
      `rebuilt`), total/guide/source chunk counts, and bounded citation samples.
    - **Local model status**: the rail reads LMM status and reuses the existing
      `localModelStatus.js`/`localModelCommand.js` helpers plus the exported
      `CommandHelper` renderer from `LocalModelsPanel.jsx`. Offline/unconfigured
      states show the manual command helper; reachable states show safe model count,
      default/selected model, latency, and bounded model chips. There are **no**
      start/stop/process-control buttons.
    - **Security/redaction proof in the UI layer**: new pure
      `frontend/src/askGuide.js` helper renders only summary fields and defensively
      basenames attachment/page-selection filenames. It never renders guide/source
      bodies, chunk text, full URLs, raw keys, or host filesystem paths; browser state
      holds only endpoint summaries. Build output is generated by Vite and no new
      served secret surface is introduced.
    - **Verified**: `npm run test:ask-guide` (all helper checks pass, including
      POSIX/Windows path stripping), `npm run test:local-model-command` pass,
      `npm run test:local-model-status` pass, `npm run build` pass. Backend files were
      not touched, so `compileall` was not required for this slice. Ask backend
      regression tests are still expected before merge handoff (inventory + prepare).

54. **Ask Your Guide — backend local chat API (BACKEND ONLY)** — branch
    `ask-local-chat-api`. Adds minimal Ask chat session storage and local-only chat
    generation:
    - **Endpoints:** `POST /api/ask/jobs/{job_id}/sessions` creates
      `jobs/<job_id>/ask/sessions/<session_id>/session.json` + `history.jsonl` for
      jobs with generated `clean.md` (unknown job → 404; guide-less job →
      safe `not_ready` 409); `GET /api/ask/sessions/{session_id}` returns safe
      metadata + bounded history; `POST /api/ask/sessions/{session_id}/message`
      validates input, status-gates on LMM/local availability, retrieves, calls the
      local provider, persists JSONL history, and updates session metadata.
    - **Retrieval/prompting:** reuses/refreshes the Slice 3 prepared cache
      synchronously via `ask_context.prepare_context()` (writes only the Ask cache,
      never original artifacts), then dependency-free lexical scores over cached
      chunk term frequencies + `doc_freq`. Query = current question plus a tiny recent
      user-history window. Retrieval is bounded to top 8 chunks and an approximate
      3k-token pool (`chars/4`) with room reserved for system rules, recent chat, and
      answer. Responses return answer text, allowed citation labels, safe chunk
      metadata only (no chunk text), session id, and safe local model status.
    - **Local-only proof:** message calls `get_local_model_status()` first; offline /
      unconfigured / unreachable returns structured `local_offline` without building
      provider config or calling the model. The generation call uses
      `build_provider_config("local", selected_model, max_tokens=...)` and
      `generate_chat_completion`; focused tests assert no DeepSeek/Qwen/cloud fallback
      path is used.
    - **Security/storage:** session ids are opaque `ask_<uuidhex>` values and session
      lookup is fenced under each parent job. `session.json` is atomic; history appends
      JSONL. Raw prompts are never stored or returned. Obvious `sk-*` keys,
      Authorization bearer headers, and full `http(s)://` URLs are masked before Ask
      cache/session persistence and responses. `session.json`/`history.jsonl` are not
      exported by existing export endpoints.
    - **Artifact immutability:** tests sha256 `clean.md`, `extracted.txt`, and
      `job.json` before/after session creation and message calls; all unchanged. The
      slice never calls `JobManager.save_clean_md`, never creates generation jobs, and
      never rewrites guide/source/manifest artifacts.
    - **Verified:** `test_scripts/test_ask_local_chat.py` **40/40** in the Docker
      image with the repo mounted; Ask inventory regression
      `test_ask_context_inventory.py` **50/50**; Ask prepare regression
      `test_ask_context_prepare.py` **58/58**; `python -m compileall api pipeline`
      pass; `docker compose config >/tmp/compose-check.txt` exit 0; release smoke
      **28/28** against the live container. Docker image rebuilt + app container
      healthy. **Frontend build not required by the slice** because no frontend/shared
      files were touched (the Docker rebuild reused the existing frontend build layer).

55. **Ask Your Guide — frontend chat UI wiring (FRONTEND)** — branch `ask-chat-ui`.
    Wires the visible Ask workspace to the already-landed local-only chat API:
    - **Endpoints consumed:** `GET /api/ask/jobs`, `GET /api/ask/jobs/{job_id}/context`,
      `POST /api/ask/jobs/{job_id}/prepare`, `POST /api/ask/jobs/{job_id}/sessions`,
      `GET /api/ask/sessions/{session_id}`, `POST /api/ask/sessions/{session_id}/message`,
      `GET /api/local-model/status`, `POST /api/local-model/check`, and
      `GET /api/local-model/command-profile`.
    - **UX:** guide selection and context inventory remain visible; Prepare Context is
      explicit and still works; chat sessions are created lazily on first send, then
      loaded before messaging. The composer enables only when a guide is selected,
      context is ready, prepare has succeeded, the local model is reachable, and no
      send is in flight. Message success appends the user turn + assistant answer and
      renders only backend-returned citation labels and safe retrieved chunk metadata.
      Failures keep the draft available for retry; `local_offline` shows the existing
      LMM command helper and keeps the composer disabled.
    - **Security:** no `dangerouslySetInnerHTML`; answers render as plain text with
      preserved whitespace. Frontend normalizers defensively redact obvious `sk-*`
      keys, Authorization bearer headers, full `http(s)://` URLs, and POSIX/Windows
      host paths before storing/rendering. The UI stores only safe `session_id`,
      session metadata, bounded message history, citation labels, retrieved chunk
      metadata (id/source/page/tokens/score), and safe local model fields. It never
      renders guide/source bodies, chunk text, raw prompts/system prompts, raw keys,
      full URLs, or filesystem paths, and it does not persist chat to browser storage.
    - **Non-goals preserved:** no backend chat behavior change, no extra uploads, no
      chat export, no backend citation-validation slice, no long-chat rolling-summary
      UI, no streaming, no cloud fallback, no hosted provider selector, no DeepSeek/Qwen
      fallback, no local model process control, no provider settings writes, and no new
      dependencies.
    - **Verified:** `npm run test:ask-guide` pass (45/45 helper checks),
      `npm run build` pass (existing Vite chunk-size warning only),
      `npm run test:local-model-command` pass, `npm run test:local-model-status` pass,
      `test_scripts/test_ask_context_inventory.py` **50/50** in Docker with the repo
      mounted, `test_scripts/test_ask_context_prepare.py` **58/58** in Docker,
      `test_scripts/test_ask_local_chat.py` **40/40** in Docker, and
      release smoke **28/28**. `docker compose config >/tmp/compose-check.txt` exit 0.
      Backend/shared Python was not touched, so `python -m compileall api pipeline` was
      not required.

56. **Ask Your Guide — chat polish + emitted-citation validation** — branch
    `ask-chat-polish-citations`.
    Tight backend + frontend polish over the already-working local Ask chat flow:
    - **Backend citation validation:** `POST /api/ask/sessions/{session_id}/message`
      now post-validates bracket-style citations emitted by the local model against
      the exact allowed citation labels retrieved for that turn. Ask-looking
      unsupported citations (for example `[Guide Fake Topic]`) are stripped from the
      answer and reported; normal bracketed prose that does not look like an Ask
      citation is preserved. Responses include `citations_allowed`,
      `citations_used`, `citations_unsupported`, and
      `citation_validation: {ok, unsupported_count}`. Trusted `citations` now mirror
      used/validated citations, not unsupported labels.
    - **Prompt cleanup:** the answer rules still require grounding and exact allowed
      labels, but now prefer citations at paragraph ends or a short sources line
      instead of noisy citations after nearly every sentence.
    - **Frontend polish:** guide cards format attachment summaries as safe human text
      instead of `Guide only · [object Object]`; the workspace shows a friendly
      session-active label with only a short suffix instead of the full technical
      `ask_...` id; assistant answers render through a tiny inert subset renderer for
      headings, bold, numbered/bulleted lists, line breaks, and fenced blocks (no
      `dangerouslySetInnerHTML`, no markdown dependency); escaped math dollars are
      cleaned for readability.
    - **Sources/citations UX:** citation chips come from backend machine-readable
      used citations; unsupported citations show a subtle warning and are not rendered
      as trusted chips. Retrieved chunk metadata remains available but is collapsed
      behind `Sources used` / `Show retrieved chunks` disclosures by default. Chunk
      text is still never rendered.
    - **Security/non-goals:** no raw prompts/messages are logged by the new code, raw
      prompts are not returned, full chunk text is not returned to the UI, and the
      existing redaction of obvious `sk-*` keys, Authorization bearer headers, full
      URLs, and host paths remains in place. Local-only enforcement is unchanged. No
      extra uploads, no streaming, no cloud fallback, no hosted provider selector, no
      DeepSeek/Qwen fallback, no rolling summary, no multimodal, no local model
      process control, no provider settings writes, and no new dependencies.
    - **Verified:** `npm run test:ask-guide` pass (58/58 helper checks),
      `npm run build` pass (existing Vite chunk-size warning only),
      `npm run test:local-model-command` pass, `npm run test:local-model-status`
      pass, `python test_scripts/test_ask_local_chat.py` pass for pure checks
      (14/14; endpoint portion skipped on the host because FastAPI is not installed),
      `python test_scripts/test_ask_context_inventory.py` pass for pure checks
      (11/11; endpoint portion skipped for missing host FastAPI),
      `python test_scripts/test_ask_context_prepare.py` pass for pure checks (28/28;
      endpoint portion skipped for missing host FastAPI), and
      `python -m compileall api pipeline` pass. `docker compose config
      >/tmp/compose-check.txt` exit 0. A running Docker image was healthy, but it did
      not include `test_scripts/`, so in-container endpoint reruns were unavailable
      without copying files into the container.

57. **Ask Your Guide — session management UI/API** — branch
    `ask-session-management`.
    Adds safe controls for managing persisted Ask sessions without changing local chat
    generation:
    - **Backend endpoints:** `GET /api/ask/jobs/{job_id}/sessions` lists safe
      summaries for one eligible guide (session id, job id, title, created/updated,
      cheap message count, and a redacted bounded last-message snippet). Unknown job
      returns 404; an eligible job with no sessions returns an empty list. `DELETE
      /api/ask/sessions/{session_id}/history` clears `history.jsonl`, keeps
      `session.json` and the same session id, updates metadata, and does not touch
      the context cache. `DELETE /api/ask/sessions/{session_id}` deletes only that
      fenced session directory and returns `{deleted:true, session_id}`.
    - **Existing behavior preserved:** `POST /api/ask/jobs/{id}/sessions`, `GET
      /api/ask/sessions/{id}`, and `POST /api/ask/sessions/{id}/message` keep their
      prior contracts. Local-only status gating, retrieval, prompt assembly, citation
      validation, and model-call behavior are unchanged.
    - **Frontend UX:** the Ask workspace now lists sessions for the selected guide in
      a compact right-rail panel, can switch to any listed session, starts a new chat
      without re-preparing context, keeps lazy session creation for first send when
      no session is active, and adds confirm-gated **Clear chat** / **Delete** controls
      for the active session. Clear keeps the guide, prepared context, selected
      session, and draft flow intact; delete removes the session from the list and
      loads the next newest session when available, otherwise returns to no active
      chat for that guide.
    - **Security/non-goals:** summaries and UI helpers render only bounded redacted
      metadata/snippets. No raw prompts, full answers in list summaries, chunk text,
      guide/source bodies, keys, Authorization headers, full URLs, or filesystem paths
      are returned/rendered by the new surfaces. No browser storage is used. No extra
      uploads, chat export, streaming, cloud fallback, hosted selector, DeepSeek/Qwen
      fallback, long-chat rolling summary, multimodal, local model process control,
      provider settings writes, or new dependencies.
    - **Verified:** `npm run test:ask-guide` pass (67/67 helper checks),
      `npm run build` pass (existing Vite chunk-size warning only), `python
      test_scripts/test_ask_local_chat.py` pass for pure checks (27/27; endpoint
      portion skipped on the host because FastAPI is not installed), `python
      test_scripts/test_ask_context_inventory.py` pass for pure checks (11/11;
      endpoint portion skipped for missing host FastAPI), `python
      test_scripts/test_ask_context_prepare.py` pass for pure checks (28/28; endpoint
      portion skipped for missing host FastAPI), `python -m compileall api pipeline`
      pass, `npm run test:local-model-command` pass, `npm run test:local-model-status`
      pass, release smoke **28/28**, and `docker compose config
      >/tmp/compose-check.txt` exit 0. The running Docker image was healthy but did
      not include `test_scripts/`, so in-container endpoint-script reruns were not
      available without copying test files into the container.

58. **Ask Your Guide — chat math/source visual polish** — branch
    `ask-chat-math-source-polish`.
    Frontend-only readability polish for the existing local Ask chat UI:
    - **Code files changed:** `frontend/src/askGuide.js`,
      `frontend/src/components/AskGuideWorkspace.jsx`, and
      `frontend/scripts/verify-ask-guide.mjs`.
    - **Math answer rendering:** added inert math-aware answer parsing for
      `$$...$$`, `\[...\]`, `\(...\)`, and escaped-dollar inline math. Display math
      renders as readable monospace blocks preserving line breaks; inline math renders
      as small monospace chips. No `dangerouslySetInnerHTML`, no markdown dependency,
      no KaTeX/MathJax, and no new dependency.
    - **Source/citation affordances:** trusted backend-used citations now appear in a
      clearer **Sources used** section. Unsupported citations remain warning-only and
      are not trusted chips. Retrieved chunk metadata remains collapsed by default
      and shows cleaner label/type/page/score/token rows. Chunk text is still never
      rendered.
    - **Behavior preserved:** local-only Ask behavior is unchanged. Session
      management behavior is unchanged. No backend retrieval, prompt assembly,
      model-call, citation-validation, session, clear/delete, or lazy session
      creation logic changed. No extra uploads, streaming, hosted/cloud Ask mode,
      DeepSeek/Qwen fallback, rolling summary, multimodal, local model process
      control, provider settings writes, browser storage, or new dependencies.
    - **Verified:** root `npm run test:ask-guide` failed because the root package has
      no such script. `frontend` `npm run test:ask-guide` passed. `frontend`
      `npm run build` passed with the existing Vite chunk-size warning. `frontend`
      `npm run test:local-model-command` passed. `frontend`
      `npm run test:local-model-status` passed. `python -m compileall api pipeline`
      passed. `python test_scripts/test_ask_local_chat.py` passed pure checks;
      endpoint section skipped because FastAPI is unavailable on the host. `python
      test_scripts/test_ask_context_inventory.py` passed pure checks; endpoint
      section skipped because FastAPI is unavailable on the host. `python
      test_scripts/test_ask_context_prepare.py` passed pure checks; endpoint section
      skipped because FastAPI is unavailable on the host. `python
      test_scripts/smoke_release.py` passed **28/28**. `docker compose config
      >/tmp/compose-check.txt` exit code 0.
    - **Manual validation follow-up:** browser validation after this slice found the
      empty local-model response guard bug recorded in DONE #59.

59. **Bugfix — Ask empty local-model response guard** — branch
    `ask-empty-response-guard`.
    Discovered during manual Ask UI validation after the math/source polish slice.
    - **Bug:** a browser Ask message returned
      `POST /api/ask/sessions/{session_id}/message` → 500. The traceback showed
      `generate_chat_completion` raised
      `RuntimeError("LLM returned an empty response.")`; Ask did not catch that
      exception, so FastAPI returned raw 500 text.
    - **Fix:** `pipeline/ask_sessions.py` now catches the narrow empty local-model
      RuntimeError response case and returns a safe structured `provider_error`
      response with `error.category: provider_empty_response` and a retryable,
      user-safe message.
    - **History behavior:** the failed turn does not append a successful
      user/assistant message to history.
    - **Behavior preserved:** local-only behavior is unchanged. No retrieval, prompt
      assembly, model fallback, citation validation, session management, clear/delete,
      provider settings, streaming, uploads, rolling summary, multimodal, or
      process-control behavior changed.
    - **Tests/validation:** `test_scripts/test_ask_local_chat.py` updated with
      focused coverage. `python test_scripts/test_ask_local_chat.py` passed 38/38;
      endpoint section skipped because plain Python lacks FastAPI. `python
      test_scripts/test_ask_context_inventory.py` passed 11/11; endpoint skipped for
      missing FastAPI. `python test_scripts/test_ask_context_prepare.py` passed
      28/28; endpoint skipped for missing FastAPI. `.venv/bin/python -m compileall
      api pipeline` passed. `npm --prefix frontend run test:ask-guide` passed.
      `npm --prefix frontend run build` passed. `docker compose config
      >/tmp/compose-check.txt` exit code 0. `.venv/bin/python
      test_scripts/smoke_release.py` ran 27/28 with one existing-looking non-Ask
      outline-ordering failure.
    - **Manual validation:** Docker app rebuilt/restarted and healthy. The original
      empty local-model behavior was not reproducible, but the simulated regression
      is now covered.

60. **Compatibility fix — Ask local thinking-model `/no_think` control** — branch
    `ask-local-direct-answer-guard`.
    Follow-up to manual browser validation of DONE #59.
    - **Bug:** the previous direct-answer system rules were not strong enough for the
      full Ask prompt with the Gemma llama-server setup. The local model generated
      through the whole Ask response budget in hidden `reasoning_content` and
      returned no visible assistant content, producing `provider_empty_response`.
    - **Fix:** `pipeline/ask_sessions.py` keeps the direct visible-answer system
      rules and adds a standalone `/no_think` local thinking-model control only to
      the assembled model-facing user message, immediately before the final `User
      question:` block sent to `generate_chat_completion`.
    - **Model-only boundary:** `/no_think` is not appended to the saved raw user turn,
      not stored in `history.jsonl`, not returned by session load/list responses, not
      included in session summaries, and not rendered by the frontend. Citation and
      grounding rules are preserved.
    - **Tests/validation:** `python test_scripts/test_ask_local_chat.py` passed
      45/45 pure checks with endpoint skip because FastAPI is unavailable in this
      environment. `python test_scripts/test_ask_context_inventory.py` passed 11/11
      with endpoint skip. `python test_scripts/test_ask_context_prepare.py` passed
      28/28 with endpoint skip. `python -m compileall api pipeline` passed.
      `npm --prefix frontend run test:ask-guide` passed. `npm --prefix frontend run
      build` passed with the existing Vite large-chunk warning. `python
      test_scripts/smoke_release.py` passed 28/28. `docker compose config
      >/tmp/compose-check.txt` exit code 0.
    - **Manual/live validation:** Docker app rebuilt/restarted and healthy. Local
      model status from the container was reachable for
      `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`. A live Ask session
      `ask_7cec13974cbf48ccb7de71889c9a71e9` against job
      `20260605-181809-c768` returned `status: answered` with visible assistant
      content instead of `provider_empty_response`. Session load/list responses and
      persisted `history.jsonl` did not contain `/no_think`; container-side grep of
      that session/cache found no `/no_think`, `reasoning_content`, or
      `provider_empty_response`. Headless Chromium verified the rebuilt browser shell
      is served; a full browser click/send replay was not automated in this repo.

61. **Local Model Manager Phase 2G7 — operator setup docs + safe profile preset
    import** — branch `lmm-phase2g7-profile-presets-docs`. Added
    `docs/LOCAL_MODEL_MANAGER_OPERATOR_SETUP.md`, a Linux-first operator guide
    covering how to find `llama-server` (`command -v llama-server`,
    `readlink -f /proc/<pid>/exe`), approved model roots, companion JSON config,
    process runtime dir, token handling, safe CPU / low-memory GPU / balanced GPU
    profile examples, Unix socket Docker mount concept, backend env vars
    (`LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`,
    `LMM_COMPANION_TIMEOUT_SECONDS`), the real validation harness
    (`test_scripts/validate_lmm_real_llama_server.py`), troubleshooting, and
    Linux-first platform scope.
    - **Implemented optional `.ini` preset import** in
      `tools/local_model_companion/config.py` using Python stdlib
      `configparser` with interpolation disabled. Preset paths come only from
      explicit companion JSON (`profile_preset_files`), never from the frontend.
      Imported presets require `llama_server_executable` in companion JSON; the
      preset file cannot set executable/model paths or commands. Imported
      sections become normal `llama_server` profiles through the same whitelist
      schema used by JSON profiles.
    - **Rejected rather than ignored:** unknown preset keys, duplicate ids,
      `DEFAULT` values, invalid int/bool/enum/range values, env expansion,
      shell/path-like text, and command/args/shell/model_path/executable/
      free-form flag keys. CPU safe and GPU balanced defaults avoid
      `gpu_layers=999`.
    - **Docs reconciled:** `PROJECT_CONTEXT.md`, `NEXT_CHAT_HANDOFF.md`,
      `LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md`, and `DECISIONS.md` now record that
      CPU validation passed, full offload `gpu_layers=999` failed safely as
      `model_may_be_too_large` / CUDA OOM, profile presets/defaults are
      whitelist-based, app-suggested settings remain deferred, and `.ini` import
      is implemented.
    - **Scope preserved:** no app-suggested settings, AI-generated
      recommendations, Provider Settings writes, Ask changes, permanent Docker
      Compose changes, frontend UI changes, free-form flags, raw shell command
      execution, model download manager, host-gateway TCP, Docker socket,
      privileged container, host PID namespace, Windows/macOS implementation, or
      token/socket/absolute path/raw argv exposure.

## NEXT (in order)

> **Provider settings feature group is DONE through Slice 5** (DONE #32→#36):
> design (`978516e`) → backend store + safe endpoints (`1ba2b28`) → frontend
> Providers UI (`3024a33`) → runtime settings applied to live generation
> (`40df617`) → backend fetch-models endpoint (`6da944a`) → frontend Refresh
> Models UI (`61fb423`). Raw keys stay **server-side only**; `/api/options` and
> `/api/provider-settings` are **redacted**; `config/provider_settings.json` is
> non-secret (`0644`), `config/secrets.json` is secret-only (`0600`). Precedence:
> **per-job request > provider-settings default > `.env` > built-in**; generator
> presets **never hard-pin** provider/model (`model_hint` advisory), and an
> **explicit** preset sampling/thinking value overrides the stored runtime default.
> The **fetch-models endpoint** (DONE #35) is read-only and never auto-persists;
> the **Refresh Models UI** (DONE #36) fetches review-only model ids, stages new
> ids into draft `custom_models` via Add / Add all new, and requires an **explicit
> Save** to persist (after which `/api/options` exposes the saved custom models).
> Still deferred from provider settings: **encrypted-at-rest / OS keyring, `.env`
> import, the Local Model Manager (separate design-first feature), and the optional
> Builder "Provider default" thinking UI polish.**
>
> **Large-PDF core (DONE #27→#31) and Group C (C1→C5) also remain done.** The
> earlier "in-app provider settings — design-first" recommendation is now
> **completed and removed**. The only remaining math/PDF slice is **font-size
> rationalization** (cause C, CSS-only) — optional, not the headline.
>
> **Shortcut Inspector / Repair Loop is COMPLETE through Slice 3B** (DONE #39→#42,
> `a0f96d1`→`4458c9a`): backend read-only inspector + `validity`, read-only
> Inspector UI, repair preview/apply endpoints, and the repair UI. The earlier
> "shortcut inspector / repair loop — design/polish" recommendation is **done and
> removed** from this list. The provider-settings real-world validation pass also
> ran (see `docs/VALIDATION_PROVIDER_SETTINGS_LARGE_PDF.md`) and surfaced two
> already-fixed findings, so it is no longer a recommended next step either. The
> Shortcut Inspector itself was validated in
> `docs/VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md` (docs-only; no code changed).

> **LMM Phase 1 is DONE through validation** (Slices 1→4 + Slice 5 validation,
> #45→#49; `94003bc`→`e399f09`, validated in
> `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`). The earlier "Phase-1 validation /
> docs reconciliation" recommendation is **done and removed** from this list.

1. **Ask Your Guide — extra session uploads (optional, explicit separate slice).**
   Do not start automatically. If the operator chooses to continue Ask features,
   design/implement session-scoped extra uploads separately, keeping them out of job
   artifacts and preserving local-only Ask behavior.
2. **Broader manual Ask UI validation / polish, only if a concrete issue surfaces.**
   The empty local-model response regression found during manual validation is now
   guarded and covered. Keep any follow-up narrow and bug-driven.
3. **Local Model Manager — next real-setup slice, explicit only.**
   Phase 2G7 completed operator docs and safe `.ini` preset import. App-suggested
   settings remain deferred until more real validation exists. Any future LMM
   work should stay explicit and narrow, for example additional live validation,
   packaging/runtime-service docs, or a separately approved recommendations
   design. Preserve the host companion boundary: no direct Docker→host spawn, no
   Provider Settings writes, no Ask changes, no permanent Docker Compose changes,
   no Docker socket/privileged/host-PID path.
4. **Math/PDF font-size rationalization (cause C) — optional CSS-only
   investigation.** The remaining math/PDF fidelity slice; investigate the
   CSS-only font sizing before any change.
5. **Large-PDF preflight size-limit polish — optional, later.** Raising/uniting
   the upload ceiling + preflight size thresholds is a possible later slice. It is
   **explicitly not part of this slice** and not started.
6. **Focused manual validation / polish of the Shortcut Inspector UI.** The
   inspect→repair loop is complete and validated at the API + served-bundle level
   (`docs/VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md`); the remaining gap is a human
   click-through of the live Home/Customize 3-tier badges, the Inspector drawer
   layout, and the Preview→Apply / clone flow (incl. the stale-preview re-disable).
   Validation / polish only — no feature work unless a concrete UI bug surfaces.

(**Also still on the books, design-first:** Library archive / tag model — bulk
**archive** needs a new archive state designed + a `DECISIONS.md` entry first;
bulk **tag** needs a tag model designed first. Neither is started. Bulk **export**
is already DONE (B4). Do not begin either without an explicit slice + design
sign-off.)

## OPEN ITEMS

- **Shortcut options → Builder wiring — DONE (`7af9cbd`, Slice C3).** The Builder
  now exposes `include_sections` + the C2 axes, loads them from a selected
  shortcut into Builder state, and sends them to `/api/jobs/llm` (both the JSON
  and multipart/attachment transports). The backend bridge (`cc75292`) feeds the
  load path; legacy `modules` still translate to canonical `include_sections` on
  read/export. No longer open.
- **Generator preset cards + compatibility warning (C4b) — DONE (`b3d7785`).** The
  Builder Style tab now renders generator presets as cards (provider SVG icon / text
  badge, model chip, purpose, description, recommended use, selected state) consuming
  the C4a `/api/options.generator_presets` metadata, plus a soft, advisory
  `model_hint`-vs-selected-model compatibility warning that never blocks Generate.
  See `presetMeta.js` + `DECISIONS.md`. The shortcut **inspector/repair** loop
  (the store's `valid`/`reason` "references unavailable …" surfacing) is now
  **DONE** (DONE #39→#42). **Still open:** richer **shortcut** cards on Home.
- **Home duplicate "Customize" button — DONE (`7f78542`, Slice C5).** The lower
  duplicate "Customize" button in the Pinned-shortcuts section head was removed;
  the single page-head "Customize Shortcuts" entry is kept and opens the shortcut
  customization modal (not Styles). Smart Tools confirmed already absent from Home;
  Compare Styles confirmed already living in Styles. No longer open.
- **Shortcut inspector / repair loop — DONE** (DONE #39→#42, `a0f96d1`→`4458c9a`,
  on trunk). Read-only inspector + additive `validity` (3-tier status, full
  findings list, saved-model check), 3-tier Home/Customize badges + read-only
  Inspector drawer, repair preview/apply endpoints (preview read-only, apply the
  only write, in-place + clone), and the repair UI (Preview-before-Apply,
  stale-preview re-disables Apply, explicit confirm). Validated docs-only in
  `docs/VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md`. **Still deferred:** the
  degraded-activation confirm / "Repair instead" Home path (§5.5), "Repair all"
  batch, a Home "N need attention" banner, model auto-suggest/fuzzy match,
  imported preview-row repair before import, and tool/view repair (repair is
  scoped to `builder_setup` only). **Update:** the degraded-activation confirm /
  "Repair instead" Home path (§5.5) is now **DONE (#43)** — degraded shortcuts ask
  before launch, broken stay blocked with an Inspect/Repair dialog, valid launch
  unchanged.
- **Rerender drops `generator_preset` — FIXED** (`2716995`, branch
  `fix-rerender-generator-preset`, now on trunk).
  `retry_failed_job` (`api/server.py`, `path_mode == "generate"`) now reads
  `generator_preset` from the manifest and rebuilds through it: the preset is resolved,
  its tuned sampling params are applied to the provider config (mirroring the
  `/api/jobs/llm` preset path), and the id is passed to `generate_study_guide`. An
  absent/null preset keeps the default path; a since-removed preset id degrades
  gracefully to the default path instead of failing the retry. The user's saved
  provider/model still wins (`model_hint` stays advisory). Backend-only; no new request
  field. Regression test `test_scripts/test_retry_generator_preset.py` (7/7 in Docker:
  threading + sampling overrides, default path, stale-id degrade, and a real on-disk job
  whose manifest still records the preset after retry).
- **Provider-aware truncation caps** — deferred (Option B in `DECISIONS.md`).
  Current caps are env-configurable with static defaults.
- **Real cancel button — DONE** (`901d44b`, branch `server-side-cancel`, now on
  trunk; DONE #22). Cooperative server-side cancel via a `jobs/<id>/cancel.requested`
  marker checked at safe stage boundaries; new `cancelled` terminal status;
  `POST /api/jobs/{id}/cancel`; Builder Cancel button. **Cooperative + checkpoint-based:**
  it does **not** kill processes or threads — it sets a marker that the pipeline checks
  at safe stage boundaries, so a cancel requested during an uninterruptible LLM call or
  Chromium render only takes effect at the **next safe checkpoint** (it is "stop at the
  next checkpoint," not an instant abort). **Partial artifacts and the user's uploads /
  Builder inputs / settings are preserved** — nothing is deleted on cancel; the Builder
  keeps its inputs so the user simply re-generates. No pipeline rewrite. **Still
  deferred:** retry-from-cancelled (kept gated to `failed`; re-generate from the Builder
  instead).
- **Docker GHCR publish workflow / prebuilt image** — deferred. `863f5b7` carried a
  `.github/workflows/publish.yml` (push image to GHCR on `v*` tags) and an
  `image: ghcr.io/...` line in compose. Needs a deliberate distribution decision before
  adopting (the app is local-only/single-operator today). Parked on `hardening`.
- **Pinned dependency lockfile** — deferred. `863f5b7` fully froze `requirements.txt`
  (transitive pins + new packages). Reproducibility is good, but a freeze should be
  regenerated from *this* tree, not lifted from the divergent `hardening` branch. Its
  own deliberate slice if/when wanted.
- **Branch retirement** — deferred housekeeping. The consumed feature/integration
  branches (and the short-lived `salvage-compose-limits`, `integ-group-c`) are kept,
  not deleted, per the operator's "do not delete branches" rule.
- **Group D** — not started. Do not begin without an explicit slice request.
