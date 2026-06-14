# CURRENT_TASK.md — Live handoff

> Update this every slice. For stable overview see `PROJECT_CONTEXT.md`; for the
> "why" behind choices see `DECISIONS.md`.

---

## Slice 89 — **Full Material Coverage controls and warnings**, on `slice89-material-coverage-controls-warnings`. **NOT COMMITTED.**

- **Final user-facing warning/control polish before Slice 90 full non-table figure insertion v2.** Slice 88 was
  committed `769d1f5`, fast-forward merged, and pushed to trunk on `chrome-renderer-v1` (it added the read-only JobDetails
  "Material Coverage" display). Slices 87–88 let users *set* per-attachment page/slide exclusions and *see* coverage
  counts after a job. Slice 89 adds the honest **controls + warnings** layer so the user clearly understands which
  attachments have active exclusions, how many pages/slides are excluded, that exclusions apply to guide content **and**
  visual/table planning, that the separate `page_selections` is preserved, and — critically — that full figure insertion
  and table reconstruction are **not enabled yet** (no overpromising).
- **Frontend UX/control slice only.** No backend change: extraction logic, material page-selection application,
  visual-manifest filtering, visual inclusion planning, table policy, render/export/prompt/provider behavior, and
  visual-pilot ranking/classification/cap/default/two-key-gate/caption are all untouched. **No new backend field; the
  Slice 87 submit payload shape is unchanged.** No table reconstruction; no all-visual insertion/rendering.
- **New pure helper** `frontend/src/materialCoverageWarnings.js` (React-free, node-testable):
  - `buildBuilderMaterialCoverageSummary({ exclusionInputs }) → { active, attachmentsWithExclusions, totalExcludedPages,
    hasInvalidTokens }` — consumes the **positional** ordered array of raw exclusion-input strings (the same array the
    submit path maps from `attachments`); emits **counts + a boolean invalid flag only**. Never carries filenames, paths,
    page numbers, or the raw invalid tokens the user typed. Reuses `parsePageListInput` for parsing.
  - `buildJobMaterialCoverageNotes(displayModel) → [{ token, tone, text }]` — derives a fixed, deterministic, **closed
    vocabulary** of honest note strings from the Slice 88 display model: selections applied, useful visuals planned
    (insertion is a later step), table reconstruction not enabled yet, and a calm "artifacts may be unavailable for older
    jobs" note. Never echoes raw artifact warning text; tolerates missing/malformed models.
- **Builder controls/warnings** (`frontend/src/components/BuilderWorkspace.jsx`): a compact `MaterialCoverageControls`
  block rendered once below the attachment list whenever ≥1 paginated attachment is present. Shows the active/inactive
  state, the local summary (`"N attachments have exclusions. M pages/slides will be skipped."`), a generic invalid-token
  hint (`"Some entries were ignored. Use numbers or ranges like 2, 4-6, 10."` — never the raw token), the scope note
  (`"Exclusions apply to guide source text and visual/table coverage planning."`), the honest limitation copy (`"Full
  figure insertion and table reconstruction are not enabled yet; this job will still record coverage signals for them."`),
  and a **"Clear exclusions"** button that resets the parent's raw-input state. The block consumes the positional summary
  only — it never persists filenames/paths as keys and never changes the submit payload shape.
- **JobDetails warnings** (`frontend/src/components/MaterialCoveragePanel.jsx`): a new "What this means" section renders
  the closed-vocab notes from `buildJobMaterialCoverageNotes`, computed only once both artifact fetches settle (so no
  premature "unavailable" flash). 404/missing artifacts stay calm; no scary error language; no raw artifact warnings.
- **CSS** `frontend/src/design-system.css`: `.sg-coverage-controls*` (Builder block) and `.sg-coverage-note*` (JobDetails
  notes) — calm, count/status-only surfaces, no per-source detail.
- **Validation:** new node harness `frontend/scripts/verify-material-coverage-warnings.mjs` (added to `npm run test` +
  `test:material-coverage-warnings`) covers inactive/active summaries, attachment + total page counts, invalid-token
  generic flag (no raw value), cleared = empty deterministic state, positional/no-filename-leak, notes for active
  selections / available plan / deferred table reconstruction / missing artifacts, malformed-model tolerance, hostile
  canary no-leak, and determinism. `npm run build` + full frontend suite pass; existing
  `verify-material-page-selections-ui.mjs` / `verify-material-coverage-display.mjs` still pass. Python regressions green
  on host. Docker build + health + `smoke_release.py` 29/0. **Slice 89 is NOT committed.**

---

## Slice 88 — **JobDetails material coverage display**, on `slice88-jobdetails-material-coverage-display`. **COMMITTED `769d1f5` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **First read-only surface for the Full Material Coverage signals.** Slice 87 was committed `844e394`, fast-forward
  merged, and pushed to trunk on `chrome-renderer-v1` (it added the Builder UI for per-attachment page/slide exclusions).
  Slices 76–86 built + validated the backend that produces those signals; Slice 87 let users *set* exclusions. Slice 88
  adds a **read-only** "Material Coverage" tab in Job Details so a user can *see*, after a job finishes, safe coverage
  information: whether material page selections were present, page coverage counts (covered / embedded-text / OCR /
  unreadable) from `source_coverage_report.json`, how many useful non-table visuals were planned and how many table-like /
  unsafe candidates were skipped from `visual_inclusion_plan.json`, plus a static deferred table-policy note.
- **UI display only.** No backend change at all. Extraction/OCR routing, material page-selection application,
  visual-manifest filtering, visual inclusion planning, table policy, render/export/prompt/provider behavior, and
  visual-pilot ranking/classification/cap/default/two-key-gate/caption are all untouched. No table reconstruction; no
  all-visual insertion/rendering. It consumes only already-safe job-response fields and **exact-name** artifact fetches.
- **New pure helper** `frontend/src/materialCoverageDisplay.js` (React-free, node-testable):
  - `summarizeMaterialSelections(job)` — counts attachments carrying an explicit include/exclude page set (positional
    `attachment_<index>` keys only) + the global selection; reports `active`/`inactive`. Never reads a key/filename/page.
  - `summarizeSourceCoverage(report)` — closed-vocab status + non-negative page counts from the report `summary`.
  - `summarizeVisualInclusionPlan(plan)` — closed-vocab status + planned / table-like-skipped / unsafe-skipped counts.
  - `buildMaterialCoverageDisplayModel({ job, sourceCoverageReport, visualInclusionPlan })` — composite safe model; null
    reports degrade to a neutral `unavailable` section (never an error); table policy note is a static deferred string.
  - All summarizers tolerate missing/malformed input, never throw, emit only counts/booleans/closed status tokens, and
    pass status through an allowlist so no free-form text rides out.
- **New panel** `frontend/src/components/MaterialCoveragePanel.jsx`: fetches `source_coverage_report.json` and
  `visual_inclusion_plan.json` by **exact name** via the existing `getJobArtifact` / `artifactUrl` helpers (404 ⇒ calm
  "not available", never an error), reads `material_page_selection(s)` from the already-safe job response, and renders
  count tiles + status tags. Exact-name artifact links use the existing safe URL only. Wired into `RecentJobsPanel.jsx`
  as a new "Material Coverage" drawer tab (icon `Gauge`); new neutral `.sg-tag-slate` tag added to `design-system.css`.
- **No backend / client.js change.** The artifact route already serves both exact names (`api/server.py` `_artifact_path`)
  and `getJobArtifact` already does exact-name JSON fetch — so no new route and no client helper were needed.
- **Validation:** new node harness `frontend/scripts/verify-material-coverage-display.mjs` (added to `npm run test` +
  `test:material-coverage-display`) covers missing/malformed degradation, count summaries, safe-key-only active counting,
  hostile canary no-leak over the display model, and determinism. `npm run build` + full frontend suite pass. Python
  regressions green on host (material coverage E2E 79/0, source coverage report 59/0, source coverage artifact 45/0,
  inclusion planner 178/0, plan artifact 62/0, table policy 145/0). Docker build + health + `smoke_release.py` 29/0.
  Committed `769d1f5`, fast-forward merged, and pushed to `chrome-renderer-v1`.

---

## Slice 87 — **Builder UI for per-attachment page/slide exclusions**, on `slice87-builder-page-slide-exclusions-ui`. **COMMITTED `844e394` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **First UI slice on top of the Full Material Coverage backend.** Slice 86 was committed `3db8572`, fast-forward merged,
  and pushed to trunk on `chrome-renderer-v1` (it added the deterministic synthetic Material Coverage **E2E validation
  harness** that proved the whole backend chain end-to-end). Slices 78–86 proved the backend can persist + apply
  per-attachment material page selections. Slice 87 adds the **first Builder control** so a user can actually set
  per-attachment page/slide **exclusions** and submit them through the already-merged `material_page_selections` field.
- **UI-wiring only.** No backend change: extraction logic, visual-manifest filtering, visual inclusion planning, table
  policy, render/export/prompt/provider behavior, and visual-pilot cap/ranking/classification/caption are all untouched.
  The backend remains the source of truth for normalization/application.
- **New pure helper** `frontend/src/materialPageSelections.js`:
  - `parsePageListInput(input) → { pages, warnings }` — parses positive 1-based integers and simple ranges (`2, 4-6, 10`);
    dedupes + sorts; drops invalid tokens with **closed-vocabulary** local warning tokens (`page_token_invalid`,
    `page_range_invalid`, `page_range_reversed`, `page_number_invalid`) and never echoes the raw token.
  - `buildMaterialPageSelections(orderedInputs) → envelope` — maps per-attachment raw inputs **by upload order** into the
    safe envelope `{ version:1, attachments:{ attachment_<index>: { version:1, mode:"exclude", include_pages:[],
    exclude_pages:[…], warnings:[] } }, warnings:[] }`. Attachments with no exclusions are omitted; index follows upload
    order even when earlier attachments have none. Keys are **always** `attachment_<index>`, never filenames/paths.
  - `hasActiveMaterialSelections(envelope)` — the gate the Builder uses to decide whether to send the field at all.
- **Builder wiring** (`frontend/src/components/BuilderWorkspace.jsx`): new `materialExclusions` state keyed by the stable
  `attachmentKey(file)` signature (raw typed text per attachment); a small `MaterialExclusionField` rendered under each
  paginated attachment (`.pdf` / `.pptx`) with copy *"Exclude pages/slides — e.g. 2, 4-6, 10 — These pages will be skipped
  from guide content and visual/table planning."* plus a live "Excluding pages …" confirmation and generic hint text for
  invalid input (never the raw value). At submit, `attachments.map(f => materialExclusions[attachmentKey(f)] ?? "")` is
  converted to the envelope and threaded through `buildBuilderPayload → buildLlmPayload`, which adds
  `material_page_selections` **only** when at least one exclusion is active. Removing an attachment drops its entry.
- **Request path** (`frontend/src/api/client.js`): `material_page_selections` added to the multipart object-stringify
  whitelist (alongside `outline` / `include_sections` / `page_selections`) so the envelope is JSON-stringified into the
  attachment `FormData`. The JSON-only (no-attachment) path serializes it with the rest of the payload; with no active
  exclusion the field is simply absent.
- **`page_selections` untouched.** The older extraction page-range field (keyed by filename, load-bearing) is preserved
  exactly — separate state, separate field, separate UI (the preflight card).
- **Validation:** new node harness `frontend/scripts/verify-material-page-selections-ui.mjs` (added to `npm run test` and
  `test:material-page-selections-ui`) covers parse/dedupe/ranges, closed warnings, positional keys, omitted attachments,
  the active gate, determinism, and filename/path/URL/data-URI/base64 canary no-leak over the serialized payload.
  `npm run build` passes; the full frontend suite passes. Python suite green on host (material coverage E2E 79/0, model
  183/0, extraction 31/0, manifest planning 47/0, inclusion planner 178/0, plan artifact 62/0, table policy 145/0);
  FastAPI-gated tests run in Docker: `test_page_selection_request_persistence.py` 182/0, `test_page_selections.py` 24/0.
  Docker build + health + `smoke_release.py` 29/0. **Slice 87 is NOT committed.**

---

## Slice 86 — **Material Coverage E2E validation harness**, on `slice86-material-coverage-e2e-validation`. **COMMITTED `3db8572` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **Full Material Coverage foundation slice (validation side).** Slice 85 was committed `8a1b780`, fast-forward merged,
  and pushed to trunk on `chrome-renderer-v1` (it added the pure, stdlib-only table reconstruction/simplification **policy
  core** `pipeline/table_reconstruction_policy.py`). Slices 76–85 built the backend foundation for Full Material Coverage
  (source coverage report core/artifact; global + per-attachment material page-selection persistence; selection applied to
  text extraction and to visual-manifest planning; full non-table visual inclusion planner + artifact; table policy core).
  Slice 86 adds a **deterministic synthetic E2E validation harness** that proves these pieces work together as one chain —
  **before** any Builder UI is built on top of them.
- **Validation-only.** No UI, no new job artifact persisted, no table reconstruction, no LLM/prompt integration, no extra
  visuals inserted, no visual-pilot cap change, no render/export change, no provider/model call. The harness is pure and
  unwired: it composes already-merged pure helpers over synthetic dictionaries and asserts the result.
- **New test** `test_scripts/test_material_coverage_e2e_validation.py` validates the chain:
  `material page selection → text extraction page filtering → visual manifest page filtering → visual inclusion plan →
  table reconstruction policy → source/visual/material coverage summary`, using
  `apply_material_selection_to_page_universe` / `page_is_in_material_selection`,
  `build_visual_assets_manifest(..., page_filters=...)`, `build_visual_inclusion_plan`,
  `build_table_reconstruction_policy`, and `build_source_coverage_report`.
- **Synthetic scenario:** two attachments (`attachment_0`, `attachment_1`) with existing `page_selections` universes
  `{1,2,3,4}` and `{5,6,7,8}`; a global material selection (`exclude 2,4,6,8`); a per-attachment override on
  `attachment_0` (`include 1,9`). Effective extraction sets resolve to `attachment_0 → {1}` (override beats global; page 9
  dropped as outside the universe) and `attachment_1 → {5,7}` (global fallback). Visual sources carry signals on every
  page so the filter is exercised; enriched records add a useful figure + a table-like + a decorative + a tiny visual;
  four table-candidate dicts feed the policy.
- **Proven by assertions (79 pass / 0 fail on host):** per-attachment selection overrides the global fallback; existing
  `page_selections` caps the maximum universe and material cannot expand beyond it (page 9 dropped, out-of-universe
  include → empty + closed `material_selection_no_matching_pages`); excluded pages are absent from the extracted-content
  page plan; visual records on excluded pages are filtered out (only pages `{1,5,7}` survive, 5 filtered); the full
  inclusion plan includes **all** eligible useful non-table visuals (4, not top 1–2); decorative/tiny/table-like visuals
  are **not** planned as normal visuals; table-like records are counted by the **table policy** (all 4 handled, routed to
  `reconstruct_with_original`/`simplify_only`), never screenshot-inserted — `screenshot_insert_count` stays `0`; source
  coverage counts are deterministic and sanitized; an in-memory `material_coverage_validation` summary shape is emitted;
  a hostile-canary no-leak sweep over every stage output passes; repeated calls serialize identically.
- **In-memory summary only.** The harness emits a `material_coverage_validation` summary dict (checks + counts) for
  assertion; **no new job artifact is persisted** in this slice.
- **Scope boundaries.** Validation-only: `api/server.py`, `pipeline/run_llm_job.py`, `pipeline/job_manager.py`, the
  visual-inclusion planner/artifact, `visual_markdown_insertion.py`, renderers, exporters, prompts, providers, frontend,
  and visual-pilot ranking/classification/cap/caption files are all untouched. No API route change, no job-execution
  wiring, no extraction/OCR routing change, no render/export/prompt/provider behavior change, no visual-pilot
  ranking/classification/cap/default/two-key-gate/caption change, no table reconstruction implemented, no new artifact
  persisted, no Chandra/Mistral/Gemini/model/provider/cloud call, no direct `clean.md` write, no table manifest invented.
  Chandra remains blocked by its own live-validation gate. Docker rebuild **not required** (pure/unwired validation).
  **Slice 86 is NOT committed.**

---

## Slice 85 — **Table reconstruction/simplification policy core**, on `slice85-table-reconstruction-policy-core`. **COMMITTED `8a1b780` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **Full Material Coverage foundation slice (table decision side).** Slice 84 was committed `7cc9d6f`, fast-forward
  merged, and pushed to trunk on `chrome-renderer-v1` (it persisted the Slice 83 non-table plan as the exact-name artifact
  `visual_inclusion_plan.json`). The non-table planner deliberately **skips table-like material** — tables must not be
  treated as ordinary screenshot visuals. Slice 85 adds the next, still-pure step: a deterministic **policy core** that
  decides what should later happen to a table-like candidate. **No actual table reconstruction happens yet.**
- **Policy-core only.** No table content is reconstructed, no LLM/prompt is touched, no table is inserted into
  Markdown/PDF/DOCX, **no table artifact writer is added**, no UI, no OCR, no PDF/image inspection, no provider/model call.
  There is **no table manifest today and this slice invents none** — the module evaluates synthetic / sanitized
  *table-candidate-shaped* dicts only and returns a sanitized policy dict.
- **New pure module** `pipeline/table_reconstruction_policy.py` (stdlib-only, unwired):
  - `classify_table_candidate(candidate)` → sanitized per-candidate item dict;
  - `build_table_reconstruction_policy(candidates, *, max_items=None)` → sanitized policy dict
    (`version, kind, status, summary, items, warnings`).
- **Product rule encoded:** a table should generally **not** be inserted as a screenshot. Future modes (not implemented
  here) are **`reconstruct_with_original`** (original table text + a simpler/clearer version) and **`simplify_only`** (the
  simpler/clearer version only), plus **`defer`**, **`skip_unreadable`**, **`skip_unsafe`**. `screenshot_insert_count` is
  **always 0** — screenshot insertion is never the default table behavior.
- **Deterministic classification rules:** table-likeness is recognized from closed tokens
  (`table, table_like, grid_table, dense_table, table_region, table_image, tabular`) across
  `candidate_kind/visual_kind/visual_type/table_signal/kind/type/asset_type`; non-table records are **never** treated as
  table screenshots (warned `not_table_like`, no item). For a table-like record: unsafe → `skip_unsafe`; missing/invalid
  `source_page` → `defer` (closed warning); insufficient structure → `skip_unreadable`; low confidence → `defer`;
  otherwise text-layer present → `reconstruct_with_original`, text-layer absent/unknown (with structure) → `simplify_only`.
- **Preserve list (closed/deterministic):** `headers, column_labels, row_labels, exam_terms, numeric_values, units` —
  `exam_terms` always kept; header/numeric signals add the rest in fixed order. Skip/defer items carry an empty preserve.
- **Default = handle ALL candidates** (not top-1/2). `max_items` is a defensive ceiling only, default `None`; when passed
  it truncates in input order, sets `status: partial`, and records `max_items_applied`.
- **No-leak / safety:** emits only closed tokens, ints, `None`, fixed strings — verified by hostile-canary fields
  (path/title/caption/ocr/table-text/image-ref/asset-id/url/token/argv/socket/model-path/base64/data-uri) the policy reads
  for decisions and never echoes. Total/pure: never raises; malformed input → safe skipped policy.
- **Tests:** new `test_scripts/test_table_reconstruction_policy.py` — **145 passed, 0 failed** on host. Covers
  missing/malformed → skipped, non-table-not-a-screenshot, reconstruct-with-text+structure, simplify-without-text,
  dense/generic table recognition, missing/invalid `source_page` defer, insufficient-structure skip, unsafe skip, low-conf
  defer, screenshot_insert==0, closed/deterministic preserve, default-handles-all (7 of 7), `max_items` ceiling +
  reindex, determinism, schema whitelist, hostile-canary no-leak, and stdlib-only/unwired import hygiene. Slice 83 planner
  (178/0), Slice 84 artifact (62/0), visual-assets-manifest (65/0), page-selection-manifest-planning (47/0) all still
  green.
- **Scope boundaries.** Pure policy core only: `api/server.py`, `pipeline/run_llm_job.py`,
  `pipeline/visual_inclusion_planner.py`, `pipeline/visual_inclusion_plan_artifact.py`,
  `pipeline/visual_markdown_insertion.py`, renderers, exporters, prompts, providers, frontend all untouched. No API route
  change, no job-execution wiring, no extraction/OCR routing change, no render/export/prompt/provider behavior change, no
  visual-pilot ranking/classification/cap/default/two-key-gate/caption change, no Chandra/Mistral/Gemini/model/provider/
  cloud call, no direct `clean.md` write, no table manifest invented. Chandra remains blocked by its own live-validation
  gate. **Slice 85 is NOT committed.**

---

## Slice 84 — **Persist visual inclusion plan artifact**, on `slice84-visual-inclusion-plan-artifact`. **COMMITTED `7cc9d6f` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **Full Material Coverage foundation slice (persistence side).** Slice 83 was committed `72e1f87`, fast-forward merged,
  and pushed to trunk on `chrome-renderer-v1` (it added the pure, stdlib-only **full non-table visual inclusion planner
  core** — `build_visual_inclusion_plan(...)`). Slice 84 wires that planner output into backend job artifacts as the safe
  exact-name artifact `visual_inclusion_plan.json`, derived **only** from the already-sanitized
  `visual_assets_manifest.json`. No Markdown insertion / render / export / UI / provider wiring yet.
- **New writer** `pipeline/visual_inclusion_plan_artifact.py`: `write_visual_inclusion_plan(job, visual_manifest=None)`.
  Builds the Slice 83 plan, serializes deterministic JSON (`indent=2, sort_keys=True`) through `job.save_text(...)`, and
  is **degrade-never-fail** — any disk-write failure prints a safe message (`type(exc).__name__` only, no raw exception)
  and returns the in-memory plan; generation continues.
- **New `Job.visual_inclusion_plan_json`** (`<job>/visual_inclusion_plan.json`), modeled on the other advisory siblings:
  exact-name download only, never in `ARTIFACTS` / generic UI rows / export selectors / `VISUAL_ADVISORY_EXPORT_ARTIFACTS`,
  never gates job status.
- **Exact-name download** added to `api/server.py` `_artifact_path` (`application/json`), mirroring
  `source_coverage_report.json`. **Deliberately NOT** added to `ARTIFACTS`, `_artifact_urls`, `_artifact_details`,
  `EXPORT_ARTIFACTS`, `EXPORT_ARTIFACT_ALIASES`, or the export ride-along tuple. No generic JobDetails/export surfacing.
- **Integration point:** `run_llm_job._attach_sources`, immediately after the visual-assets manifest is written and read
  back (`visual_manifest_obj`), alongside the existing manifest-derived scoring/replacement-plan writers, via the wrapped
  `_write_visual_inclusion_plan_safely(...)`. Written exactly when the manifest is written; non-PDF / no-extraction jobs
  omit it (no call). A missing/skipped/malformed manifest yields a safe **skipped** plan via the pure planner.
- **Default = plan ALL eligible non-table visuals** (not top-1/2): the artifact inherits the Slice 83 contract verbatim.
  **Table-like records are skipped and counted** (`table_like_skipped_count`); decorative/logo/header/footer/background/
  watermark/tiny/blank/low-information/unsafe/unknown records are skipped per Slice 83 signals.
- **Candidate mapping deferred.** Slice 84 keeps the Slice 83 plan schema **as-is** (smallest safe option). Items expose
  only safe closed tokens / ints / `None` (`plan_index, source_index, source_page, visual_kind, inclusion_role, reason,
  warnings`). No `candidate_id` was added; if a future insertion slice needs one it must be a **generated internal id**
  (e.g. `visual_candidate_0001`) — never a filename/path/raw image-ref/caption/OCR/source text.
- **No-leak.** The artifact emits only closed tokens, ints, `None`, fixed strings — verified by hostile-canary record
  fields (filename/title/path/text/ocr/caption/table/image-ref/asset-ref/url/argv/socket/model-path/base64/key) that the
  planner reads for decisions and never echoes.
- **Tests:** new `test_scripts/test_visual_inclusion_plan_artifact.py` — **62 passed, 0 failed** on host (the
  `api.server` exact-name section SKIPs on host where FastAPI is absent; covered in Docker). Covers writes-from-manifest,
  default-plans-all (5 of 5, not top-2), table-skip+count, decorative/tiny/blank/unsafe skip, missing/skipped/malformed
  manifest → safe skipped plan, write-failure degrade-never-fail, determinism, exact-name route + no generic/export
  exposure, `_attach_sources` wiring + writer-failure-does-not-fail-generation, schema whitelist, hostile-canary no-leak,
  no `clean.md` write. Slice 83 planner tests still **178/0**.
- **Scope boundaries.** Persistence only: no Markdown insertion (`visual_markdown_insertion.py` untouched), no table
  reconstruction (Slice 85), no PDF/DOCX render change, no export-bundle change, no prompts/providers, no frontend/UI, no
  extraction/OCR routing change, no visual-pilot ranking/classification/cap/default/two-key-gate/caption change, no
  Chandra/Mistral/Gemini/model/provider/cloud call, no direct `clean.md` write. Chandra remains blocked by its own
  live-validation gate. **Slice 84 is NOT committed.**

---

## Slice 83 — **Full non-table visual inclusion planner core**, on `slice83-full-visual-inclusion-planner-core`. **COMMITTED `72e1f87` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **Full Material Coverage foundation slice (planner side).** Slice 82 was committed `fd3fb97`, fast-forward merged, and
  pushed to trunk on `chrome-renderer-v1` (it applied material page selections to **visual-assets manifest planning**, so
  visual candidates from material-excluded PDF pages never enter `visual_assets_manifest.json`). Slice 83 adds the next,
  still-pure step: a planner that decides **which non-table visuals from the already-page-filtered manifest** should be
  planned for future guide inclusion. This is the deliberate move **away from "top 1–2 visuals forever."**
- **Product goal (not "insert every crop").** Include **all useful non-table figures/diagrams/graphs/charts/instructional
  visuals from included pages, after deterministic safety filtering** — explicitly NOT every crop, logo, decorative
  header, background, tiny/blank/low-information crop, or table-as-screenshot.
- **New pure module** `pipeline/visual_inclusion_planner.py`, stdlib-only, unwired. Public API:
  `build_visual_inclusion_plan(visual_manifest: dict | None, *, max_items: int | None = None) -> dict`.
- **Plan shape:** `{version, kind:"visual_inclusion_plan", status: completed|partial|skipped, summary{...}, items[], warnings[]}`.
  Each item: `{plan_index, source_index (int|None), source_page, visual_kind (diagram|figure|graph|chart|image|unknown),
  inclusion_role (primary_visual|supporting_visual), reason:"non_table_visual_from_included_page", warnings[]}`.
  `summary` carries `source_count, candidate_count, planned_count, non_table_planned_count, table_like_skipped_count,
  unsafe_or_incomplete_skipped_count, page_count_with_planned_visuals`.
- **Default = plan ALL eligible non-table visuals.** No hard cap at 1 or 2. `max_items` is an optional **defensive
  ceiling only** (default `None`); when passed as a non-negative int and it truncates the plan, `status` becomes
  `partial` and `max_items_applied` is recorded. Any other `max_items` value is ignored.
- **Eligibility (deterministic).** A record is planned iff: it has a strictly-positive **int** `source_page`; it is not
  table-like; it is not decorative/logo/header/footer/background/watermark; it is not marked unsafe; it is not a
  low-information page (`signals.classification == "blank_or_low_text"`); it is not a tiny crop (`crop_*_px < 24`); and it
  carries a recognized non-table type. Today's manifest types `page_visual_signal` (→ supporting, kind derived from
  `has_drawings`/`has_images`) and `extracted_figure` (→ primary, kind `figure`) are non-table; explicit future kind
  tokens (diagram/figure/graph/chart/image/plot/illustration) are honored, with `plot→graph`, `illustration→figure`.
- **Table-like skip.** Records typed `table`/`table_like`/`grid_table`/`dense_table`/`table_region`/`tabular`/`table_image`
  are **skipped** and counted in `table_like_skipped_count`. Table belongs to the later table reconstruction/simplification
  policy slice — **never** screenshot insertion here. Table wins over any co-present figure token (conservative).
- **Unknown visual type rule (documented).** A record with no recognized type token at all is **skipped** with
  `visual_type_unknown` (the safer choice; today's real manifests only ever emit `page_visual_signal`/`extracted_figure`,
  so this only affects future/hostile records and never reduces real coverage).
- **Ordering.** Deterministic by `source_index` (when present), then `source_page`, then original manifest position — a
  stable sort that reproduces the manifest's existing source-then-page order. Exact-duplicate records (same internal
  `asset_id`) are collapsed; that id is used for dedupe **only** and is never emitted.
- **Closed warning/status tokens:** `manifest_missing`, `manifest_malformed`, `manifest_skipped`, `record_malformed`,
  `source_page_missing`, `source_page_invalid`, `visual_type_table_skipped`, `visual_type_unknown`,
  `visual_record_unsafe`, `visual_record_decorative`, `visual_record_low_information`, `visual_record_tiny`,
  `max_items_applied`. No raw exception strings.
- **No-leak.** The plan emits only closed tokens, ints, `None`, and fixed strings. No filename/path, document/OCR/caption/
  table text, image ref, asset ref/asset id, image bytes, base64/data URI, provider payload, token, URL, argv, socket
  path, model path, or raw exception can survive — input fields are read for decisions only and never echoed. Verified by
  hostile-canary tests.
- **Tests:** new `test_scripts/test_visual_inclusion_planner.py` — **178 passed, 0 failed** on host. Covers missing/
  malformed/skipped/empty manifests, non-table planning, table/decorative/low-info/tiny/unsafe skips, unknown-type rule,
  missing/invalid `source_page`, manifest-order preservation, default-plans-all (7 of 7, not top-2), `max_items` ceiling,
  dedupe, determinism, schema whitelist, hostile-canary no-leak, and stdlib-only import hygiene.
- **Scope boundaries.** Planner-core only and **unwired**: not imported by generation, Markdown insertion, renderers,
  exporters, prompts, `api/server.py`, or the frontend. No artifact persisted yet (that is Slice 84). No table
  reconstruction (Slice 85). No visual-pilot ranking/classification/cap/default/two-key-gate/caption change. No
  extraction/OCR routing change. No render/export/prompt/provider change. No Chandra/Mistral/Gemini/model/provider/cloud
  call. No direct `clean.md` write. Chandra remains blocked by its own live-validation gate. **Slice 83 is NOT committed.**
- **Roadmap framing (Slices 83–86 = Full Material Coverage backend foundation):** **Slice 83** full non-table visual
  inclusion planner core (this) · **Slice 84** persist `visual_inclusion_plan.json` (safe exact-name artifact; may carry
  stable safe candidate IDs + source page numbers, never raw image refs/filenames/text) · **Slice 85** table
  reconstruction/simplification policy core · **Slice 86** material-coverage E2E validation. **No UI** until the backend
  chain proves page selections apply consistently to content extraction, visual candidates, table candidates/policy, and
  coverage reporting.

### Prior position (Slice 82 — committed & merged)

## Slice 82 — **Apply material page selections to visual/table manifests**, on `slice82-apply-material-page-selection-to-visuals`. **COMMITTED `fd3fb97` + MERGED to `chrome-renderer-v1` (fast-forward) + PUSHED.**

- **Full Material Coverage foundation slice (visual side).** Slice 81 was committed `7ca109d`, fast-forward merged, and
  pushed to trunk on `chrome-renderer-v1` (it applied material selections to attachment **text extraction / content
  planning**). Slice 82 applies the **same** effective page selection to **visual-assets manifest planning**, so visual
  candidates from material-excluded PDF pages never enter the manifest.
- **What it does.** In `_attach_sources` (`pipeline/run_llm_job.py`), the slice now keeps a per-metadata-source list
  `visual_page_filters` in lockstep with `extraction_metadata_sources`. Each entry is the **effective post-material
  allowed page set** (the *same* set Slice 81 computed for extraction) when a material selection was **applied** for that
  attachment, or `None` (no active filter ⇒ existing visual-manifest behaviour). It is passed as the new
  `page_filters=` kwarg to `write_visual_assets_manifest`.
- **Manifest-level filter.** `build_visual_assets_manifest(sources, extracted_assets, *, page_filters=None)` drops a
  page-level `page_visual_signal` candidate whose `source_page` is not in its source's allowed set, BEFORE it becomes a
  manifest record. `page_filters=None` / absent ⇒ output byte-identical to before Slice 82.
- **Missing/invalid `source_page`.** Under an active filter, a candidate whose `source_page` cannot be verified (≤ 0)
  is **dropped conservatively** (`material_selection_visual_page_unknown`) so a user-excluded page can never surface a
  visual. With no active filter the candidate is kept (unchanged). On the live path page candidates always carry a valid
  physical page number, so this only affects hostile/synthetic input.
- **Interaction with the load-bearing `page_selections`.** The effective allowed set is Slice 81's
  intersection(`page_selections` universe, material selection), so a material selection can never keep a visual record on
  a page `page_selections` already excluded, nor expand visuals beyond it. `exclude`/`all` with no known universe defers
  (no filter; existing behaviour) exactly as extraction does.
- **Precedence per attachment:** per-attachment `material_page_selections.attachments.attachment_<i>` → global
  `material_page_selection` → default-all — identical to Slice 81 (the filter reuses the same resolution).
- **New pure helper** `page_is_in_material_selection(source_page, allowed_pages)` in `pipeline/page_selection_model.py`
  returns `{kept, status}` (closed token or `None`); stdlib-only, never raises.
- **Warning/status tokens (closed):** `material_selection_visual_filtered`, `material_selection_visual_page_unknown`,
  `material_selection_visual_no_matching_pages` (a source whose every candidate was filtered out → still a `completed`
  manifest, never a failure), plus `material_selection_table_manifest_not_present` reserved for the future table layer.
  A new `summary.pages_filtered_by_material_selection` int records how many candidates were dropped. No page lists,
  filenames, paths, captions, image refs, or text appear in any warning.
- **Table manifests.** There is **no separate table manifest / table-extraction artifact today** — the only visual
  artifact is `visual_assets_manifest.json`. Table-manifest page filtering is therefore **deferred** to a future table
  extraction/reconstruction layer (the reserved token documents it honestly); Slice 82 invents no table artifact.
- **Extracted figures (gated, off by default)** already receive the material-filtered `pages` at extraction time
  (Slice 40 path), so they are restricted upstream; the explicit manifest filter targets the live `page_visual_signal`
  path. Documented in DECISIONS.
- **What changed:** `pipeline/page_selection_model.py` (new pure helper + closed tokens), `pipeline/visual_assets_manifest.py`
  (`page_filters` kwarg + per-source filter + summary count + closed warnings), `pipeline/run_llm_job.py` (build
  `visual_page_filters`, pass to the manifest writer), and new
  `test_scripts/test_page_selection_visual_manifest_planning.py`. `api/server.py` unchanged (Slice 80 wired the request
  fields).
- **Scope boundaries.** No Builder UI. No all-figures planner. No table reconstruction. No visual-pilot
  selection/ranking/classification/cap/default/two-key-gate/caption change (the pilot may simply see fewer candidates
  when a selection excludes pages — the cap is unchanged). No extraction/OCR routing change beyond the intended visual
  manifest page filtering. No render/export/prompt/provider behavior change. No Chandra/Mistral/Gemini/model/provider/cloud
  call. No direct `clean.md` write (still via `JobManager.save_clean_md`). Chandra remains blocked by its own
  live-validation gate. **Slice 82 committed `fd3fb97`, fast-forward merged to `chrome-renderer-v1`, and pushed.**
  Validated: host suite green; Docker `test_page_selection_request_persistence.py` 182/0 and `test_page_selections.py`
  24/24; Docker rebuild + `/api/health` + `smoke_release.py` 29/0/0.

### Prior position (Slice 81 — committed & merged)

- **Apply material page selections to extraction/content planning**, on
  `slice81-apply-material-page-selection-to-extraction`. **COMMITTED `7ca109d` + MERGED to `chrome-renderer-v1`
  (fast-forward) + PUSHED.**
- Slice 81 is the first slice that **applied** the persisted material selection — to attachment **text extraction /
  content planning only**.
- **What it does.** In `_attach_sources` (`pipeline/run_llm_job.py`), for each PDF attachment it resolves the active
  material selection and filters which pages `extract_file(path, pages=...)` reads, so only selected pages reach the
  model-facing source text. Nothing else changes.
- **Precedence per attachment:** per-attachment `material_page_selections.attachments.attachment_<i>` (by request
  attachment order, 0-based) → global `material_page_selection` → default-all. A per-attachment entry wins outright when
  present (even default-all, which then suppresses the global fallback).
- **Interaction with the load-bearing `page_selections`.** The existing filename-keyed `page_selections` page-range
  field still defines the **maximum** page universe. A material selection can only **further filter** that universe; it
  never expands extraction beyond it (`include` intersects the universe; `exclude`/`all` subtract from it). When there is
  no `page_selections` universe and the selection is `exclude`/`all` (which need a known universe to enumerate),
  filtering is **deferred** (extraction unchanged) with a closed warning — pages are never guessed. `include` selections
  are always applied because the include list is itself an explicit page set.
- **New pure helper** `apply_material_selection_to_page_universe(material_selection, *, existing_allowed_pages=None,
  natural_pages=None)` in `pipeline/page_selection_model.py` returns `{included_pages, excluded_pages, warnings,
  resolved}` — deterministic, never raises, page-ints only.
- **Resolution helpers** `_resolve_material_selection` / `_is_active_material_selection` in `run_llm_job.py` pick the
  active selection and treat a default-all selection as a no-op (extraction byte-identical when absent/default-all).
- **Per-attachment summary.** When a material selection is active for an attachment, a safe
  `entry["material_selection"] = {"status": "applied"|"deferred"|"not_applicable", "warnings": [closed tokens]}` is
  recorded in the attachment manifest entry (counts/tokens only — no page lists, filenames, or paths). Absent/default-all
  ⇒ no field added.
- **Non-PDF attachments** are ignored safely (`material_selection_non_pdf_ignored`); current non-PDF extraction is
  unchanged.
- **Warning tokens (closed vocabulary):** `material_selection_applied`, `material_selection_no_matching_pages`,
  `material_selection_non_pdf_ignored`, `material_selection_universe_unknown`,
  `material_selection_filtered_by_existing_page_selection` (plus `material_selection_invalid_attachment_key` reserved at
  the Slice 80 normalization layer).
- **What changed:** `pipeline/page_selection_model.py` (new pure helper), `pipeline/run_llm_job.py` (apply in
  `_attach_sources`; new resolution helpers; threaded the two material params from `run_llm_job`), and new
  `test_scripts/test_page_selection_extraction_planning.py`. `api/server.py` unchanged (Slice 80 already wired the
  request fields).
- **Scope boundaries.** No Builder UI. No application to visual/table manifests, no all-figures planner, no table
  reconstruction. No visual-pilot selection/ranking/classification/cap/default/two-key-gate/caption change. No
  render/export/prompt/provider behavior change (generated guide text differs only as a consequence of less source text
  when a selection is explicitly active). No Chandra/Mistral/Gemini/model/provider/cloud call. No direct `clean.md`
  write (still via `JobManager.save_clean_md`). Existing `page_selections` page-range extraction unchanged (regression:
  `test_page_selections.py` 24/24). Chandra remains blocked by its own live-validation gate.

### Prior position (Slice 80 — committed & merged)

- **Per-attachment material page-selection persistence**, on `slice80-per-attachment-material-page-selections`.
  **COMMITTED `55eb243` + MERGED to `chrome-renderer-v1` (fast-forward) + PUSHED.**
- Slice 80 added the future-facing per-attachment `material_page_selections`
  persistence shape so the next Builder UI slice has a correct backend model to save into. It is
  still applied to nothing.
- **Persisted field:** new top-level `material_page_selections` on `LLMJobRequest`, persisted as a deterministic
  **envelope**: `{"version": 1, "attachments": {"attachment_0": <Slice 78 normalized model>, ...}, "warnings": []}`.
  Keys are SAFE internal attachment indices only (`attachment_<index>`, in request attachment order) — **never**
  filenames/paths/titles. Each value is normalized through `normalize_page_selection`. An envelope (not a flat map) was
  chosen so the "ignored unsafe key" closed warning has a home without ever copying the offending key into output.
- **Why an envelope vs. a flat map.** A flat `{key: model}` map has nowhere safe to record `attachment_key_invalid`
  without echoing the (potentially filename) key it rejected. The envelope carries a top-level closed-vocabulary
  `warnings` list (`selections_malformed`, `attachment_key_invalid`) while keeping per-attachment models intact. The
  normalizer accepts BOTH a flat client map and the persisted envelope on input, so retry round-trips.
- **Precedence (documented, not yet applied):** `material_page_selections` is the preferred per-attachment intent;
  the Slice 79 top-level `material_page_selection` remains the global fallback/default. Both are persisted (after
  normalization) when supplied. Neither is merged into extracted page ranges yet.
- **What changed:** `api/server.py` (new `LLMJobRequest.material_page_selections` field; `_MATERIAL_ATTACHMENT_KEY_RE`;
  `_normalize_material_page_selections` + `_material_selections_envelope` + `_safe_material_page_selections` helpers;
  wired into the JSON handler, the multipart `_parse_llm_request` branch, the retry path, and both
  `job_response`/ask-context echoes) and `pipeline/run_llm_job.py` (new `material_page_selections` param persisted in
  the `Job.create` manifest). Extended `test_scripts/test_page_selection_request_persistence.py` with per-attachment
  helper + endpoint coverage.
- **Both request paths wired + tested** (JSON body and multipart-with-attachments), per the permanent rule.
- **Absent ⇒ byte-identical output.** Absent/None ⇒ empty envelope `{version:1, attachments:{}, warnings:[]}`; job
  artifacts unchanged. Malformed top-level ⇒ empty envelope + `selections_malformed`. Unsafe/filename/path/title keys ⇒
  dropped + `attachment_key_invalid` (key never persisted). Bad entry value / unknown mode / invalid pages ⇒ degrade via
  the pure model's own per-entry warnings. Multipart bad-JSON ⇒ empty envelope. Never raises a 400.
- **Existing behaviour preserved.** The load-bearing, filename-keyed `page_selections` PDF page-range field and Slice 79
  `material_page_selection` are unchanged — verified by `test_page_selections.py` (24/24) and the existing Slice 79
  cases (still passing).
- **Safety.** Persisted/echoed envelope carries only `version`, safe `attachment_<index>` keys, normalized models
  (mode + sorted/deduped positive 1-based ints + closed warnings), and closed top-level warnings. No filenames, paths,
  document text, OCR text, captions, table text, image refs/bytes, base64/data URI, provider payloads, tokens, raw argv,
  sockets, model/mmproj/executable paths, URLs, or raw exception messages — verified with hostile-canary tests over the
  manifest and the response.
- **Scope boundaries.** No frontend/UI. The model is applied to NOTHING — no extraction/OCR routing, content/guide
  generation, visual manifest, render, export, or prompt change. No visual-pilot selection/ranking/classification/cap/
  default/two-key-gate/caption change. No Chandra/Mistral/Gemini/model/provider/cloud call. No direct `clean.md` write
  (all `clean.md` writes still via `JobManager.save_clean_md`). Page-exclusion application, all-figures planner, and
  table reconstruction remain documented future direction only. Chandra remains blocked by its own live-validation
  gate.

### Prior position (Slice 79 — committed & merged)

- **Persist page/slide selection with job requests**, on `slice79-page-selection-request-persistence`. **COMMITTED
  `d4d2513` + MERGED to `chrome-renderer-v1` (fast-forward) + PUSHED.**
- Slice 79 persisted the top-level `material_page_selection`
  normalized model with job requests/manifests so later slices can apply it to extraction/content planning, visual/table
  manifests, and Builder UI. It is still NOT applied to anything yet.
- **Persisted field:** new top-level `material_page_selection` on `LLMJobRequest` — the Slice 78 normalized shape
  `{version, mode, include_pages, exclude_pages, warnings}`. This is a **new, future-facing** field, deliberately
  SEPARATE from the existing load-bearing, filename-keyed `page_selections` PDF page-range field (which still drives
  extraction and is unchanged). A single top-level model was chosen for the smallest safe change; per-attachment mapping
  (`material_page_selections`) is documented as the next step.
- **What changed:** `api/server.py` (new `LLMJobRequest.material_page_selection` field; `_normalize_material_page_selection`
  + `_safe_material_page_selection` helpers; wired into the JSON handler, the multipart `_parse_llm_request` branch, the
  retry path, and both `job_response`/ask-context echoes; imports `normalize_page_selection`) and `pipeline/run_llm_job.py`
  (new `material_page_selection` param persisted in the `Job.create({...})` manifest). New test
  `test_scripts/test_page_selection_request_persistence.py`.
- **Both request-construction paths wired + tested.** Per the permanent rule, the field is parsed on BOTH the JSON body
  path and the multipart-with-attachments path (`_parse_llm_request`), and both are exercised in the test.
- **Absent field ⇒ byte-identical output.** Absent/None normalizes to a clean default `mode: "all"` with no warnings;
  job artifacts are unchanged (only an extra safe manifest key is stored). Existing `page_selections` behaviour
  (normalization, 400 on bad shapes, manifest persistence, retry round-trip) is preserved — covered by the unchanged
  `test_scripts/test_page_selections.py` (24/24).
- **Degrade-never-fail.** Unlike `_normalize_page_selections` (which 400s), `material_page_selection` never raises a 400
  on malformed *content*: unknown mode → `all` + `mode_unknown`; bad page lists → dropped + `selection_malformed`/
  `page_invalid`. Multipart bad-JSON falls back to the default.
- **Safety.** The persisted/echoed model carries only `version`, `mode ∈ {all, include, exclude}`, sorted/deduped
  positive 1-based page integers, and closed-vocabulary warnings. No filenames, paths, document text, OCR text,
  captions, table text, image refs/bytes, base64/data URI, provider payloads, tokens, raw argv, sockets,
  model/mmproj/executable paths, URLs, or raw exception messages — verified with hostile-canary tests over the manifest
  and the response.
- **Scope boundaries.** No frontend/UI. The model is NOT applied to extraction/OCR routing, content/guide generation,
  visual manifest, render, export, or prompts. No visual-pilot selection/ranking/classification/cap/default/
  two-key-gate/caption change. No Chandra/Mistral/Gemini/model/provider/cloud call. No direct `clean.md` write
  (all `clean.md` writes still go through `JobManager.save_clean_md`). Page exclusion application, all-figures planner,
  and table reconstruction remain documented future direction only. Chandra remains blocked by its own
  live-validation gate.

### Prior position (Slice 78 — committed & merged)

- **Page/slide inclusion-exclusion pure model**, on `slice78-page-slide-selection-model`. **COMMITTED `ee04f55` +
  MERGED to `chrome-renderer-v1` (fast-forward) + PUSHED.**
- Slice 78 added the pure, deterministic model for representing user-controlled page/slide inclusion and exclusion per
  attachment.
- **What changed:** new stdlib-only module `pipeline/page_selection_model.py` plus synthetic tests
  `test_scripts/test_page_selection_model.py`. No production wiring.
- **Public API:** `normalize_page_selection(selection, *, page_count=None)`,
  `apply_page_selection(page_numbers, selection)`, and `summarize_page_selection(selection, *, page_count=None)`.
- **Normalized schema:** `{version, mode, include_pages, exclude_pages, warnings}` with `mode ∈ {all, include,
  exclude}`. Pages are positive 1-based integers, deduplicated and sorted. Invalid pages are dropped with warnings;
  with a valid `page_count` out-of-range pages are dropped. `mode: all` includes all pages except exclusions; `mode:
  include` includes only listed pages (then subtracts exclusions); `mode: exclude` includes all except exclusions.
  Unknown mode degrades to `all` with a warning; an empty include list in `include` mode yields an empty included set
  with a warning.
- **Apply behavior:** `apply_page_selection(page_numbers, selection)` returns `{included_pages, excluded_pages,
  effective_mode, warnings}`. The page-number universe is normalized (positive/unique/sorted); invalid values are
  dropped with a warning; pages are never inferred when none are provided.
- **Summary behavior:** `summarize_page_selection(...)` returns counts only — `{version, mode, included_page_count,
  excluded_page_count, explicit_include_count, explicit_exclude_count, warnings}`.
- **Warning tokens (closed vocabulary):** `selection_missing`, `selection_malformed`, `mode_unknown`, `page_invalid`,
  `page_out_of_range`, `page_count_invalid`, `include_empty`, `exclude_overlaps_include`.
- **Safety:** stdlib-only, deterministic, and degrade-never-fail. It never raises and never copies filenames, paths,
  source titles, document text, OCR text, source captions, table text, image refs, image bytes, base64/data URI,
  provider payloads, tokens, raw argv, sockets, model/mmproj/executable paths, URLs, or raw exception messages.
- **Scope boundaries (pure core only):** no API route, no request/job-manifest wiring, no job execution wiring, no
  extraction/OCR routing change, no visual manifest behavior change, no render/export change, no frontend/UI, no prompt
  change, no provider/model/cloud call, no Chandra/Mistral/Gemini integration, and no `clean.md` write. No visual-pilot
  selection/ranking/classification/cap/default/two-key-gate/caption behavior change.
- **Future slices may** persist this model with job requests (now done — Slice 79), expose Builder UI controls, apply
  it to extraction/content planning, apply it to visual/table manifests, and later plan all useful non-table figures
  plus table reconstruction/simplification. Chandra remains blocked by its own live-validation gate.

### Prior position (Slice 77 — committed & merged)

- **Source coverage report artifact writer**, on `slice77-source-coverage-report-artifact`. **COMMITTED `3ebfe54` +
  MERGED to `chrome-renderer-v1` (fast-forward) + PUSHED.**
- **Foundation for revised Full Material Coverage direction.** Slice 76 was committed, fast-forward merged, and pushed
  to trunk as `91e3845`. Slice 77 persists its pure report as the exact-name job artifact
  `source_coverage_report.json`, the first foundation artifact for future page/slide include-exclude controls,
  all useful non-table figure/diagram/graph inclusion from included pages, table reconstruction/simplification, and
  coverage-aware guide generation.
- **What changed:** new writer `pipeline/source_coverage_artifact.py`, new `Job.source_coverage_report_json`, exact-name
  download mapping in `api/server.py`, and `_attach_sources` wiring in `pipeline/run_llm_job.py` after extraction
  metadata and the optional visual manifest are available. The writer consumes
  `build_source_coverage_report(extraction_metadata, *, visual_manifest=None)`.
- **Artifact behavior:** writes deterministic JSON at `<job>/source_coverage_report.json`. Completed PDF extraction
  metadata produces a completed/partial Slice 76 report; skipped/unavailable metadata produces the same safe skipped
  report schema. Visual manifest input is counts-only from sanitized `source_page` values and malformed visual input
  emits closed warnings without failing generation.
- **Safety:** the artifact is sanitized, closed-vocabulary, deterministic, and degrade-never-fail. It does not copy
  filenames, paths, source titles, source text, OCR text, source captions, table text, image refs, image bytes,
  base64/data URI, provider payloads, tokens, raw argv, sockets, model/mmproj/executable paths, URLs, or raw exception
  messages.
- **Scope boundaries:** no frontend/UI; no generic JobDetails row; no generic artifact list exposure; export ZIP
  inclusion deferred; no `clean.md` write; no extraction/OCR routing change; no render/export/prompt/provider/model/
  cloud behavior change; no Chandra/Mistral/Gemini call; no visual-pilot selection/ranking/classification/cap/default/
  two-key-gate/caption behavior change. Page exclusion, all-figures mode, and table reconstruction are documented
  future direction only, not implemented in Slice 77. Chandra remains blocked by its own live-validation gate.
- **Validation:** focused tests `test_scripts/test_source_coverage_report.py` and
  `test_scripts/test_source_coverage_artifact.py` passed, alongside `test_extraction_metadata.py` and
  `test_visual_assets_manifest.py`; Docker build + health + `smoke_release.py` all green before commit.

### Prior position (Slice 76 — committed & merged)
- **Slice 76 (source coverage report pure core) — COMMITTED `91e3845` + MERGED to `chrome-renderer-v1`
  (fast-forward) + PUSHED** on branch `slice76-source-coverage-report-core`. It added stdlib-only
  `pipeline/source_coverage_report.py` with public API
  `build_source_coverage_report(extraction_metadata, *, visual_manifest=None)` plus
  `test_scripts/test_source_coverage_report.py`.
- The core reads no files and imports no extraction/render/provider modules. It emits only `version: 1`,
  `kind: "source_coverage_report"`, status, summary counts, per-source counts/status, and closed warning tokens. It
  never copies filenames, paths, titles, document/OCR/table text, source captions, image refs, image bytes,
  base64/data URI, URLs, provider payloads, tokens, raw argv, socket paths, model/mmproj/executable paths, or raw
  exception messages.
- Slice 76 changed no API route, no job artifact writer, no `clean.md`, no frontend/UI, no export, no extraction/OCR
  routing, no render/prompt/provider/model/cloud behavior, and no visual-pilot behavior.

### Likely next slices after Slice 82 (documentation only)
- Slice 83 — Builder UI for per-attachment page/slide exclusions (save/load `material_page_selections`)
- Slice 84 — Full non-table figure inclusion planner
- Slice 85 — Table reconstruction/simplification policy core (introduces a real table manifest; then apply the
  Slice 82 page filter to it via `material_selection_table_manifest_not_present` → real filtering)
- Slice 86 — Table reconstruction prompt integration or E2E material coverage validation

---

## Slice 75 — **Diverse visual-pilot exit validation**, on `slice75-visual-pilot-diverse-exit-validation`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward) + PUSHED.**

- **Validation / exit-decision slice only.** Slice 75 is intentionally **not** more caption polish, not more
  table/diagram heuristic work, and not a UI slice. It checks whether enough **diverse, manually categorized,
  non-private** operator samples are available to decide whether the default-off visual markdown pilot should remain
  opt-in, become more discoverable, or pause pending a controlled understanding layer such as Chandra. Chandra remains
  blocked by its own live-validation gate.
- **Outcome:** `diverse_visual_pilot_exit_validation: not_run`; `reason:
  non_private_diverse_samples_not_available`. An operator-local sample count was present, but no safe manual mapping
  from samples to the requested closed categories was available in this session, and the slice rules forbid guessing
  categories from local PDFs. No harness run was performed and no trace/render/export artifacts were produced.
- **Target category records (all skipped):** `math_heavy_deck`, `mostly_text_only_pdf`,
  `low_quality_or_scan_like_pdf`, `mixed_diagrams_tables_deck`, and `no_good_figures_deck` each recorded
  `status: skipped`, `skip_reason: sample_not_available`, `trace_artifact_present: not_applicable`,
  `trace_no_leak_sweep: not_applicable`, `effective_max_images: not_applicable`, `inserted_visual_count: 0`,
  all candidate/type/selected counts `0`, `selected_visual_type: none_inserted`,
  `irreplaceable_visual_selected: not_applicable`, `selected_figures_quality: none_inserted`,
  `caption_status: not_applicable`, `graceful_omission: not_applicable`, all render/export booleans
  `not_applicable`, `warnings: [sample_unavailable]`, `failure_category: sample_unavailable`,
  `no_leak_sweep: clean`.
- **Aggregate exit record:** `validated_category_count: 0`, `available_category_count: 0`, `pilot_inserted_count: 0`,
  `graceful_omission_count: 0`, `bad_selection_count: 0`, `caption_safe_count: 0`,
  `pdf_image_visible_count: 0`, `docx_render_ok_count: 0`, `export_png_included_count: 0`,
  `no_leak_sweep: clean`, `exit_recommendation: insufficient_evidence`, `exit_reason:
  diverse_validation_insufficient_sample_count`.
- **Scope / safety:** docs-only (`VISUAL_PILOT_OPERATOR_VALIDATION.md`, this file, `NEXT_CHAT_HANDOFF.md`,
  `DECISIONS.md`). No production pipeline/API/frontend code changed; no harness was added; no selection,
  classification, ranking, cap, caption, export, renderer, OCR-routing, prompt, provider/model/cloud, or UI behavior
  changed. No Chandra/model/provider/cloud call. No committed binary/image/PDF/DOCX/ZIP/runtime output, eval JSON, or
  `visual_markdown_selection_trace.json`. No sample path, filename, document text, OCR text, source caption/table text,
  image bytes, base64, data URI, full URL, provider payload, token, raw argv, model/mmproj/executable path, or raw
  exception recorded.
- **Decision:** keep the visual markdown pilot default-off / opt-in for now due insufficient diverse evidence. The
  morphology loop remains paused; the caption micro-loop is not starting. Next useful step is an operator-provided
  closed-category mapping for multiple known non-private samples, then rerun this exit-validation slice without
  changing visual behavior. **Slice 75 commit `00c3f79`, fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

---

## Slice 74 — **Visual caption / source-page polish (final in-lab visual-pilot polish)**, on `slice74-visual-pilot-caption-page-polish`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Small user-visible polish slice — NOT a new heuristic loop.** Slice 73 proved (on the real, non-private operator
  sample) that the pilot now selects irreplaceable diagrams/figures (`selected_visual_type: diagrams_or_figures_present`,
  `irreplaceable_visual_selected: true`). Per the operator's adjustment, Slice 74 is the **final in-lab caption/page
  polish** for the current visual pilot: it adds a safe, generic italic caption line **below** each inserted visual and
  then the morphology/classification loop stays **paused/frozen**. No selection, ranking, classification, cap, default,
  two-key gate, export, renderer, provider/model/cloud, OCR-routing, prompt, or UI behavior changed. **No separate
  caption-validation follow-up slice will be created.**
- **What changed (one file).** `pipeline/visual_markdown_insertion.py` gains a tiny `_visual_caption_line(source_page)`
  helper (returns exactly `*Source visual, page N.*` when a positive integer page is known, else the page-free
  `*Source visual.*`) and a `build_visual_markdown_block(candidate)` wrapper that appends that caption one blank line
  **below** the unchanged `build_visual_markdown_image(...)` ref. Both insertion entry points
  (`insert_visual_markdown_reference` / `insert_visual_markdown_references`) now emit the block. The caption is a fixed
  closed string + bounded integer page only — it can carry **no** source filename, path, title, raw manifest caption,
  OCR/document/extracted-table text, base64/data URI, provider payload, token, or URL regardless of input. Caption
  construction **degrades-never-fails**: any error falls back to the image ref alone (pre-Slice-74 output).
- **Invariants proven unchanged.** Image asset refs are byte-identical (the `![alt](assets/<slug>.png)` line is
  untouched; the caption is an additional italic line); selected candidate **order**, **count**, and **ranking
  outcomes** match the unmodified selector; default-off output stays byte-identical; the caption never appears unless
  **both** the master flag and per-job opt-in are on; cap stays hard-capped at **2**, default stays **1**; no UI count
  selector; export ref-scan still finds only the safe `assets/<slug>.png` refs; the Slice 68 selection trace is
  unchanged and never carries the caption text.
- **Status flags for the next session:**
  - `visual_pilot_morphology_loop_status: paused_after_real_success`
  - `visual_pilot_polish_scope: final_in_lab_caption_page_polish`
  - `next_recommended_slice: diverse_visual_pilot_exit_validation`
- **Next slice is NOT more visual polish/heuristics.** It should be a **diverse validation / exit-decision** slice across
  multiple document types (one math-heavy deck, one mostly text-only PDF, one low-quality/scan-like PDF if available, one
  deck with diagrams/tables mixed, and one deck with no good figures to verify graceful omission), to decide whether
  visual markdown stays opt-in, becomes more discoverable, or pauses pending a controlled understanding layer (e.g.
  Chandra, which remains blocked by its own live-validation gate).
- **Tests.** New `test_scripts/test_visual_pilot_caption_page_polish.py` (24-scenario coverage: caption presence,
  page label, generic fallback, no filename/path/OCR/table/base64/data-URI/token leak, cap 1 + cap 2, order, refs/count/
  ranking unchanged, default-off byte-identical, both gates off → no caption, tables-when-best + diagram-beats-table
  ranking unchanged, sanitized trace, export ride-along, PDF/DOCX render, degrade-never-fail) — **133 PASS / 0 FAIL /
  0 SKIP in the container** (host shows 1 SKIP: python-docx absent). The full visual-pilot + insertion/render/export/
  options/anki suites and the offline eval pass on host; the production image was rebuilt + recreated, `/api/health`
  `{"ok":true}`, `smoke_release.py` 29/0/0, and the visual-pilot suite (incl. the new test) re-run **inside the
  container** (Pillow + python-docx present, no skips) all green. `git diff --check` clean.
- **Optional real operator caption validation:** `caption_operator_validation: not_run`; `reason:
  non_private_operator_sample_not_available`. The non-private operator sample is not available in this session, so no
  real cap-2 caption rerun was performed and **no sanitized caption-operator result was recorded** (none invented). When
  the sample is next available, it can be inspected inside Slice 74 (no follow-up slice); record only the sanitized
  `caption_operator_validation` closed-vocab fields.
- **Safety / no-leak:** only a fixed caption string + bounded page integer is emitted into the guide; tests build every
  PNG at runtime in a temp dir — nothing binary/image/PDF/DOCX/ZIP/runtime committed; runtime eval result JSONs stay
  gitignored. No real PDF path/filename, document/OCR/table/source-caption text, image bytes, base64, data URI, full URL,
  raw argv, token, or model/mmproj/executable path recorded. **Slice 74 commit `9e92e5a`, fast-forward merged + pushed
  to trunk `chrome-renderer-v1`.**

---

## Slice 73 — **Dense-wrapped-table real operator validation**, on `slice73-visual-pilot-dense-wrapped-operator-validation`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Validation/docs slice only.** Reruns the existing operator harness against the real, **non-private** operator
  sample now that **Slice 72's dense / wrapped-cell two-column table detection fix** is on trunk, then reads Slice 68's
  sanitized selection trace + manually inspects the rendered PDF/HTML/DOCX to record — closed vocabulary only —
  whether the pilot now selects at least one irreplaceable diagram/figure instead of only reconstructable tables.
  **No production pipeline/API/frontend code changed; no heuristic tuned; no ranking/cap/default/gate/render/export/
  extraction-OCR routing change; no model/provider/cloud call.** Docs-only — **no harness correction was needed.**
- **Outcome this session (the long-standing `tables_only` result finally flipped): `dense_wrapped_table_operator_validation:
  run` — `status: ok`, `trace_artifact_present: true`, `trace_no_leak_sweep: clean`, `effective_max_images: 2`,
  `inserted_visual_count: 2`, `safe_candidate_count: 11`, `unsafe_candidate_count: 0`, `selected_count: 2`,
  `type_counts {diagram_or_figure: 9, reconstructable_table: 2, unknown: 0, decorative_or_low_information: 0}`,
  `selected_visual_type: diagrams_or_figures_present`, `irreplaceable_visual_selected: true`, `selected_figures_quality:
  all_useful_or_acceptable`, `selection_explanation: diagrams_selected_after_dense_table_fix`,
  `pdf_render_ok/pdf_image_visible/docx_render_ok/export_zip_ok/export_png_included: true`,
  `warnings: [multiple_figures_present_one_inserted]`, `failure_category: none`, `no_leak_sweep: clean`.**
- **What unblocked it.** The trace's `type_counts` still reads `diagram_or_figure: 9` / `reconstructable_table: 2`,
  but the two reconstructable two-column definition tables that Slice 71 *selected* are now **deprioritized** behind
  the diagram tier (`rejection_reason_counts.deprioritized_reconstructable_table: 2`), so diagram-first ranking now
  reaches the genuine schematic figures. Both selected candidates are `classified_diagram_or_figure` with
  `selection_reason: selected_by_diagram_first_ranking`; manual ground-truth confirms both are legible,
  content-bearing, non-decorative graphics from distinct source pages that render visibly in PDF/DOCX and ride along
  in the export ZIP.
- **Decision gate / next work (recorded, not started):** `decision_gate: irreplaceable_diagram_selected_on_real_sample`;
  `next_recommended_slice: visual_placement_or_citation_polish_may_now_be_considered` — because an irreplaceable
  diagram/figure is finally selected on the real sample, future visual work **may** now consider placement/citation
  polish as a separately-designed slice (a *may*, not a mandate; classification precision can be revisited if other
  samples regress).
- **Hard boundaries honored:** no cap above 2 (default still **1**, cap still hard-capped at **2**), no UI count
  selector, no Chandra/Mistral/Gemini/cloud OCR, no model/provider/`llama-server` call, no image generation, no
  OCR-routing/renderer/prompt/export change, no new API route. Chandra remains blocked by its own live-validation gate.
- **Safety / no-leak:** only sanitized closed-vocab + bounded-numeric fields recorded; **no** real PDF path/filename,
  document text, OCR text, source caption/table text, image bytes, base64, data URI, full URL, raw argv, token,
  model/mmproj/executable path, provider payload, or raw exception. The runtime
  `visual_markdown_selection_trace.json` was **inspected but not committed**; nothing binary/image/PDF/DOCX/ZIP/
  runtime committed. **Slice 73 commit `76e837b`, fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

---

## Slice 72 — **Dense ruled / wrapped-cell two-column table detection**, on `slice72-visual-pilot-dense-wrapped-table-detection`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Production classification slice (precision only).** Slice 71's real-sample validation showed Slice 70 measurably
  improved table-vs-diagram classification (the trace's type buckets split: `diagram_or_figure: 9`,
  `reconstructable_table: 2`, where Slice 69 read 11 / 0) but the two *selected* visuals were **still** reconstructable
  two-column definition tables. Root cause: those tables are **densely ruled with wrapped multi-line cells**, so each
  column's antialiased wrapped lines merge into too FEW separated horizontal text bands for Slice 70's `two_col_split`
  per-column band guard (≥ 3 bands) to fire — they fall through to `diagram_or_figure` and lead the diagram tier.
- **What changed:** one more bounded, deterministic, **pixel-only** signal — `dense_wrapped_two_col` — added to the
  existing `extracted_figure` crop analyzer (`pipeline/visual_markdown_insertion.py`). It does **not** rely on band
  count; it pairs the two-column structure with two guards a diagram cannot fake: a **persistent clean vertical gutter**
  (`_gutter_consistency` — a diagram's connectors/diagonals break it) and per-column **text richness**
  (`_column_text_richness` — avg ink-runs per inked row: several words per row, not a continuous shape outline). It
  fires only when there are exactly two substantial dense columns, a real persistent gutter, and both columns are
  text-rich. Wired as a fourth path inside `_looks_like_reconstructable_table`, so the public classification token and
  the Slice 68 trace schema are unchanged.
- **Effect (verified by tests):** dense / wrapped-cell / ruled / lightly-ruled two-column definition tables now
  classify as `reconstructable_table` (incl. the *merged-band* case where Slice 70's `two_col_split` cannot fire);
  labeled diagrams, flowcharts, and irregular diagrams stay `diagram_or_figure` (text presence alone never flips a
  diagram); a diagram/figure still beats a reconstructable table at cap 1 and ranks first at cap 2; tables are still
  selected when best/only. Default remains **1**; hard cap remains **2**; two-key gate, render, export ride-along,
  extraction/OCR routing, prompts, and `/api/options` all unchanged. No Chandra/Mistral/Gemini/model/provider/cloud
  call; no UI/frontend change. Chandra remains blocked by its own live-validation gate.
- **Validation:** `python -m compileall api pipeline test_scripts` clean; the new
  `test_visual_pilot_dense_wrapped_table_detection.py` (81 PASS / 0 FAIL, cap-1 and cap-2) plus the full visual-pilot
  suite, `validate_visual_pilot_operator_sample.py --self-test`, the insertion/render/export/options/anki tests, and the
  offline eval all pass on host; the production image was rebuilt + recreated, `/api/health` `{"ok":true}`,
  `smoke_release.py` 29/0/0, and the visual-pilot suite was re-run **inside the container** (Pillow present — no skips:
  multifigure 78, quality_gate 54) all green. `git diff --check` clean.
- **Optional real operator revalidation: NOT run in the Slice 72 session** — the non-private operator sample was not
  available then, so no real cap-2 rerun was performed and no sanitized operator result was recorded (none invented).
  **Slice 73 has since run that revalidation and recorded the flipped `diagrams_or_figures_present` result above.**
- **Safety / no-leak:** only bounded numeric pixel summaries and closed-vocab tokens are produced; the classifier never
  OCRs, never calls a model/provider/network, never base64/serializes/logs image bytes, records no path or source text,
  and adds **no** new artifact (the Slice 68 trace is the only one). Tests build every PNG at runtime in a temp dir —
  nothing binary/image/PDF/DOCX/ZIP/runtime committed; runtime eval result JSONs stay gitignored. **Slice 72 is
  COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

---

## Slice 71 — **Table-vs-diagram precision operator validation**, on `slice71-visual-pilot-table-diagram-operator-validation`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Validation/docs slice only.** Reruns the existing operator harness against the real, **non-private** operator
  sample now that **Slice 70's table-vs-diagram classifier precision fix** is on trunk, then reads Slice 68's
  sanitized selection trace + manually inspects the rendered PDF/HTML/DOCX to record — closed vocabulary only —
  whether the pilot now selects an irreplaceable diagram/figure instead of only reconstructable tables. **No
  production pipeline/API/frontend code changed; no heuristic tuned; no ranking/cap/default/gate/render/export/
  extraction-OCR routing change; no model/provider/cloud call.** Docs-only — **no harness correction was needed.**
- **Outcome this session (honest): `table_diagram_precision_operator_validation: run` — `status: ok`,
  `trace_artifact_present: true`, `trace_no_leak_sweep: clean`, `effective_max_images: 2`, `inserted_visual_count: 2`,
  `safe_candidate_count: 11`, `unsafe_candidate_count: 0`, `selected_count: 2`,
  `type_counts {diagram_or_figure: 9, reconstructable_table: 2, unknown: 0, decorative_or_low_information: 0}`,
  `selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`, `selected_figures_quality:
  all_useful_or_acceptable`, `selection_explanation: tables_still_misclassified_as_diagram_or_figure`,
  `pdf_render_ok/pdf_image_visible/docx_render_ok/export_zip_ok/export_png_included: true`,
  `warnings: [multiple_figures_present_one_inserted]`, `failure_category: none`, `no_leak_sweep: clean`.**
- **Slice 70 measurably improved classification but did not yet generalize.** The trace's `type_counts` is **no longer
  collapsed** — `diagram_or_figure: 9` **and** `reconstructable_table: 2` (Slice 69 read 11 / 0), and the 2 typed
  tables were correctly **deprioritized** (`deprioritized_reconstructable_table: 2`). **But manual inspection
  ground-truths that both *selected* visuals are still reconstructable two-column definition tables** — they are
  densely ruled with wrapped multi-line cells, so the Slice 70 two-column-split guard (several *separated* row bands
  per column) does not fire and they still type as `diagram_or_figure`, leading the diagram tier in priority order.
  **Genuine irreplaceable diagrams/figures were present and correctly extracted among the safe candidates but were
  NOT selected** — so this is still **classification precision**, not extraction and not pure ranking.
- **Next work (recorded, not started):** `continue_table_vs_diagram_classification_precision` — keep improving the
  deterministic local classifier for densely-ruled / wrapped-text two-column tables (or design a controlled
  understanding layer in a separate slice). **Do not** proceed to UI polish or cap expansion until an irreplaceable
  diagram/figure is selected in real validation, or there is a deliberate product decision to accept tables.
- **Hard boundaries honored:** no cap above 2, no UI count selector, no Chandra/Mistral/Gemini/cloud OCR, no
  model/provider/`llama-server` call, no image generation, no OCR-routing/renderer/prompt/export change, no new API
  route. Chandra remains blocked by its own live-validation gate.
- **Safety / no-leak:** only sanitized closed-vocab + bounded-numeric fields recorded; **no** real PDF path/filename,
  document text, OCR text, source caption/table text, image bytes, base64, data URI, full URL, raw argv, token,
  model/mmproj/executable path, provider payload, or raw exception. The runtime
  `visual_markdown_selection_trace.json` was **inspected but not committed**; nothing binary/image/PDF/DOCX/ZIP/
  runtime committed. **Slice 71 is NOT committed.**

---

## Slice 70 — **Table-vs-diagram visual-classification precision**, on `slice70-visual-pilot-table-diagram-precision`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Production classification slice (precision only).** Slice 69's real-sample selection trace localized the
  remaining failure to *classification*, not extraction/ranking/cap/export/rendering/UI: **all 11 safe candidates were
  classified `diagram_or_figure`** while the two *selected* visuals were, by manual inspection, clean two-column
  definition/glossary **tables** (`selection_explanation: tables_misclassified_as_diagram_or_figure`). Slice 70
  improves the deterministic, bounded, pixel-only visual-type classifier so **two-column / glossary / definition
  tables classify as `reconstructable_table`** instead of `diagram_or_figure`, giving Slice 64's diagram-first
  ranking a real signal — while genuine diagrams/figures (including labeled ones) stay `diagram_or_figure`.
- **Root mechanism fixed.** A glossary/definition table has **variable-height rows** (multi-line definitions wrap),
  so its horizontal text bands are *not* evenly spaced; Slice 66's text-grid path requires a *regular* row rhythm and
  missed it, and with no drawn rules the lightly-ruled path missed it too — so it fell through to
  `diagram_or_figure`. Slice 70 adds one bounded pixel-only feature, **`two_col_split`**, that fires only when the
  crop has **exactly two substantial text columns separated by a real gutter** (whitespace or a thin drawn divider)
  **AND each column independently contains several separated horizontal text bands**. The per-column row-band
  requirement is the guard that keeps a labeled **diagram** a diagram — text presence alone never flips a diagram;
  row-spacing regularity is intentionally **not** required, which is what now catches variable-height glossary rows.
- **Behavior:** two-column/glossary/definition tables → `reconstructable_table`; lightly-ruled two-column, text-band
  central-gutter, and strong-grid tables remain `reconstructable_table`; irregular labeled diagrams, flowcharts, and
  diagrams whose labels make text-like dark bands remain `diagram_or_figure`. **Diagrams beat reconstructable tables**
  (cap 1 picks the diagram; cap 2 with one of each selects both, diagram first; cap 2 with two diagrams + a table
  selects the two diagrams). **Tables are still allowed when best/only.** The existing Slice 68 selection trace
  reflects the improved classification automatically (`type_counts` no longer collapse) — **no artifact schema
  change**.
- **Hard boundaries honored:** cap still hard-capped at **2**, default still **1**, `fitz_local` + `extracted_figure`
  only, safe `assets/<slug>.png` only, file-inside-job-dir gate, Chandra/Mistral/`page_visual_signal` still rejected,
  degrade-never-fail (no Pillow / unreadable / too-small ⇒ `unknown`, prior behavior). **No** frontend/UI change, **no**
  `/api/options` change, **no** export/cap/OCR-routing/renderer/prompt/extraction change, **no** model/provider/cloud/
  `llama-server` call, **no** new API route, **no** committed binary/image/PDF/DOCX/ZIP/runtime fixture (every PNG is
  runtime-built in a temp dir). Chandra remains blocked by its own live-validation gate.
- **Tests:** new `test_scripts/test_visual_pilot_table_diagram_precision.py` (24-point coverage, **70/70** pass host;
  **70/70** with `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`). Full visual-pilot suite + operator self-test +
  insertion/render/export/anki/options + `eval --offline --all` (no regression, 0.8306→0.8306) green host-side; the
  rebuilt+recreated container is `/api/health` `{"ok":true}` and the in-container visual suite is green
  (precision 70/0, selection-trace 56/0, light-table 66/0, type-ranking 64/0, multifigure 78/0, quality-gate 54/0,
  operator self-test PASS). `git diff --check` clean. **Slice 70 is NOT committed.**
- **Release smoke (`smoke_release.py`):** `release_smoke_status: transient_failure_then_green_on_rerun` ·
  `release_smoke_failure_category: outline_ordering_check` · `slice70_visual_tests: green` ·
  `slice70_docker_health: green` · `slice70_not_cause: confirmed`. A first run reported **28/29** with a single
  `outline_ordering_check` miss (`pos=[-1,-1,-1]`); an unchanged rerun on the same Slice 70 branch/container passed
  **29/0/0** with that same check green — i.e. a flaky LLM section-ordering check, **not** caused by Slice 70 (which
  only adds a deterministic pixel-only visual-type feature and cannot affect generated outline text). No raw
  generated guide content recorded.
- **Safety / no-leak:** classifier reads only bounded non-sensitive pixel summaries; never OCRs, never base64/
  serializes/logs image bytes, never records a path or source text, adds no artifact. No real PDF path/filename,
  document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable path, or
  provider payload anywhere.

---

## Slice 69 — **Real operator selection-trace audit**, on `slice69-visual-pilot-selection-trace-operator-audit`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Validation/docs slice only.** Reruns the existing operator harness against the real, **non-private**
  operator sample with **Slice 68's sanitized selection trace** (`visual_markdown_selection_trace.json`) enabled,
  then reads that trace to explain *why* the real sample still selects tables instead of irreplaceable diagrams —
  without leaking source material. **No production pipeline/API/frontend code changed; no new visual behavior; no
  ranking/cap/default/gate/render/export/extraction-OCR routing change; no model/provider/cloud call.** Docs-only —
  **no harness correction was needed.**
- **Outcome this session: `selection_trace_operator_audit: run` — `status: ok`, `trace_artifact_present: true`,
  `trace_no_leak_sweep: clean`, `effective_max_images: 2`, `inserted_visual_count: 2`, `safe_candidate_count: 11`,
  `unsafe_candidate_count: 0`, `selected_count: 2`.** The non-private sample was available, so the cap-2 harness
  **was** run inside the rebuilt Slice 68 container; the trace + rendered PDF/HTML/DOCX were copied to a host folder
  and inspected by hand. Trace was checked for leaks **before** any field was transcribed (clean).
- **Root cause finally localized — it is classification, not extraction or pure ranking.** The trace's `type_counts`
  shows **all 11 safe candidates classified `diagram_or_figure`** (`reconstructable_table: 0`, `unknown: 0`,
  `decorative_or_low_information: 0`). Manual inspection ground-truths the discrepancy: the two **selected** visuals
  are clean two-column definition/glossary **tables** (`selected_visual_type: tables_only`,
  `irreplaceable_visual_selected: false`, `selected_figures_quality: all_useful_or_acceptable`), and at least one
  **genuinely irreplaceable schematic diagram was present among the safe candidates but was NOT selected**. Because
  the pixel classifier over-accepts reconstructable tables as `diagram_or_figure`, every candidate carries the same
  `visual_type_score: 3`, diagram-first ranking has nothing to discriminate on, and pure quality score picks the
  clean tables (`quality_score: 1.2`) ahead of the real diagram. `selection_explanation:
  tables_misclassified_as_diagram_or_figure`.
- **Next work (recorded, not started):** `improve_visual_type_classification_table_vs_diagram_precision` — the
  deterministic local pixel classifier must separate reconstructable tables from genuine diagrams so diagram-first
  ranking gets a real signal. **Not** extraction (diagrams present) and **not** a blind ranking/threshold change
  (ranking is signal-starved, not wrong). The trace is **sufficient** to localize this; its per-candidate
  rejection-reason coverage is sparse (only `rejected_secondary_below_quality_floor: 1` for nine unselected
  candidates) — a possible future *trace* refinement, not a reason to guess heuristics.
- **Hard boundaries honored:** no cap above 2, no UI count selector, no Chandra/Mistral/Gemini/cloud OCR, no
  model/provider/llama-server call, no image generation, no OCR-routing/renderer/prompt/export change, no new API
  route. **Do not proceed to UI polish or cap expansion** until an irreplaceable diagram/figure is selected in real
  validation, or there is a deliberate product decision to accept tables.
- **Safety / no-leak:** only sanitized closed-vocab + bounded-numeric fields recorded; **no** real PDF path/filename,
  document text, OCR text, source caption/table text, image bytes, base64, data URI, full URL, raw argv, token,
  model/mmproj/executable path, provider payload, or raw exception. The runtime
  `visual_markdown_selection_trace.json` was **inspected but not committed**; nothing binary/image/PDF/DOCX/ZIP/
  runtime committed. **Slice 69 is NOT committed.**

---

## Slice 68 — **Sanitized visual-pilot selection trace / candidate audit**, on `slice68-visual-pilot-sanitized-selection-trace`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Production diagnostic slice (visibility only).** Slice 67 proved the real post-Slice-66 cap-2 run still
  selected **two useful-but-reconstructable tables only** (`selected_visual_type: tables_only`,
  `irreplaceable_visual_selected: false`); the next problem is **visibility, not more blind heuristic tuning**.
  Slice 68 adds a bounded, sanitized **candidate-audit artifact** so future real operator runs can explain *why*
  diagrams were not selected — which candidates existed, their classified visual type, and why the chosen tables
  outranked them. **Diagnostic only — ranking/cap/default/two-key-gate/UI/render/export/extraction-OCR routing all
  unchanged; no model/provider/cloud call added.**
- **What changed (one production file):** `pipeline/visual_markdown_insertion.py`. Added
  `build_visual_markdown_selection_trace(...)` + `_emit_selection_trace(...)` (and small pure helpers), and wired
  `_emit_selection_trace` into `apply_visual_markdown_pilot` at the three both-gates-pass exits (inserted,
  insert-failed, no-candidate). Selection logic, the `_pick_candidates`/`_best_typed` ranking core, the cap reader,
  and the two-key gate are **byte-for-byte unchanged** — the trace is built by an independent, read-only pass that
  never influences the decision.
- **Exact artifact:** `visual_markdown_selection_trace.json`, written to the job dir **only** when the global
  master env switch is ON **and** the job opted in **and** candidate selection was attempted (including the
  no-candidate / low-quality skip — that is exactly the case worth auditing). **Never** written when the master
  switch is off, the job did not opt in, or the pilot code is not reached. Build/write is wrapped degrade-never-fail
  — a trace problem can never fail generation and leaves no partial file.
- **Sanitized + bounded.** Top level is whitelisted: `schema_version`, `status`, `reason`, `effective_max_images`,
  `inserted_visual_count`, `selected_candidates`, `candidate_summary`, `warnings`. Per-selected-candidate carries
  only safe fields (`asset_id`, safe `assets/<slug>.png` `asset_ref`, `source_page`, `source_provider`,
  `visual_type`, `visual_type_score`, `classification`, `quality_score`, `quality_reasons`, `placement`, `rank`,
  `selected`, `selection_reason`); `candidate_summary` is counts only (`total_manifest_assets`,
  `safe_candidate_count`, `unsafe_candidate_count`, `selected_count`, `type_counts`, `rejection_reason_counts`). All
  reasons are **closed-vocabulary tokens** (`selected_by_diagram_first_ranking` · `selected_by_quality_ranking` ·
  `selected_by_priority_order` · `rejected_low_quality` · `rejected_unsafe_ref` · `rejected_wrong_provider` ·
  `rejected_wrong_asset_type` · `rejected_duplicate_asset_ref` · `rejected_duplicate_asset_id` ·
  `rejected_secondary_below_quality_floor` · `deprioritized_reconstructable_table` · `classified_*`). **No** absolute
  path, source filename, document/OCR/caption/extracted-table text, image bytes, base64, data URI, provider payload,
  raw exception, URL, token, raw argv, or model/mmproj/executable path is ever included. Chandra/Mistral/
  page_visual_signal candidates are **counted/rejected** but never written raw.
- **New focused test:** `test_scripts/test_visual_pilot_selection_trace_sanitized.py` (20-point coverage:
  written/not-written gating, default cap 1 / env cap 2, selected+inserted counts, tables-only vs diagram-selected
  via safe tokens, safe/unsafe counts, unsafe-ref counted-not-raw, foreign-provider rejection, full no-leak sweep,
  trace-failure-never-fails-generation, default-off byte-identical, two-key gate unchanged, cap constants unchanged,
  export excludes the trace, pilot does not write `clean.md`). **56/56 pass host and in-container.**
- **Validation:** `compileall api pipeline test_scripts` OK; the full visual-pilot suite + operator self-test +
  insertion/render/export/anki/options + `eval --offline --all` all green host-side; rebuilt + recreated the
  container, `/api/health` `{"ok":true}`, `smoke_release.py` **29/29**, and the visual-pilot suite re-run
  in-container (selection-trace 56/0, light-table 66/0, type-ranking 64/0, multifigure 78/0, quality-gate 54/0,
  operator self-test PASS). `git diff --check` clean. The container test copies were removed after the run.
- **Decision recorded:** instrument before tuning. The next visual slice can read this trace on a real run to decide
  whether the diagrams are being **classified** wrong (type detection) or **ranked/capped** wrong (selection), rather
  than guessing. **Do not** change ranking/cap/default in this slice; **do not** expand beyond hard cap 2, add a UI
  count selector, or add Chandra/Mistral/Gemini/model/provider/cloud integration. Chandra remains blocked by its own
  live-validation gate.
- **Safety / no-leak:** no real PDF path/filename, document text, OCR text, image bytes, base64, data URI, full URL,
  raw argv, token, model/mmproj/executable path, or provider payload recorded; nothing binary/image/PDF/DOCX/ZIP/
  runtime committed. **Slice 68 is NOT committed.**

---

## Slice 67 — **Improved-light-table real operator validation**, on `slice67-visual-pilot-light-table-operator-validation`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Validation/docs slice only.** Records whether Slice 66's strengthened lightly-ruled / text-heavy table
  detection lets the **real** non-private operator sample finally select a hard-to-reconstruct diagram/figure
  instead of tables only. **No production pipeline/API/frontend code changed; no new visual behavior added.**
  **Docs-only — no harness correction was needed.**
- **Outcome this session: `light_table_operator_visual_quality_review: run` — `status: ok`,
  `inserted_visual_count: 2`, `selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`,
  `selected_figures_quality: all_useful_or_acceptable`.** The non-private operator sample was available again, so
  the cap-2 operator harness **was** run inside the rebuilt Slice 66 container
  (`GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1`, `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION=1`,
  `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`); the rendered PDF/HTML/DOCX were copied to a host folder and inspected
  by hand. All render/export checks passed (`pdf_render_ok` / `pdf_image_visible` / `docx_render_ok` /
  `export_zip_ok` / `export_png_included: true`), `warnings: [multiple_figures_present_one_inserted]`,
  `failure_category: none`, `no_leak_sweep: clean`. Full record + interpretation in
  `VISUAL_PILOT_OPERATOR_VALIDATION.md`.
- **Honest outcome — improved light-table detection did *not* change the real selection.** The two inserted
  visuals are still **useful/acceptable but reconstructable tables**; the genuinely irreplaceable visual content
  present elsewhere in the sample was **not** selected. Slice 66 improved the synthetic / light-table detection
  tests, but the real cap-2 run still lands on **two useful tables only** — readable and useful, yet
  reconstructable from extracted text. **No irreplaceable diagram/figure was selected, so visual-type selection is
  still not solved for the real sample.** `decision_gate: light_table_detection_did_not_change_real_outcome` ·
  `next_recommended_slice: add_sanitized_selection_trace_before_more_heuristics`.
- **Decision:** **do not proceed to UI polish or cap expansion.** Before further heuristic tuning, add a
  **sanitized selection trace / candidate audit** so future runs can explain (in closed-vocab / bounded-numeric form
  only) *why* diagrams were not selected — which candidates existed, their classified visual type, and why the
  chosen tables outranked them. **Do not expand beyond cap 2. Do not add a UI count selector. Do not add
  Chandra/Mistral/Gemini/model/provider/cloud integration.** Chandra remains blocked by its own live-validation
  gate.
- **Validation:** docs-only; `git diff --check` clean. The harness was **not** touched (no `compileall` /
  `--self-test` needed beyond Slice 66's already-green run). No production behavior, no frontend/UI, no
  extraction/OCR-routing/prompt/render/export change, no Chandra/model/provider/cloud call.
- **Safety / no-leak:** only the sanitized closed-vocabulary fields recorded — no real PDF path/filename, document
  text, OCR text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable path, or provider
  payload; nothing binary/image/PDF/DOCX/ZIP/runtime committed. **Slice 67 is NOT committed.**

---

## Slice 66 — **Lightly-ruled / text-heavy table detection**, on `slice66-visual-pilot-light-table-detection`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Production-behavior slice (visual-type detection only).** Slice 65's real operator validation proved the
  Slice 64 diagram-first ranking **did not change the real sample outcome** — the two selected visuals stayed
  **useful tables only** (`selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`). **Root
  cause:** the Slice 64 classifier only recognized a **strong full horizontal+vertical rule grid** as a table, so
  the sample's **lightly-ruled / text-heavy** tables stayed `unknown` and every candidate sat in one visual-type
  tier — ranking had no signal to act on. Slice 66 improves the **deterministic, local, pixel-only** visual-type
  detection so a lightly-ruled / reconstructable table is classified as `reconstructable_table` rather than
  `unknown`, giving diagram-first ranking a real signal. **This is detection work *before* any UI/placement polish,
  exactly as Slice 65 recommended.**
- **What changed (one file):** `pipeline/visual_markdown_insertion.py`. Extended the bounded grayscale feature
  summary (`_summarize_gray_pixels`) with a **softer-ink** (`_LT_INK`) horizontal **text-band rhythm** and a
  vertical **column-gutter** structure, and added a conservative `_looks_like_reconstructable_table(...)` rule
  (plus pure helpers `_profile_runs`, `_runs_regular`, `_count_col_blocks`) wired into
  `_classify_visual_type_from_features` **after** the existing strong-grid table rule and **before** the diagram
  rule. Two dual-signal table paths: (a) **text-grid** — a regular repeated text-band rhythm *and* a multi-column
  gutter structure; (b) **lightly-ruled** — multiple full horizontal rules *without* a strong vertical-rule grid,
  backed by either the row rhythm or the column structure. A genuine diagram (irregular row spacing, no clean
  full-height column gutters, no repeated horizontal rules) satisfies neither and stays `diagram_or_figure`.
- **Behavior outcome:** lightly-ruled and text-band (weak/no vertical rule) tables now classify as
  `reconstructable_table`; the diagram still classifies as `diagram_or_figure`; a diagram **beats** a lightly-ruled
  table at cap 1, and at cap 2 a diagram is selected **before** a table. **Tables remain allowed when they are the
  best/only useful visual.** Same hard limits as Slice 64: pixel-only over the already-safe job-dir-contained crop,
  **no OCR / model / provider / network / cloud / `llama-server` / image-gen**, no bytes/base64/data-URI/path/text
  retained, **no new artifact**; Pillow-absent / unreadable / too-small ⇒ `unknown` ⇒ **byte-identical fallback**
  to the prior Slice 60/62 quality-only selection.
- **Invariants unchanged:** global master flag + per-job opt-in two-key gate, **default cap 1**, **hard cap 2**
  (server-side only), `fitz_local` / `extracted_figure`-only, unsafe-ref / Chandra / Mistral / `page_visual_signal`
  still rejected, decorative/low-information rejection still dominates, default-off output **byte-identical**,
  export ride-along unchanged. **No frontend/UI, no `/api/options`/route change, no cap change, no extraction/
  OCR-routing/prompt/render/export behavior change.** Chandra remains blocked by its own live-validation gate.
- **Tests:** new `test_scripts/test_visual_pilot_light_table_detection.py` (runtime-generated tiny PNG fixtures in
  temp dirs — never committed) covering strong-grid / lightly-ruled / text-band tables → `reconstructable_table`,
  diagram → `diagram_or_figure`, diagram-beats-light-table at cap 1, cap-2 diagram-first / two-diagrams /
  only-tables, decorative rejection, unknown-preserves-prior, analysis-failure degrade, unsafe-ref / blocked-provider
  exclusion, determinism, two-key gate, default-off byte-identical, default-1 / hard-cap-2, export ride-along, and a
  full no-leak sweep. Existing visual-type ranking / multifigure / quality-gate / insertion / render / export /
  options / e2e / anki tests and the operator-sample `--self-test` all still pass unchanged.
- **Validation:** `python -m compileall api pipeline test_scripts` clean; full visual + anki + offline eval suite
  green on host; **Docker** `build` + `up` + `/api/health` + `smoke_release.py` (29/0) green; the visual tests also
  re-run **inside the production container** (Pillow 12 present) with **no skips** (light-table 66/0, ranking 64/0,
  multifigure 78/0, quality-gate 54/0, operator `--self-test` PASS); copied-in test scripts removed from the
  container afterward; `git diff --check` clean.
- **Optional real operator revalidation:** **not run in this slice** — the non-private operator sample is not
  available in this session. The desired outcome (`selected_visual_type: diagrams_or_figures_present` /
  `irreplaceable_visual_selected: true`) is **not assumed**; whether the strengthened detection actually flips the
  real sample must be confirmed by re-running the cap-2 operator harness when the sample is available, and recorded
  only if true after manual inspection.
- **Safety / no-leak:** only closed-vocab tokens and bounded numeric features in info dicts / tests — no real PDF
  path/filename, document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token, or
  model/mmproj/executable path in any doc/test/artifact/log; **nothing binary/image/PDF/DOCX/ZIP/runtime committed**.
  **Slice 66 is NOT committed.**

---

## Slice 65 — **Diagram-first real operator validation record**, on `slice65-visual-pilot-diagram-first-operator-validation`. **COMMITTED + MERGED to `chrome-renderer-v1`.**

- **Validation/docs slice.** Records a real, sanitized operator validation of the **Slice 64 diagram-first
  ranking** behavior against the same already-supplied non-private operator sample. Slice 64 proved diagram-first
  ranking **synthetically and in Docker** but explicitly left the **real** operator revalidation *not run*; Slice
  65 closes that one gap. **No production pipeline/API/frontend code changed; no new visual behavior added.**
  **Docs-only — no harness correction was needed.**
- **What was done:** used the rebuilt Slice 64 container, ran the existing operator harness
  (`validate_visual_pilot_operator_sample.py`) with `GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1`,
  `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION=1`, `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2` against the non-private sample
  (copied in/out via the running compose container; sample removed from the container afterward), copied the
  rendered PDF/HTML/DOCX to a host folder, and inspected the inserted visuals by hand.
- **Recorded (sanitized, closed vocab):** `diagram_first_operator_visual_quality_review: run` · `status: ok` ·
  `pilot_inserted: true` · **`inserted_visual_count: 2`** · **`selected_visual_type: tables_only`** ·
  **`irreplaceable_visual_selected: false`** · **`selected_figures_quality: all_useful_or_acceptable`** ·
  `pdf_render_ok/pdf_image_visible/docx_render_ok/export_zip_ok/export_png_included: true` ·
  `warnings: [multiple_figures_present_one_inserted]` · `failure_category: none` · `no_leak_sweep: clean`.
- **Honest outcome — diagram-first did *not* change the real selection.** The two inserted visuals are still
  **reconstructable tables**, and the genuinely irreplaceable visual content present elsewhere in the sample was
  **not** selected. **Root cause (sanitized):** the Slice 64 ranking only re-orders when its deterministic pixel
  classifier can tell a `reconstructable_table` from a `diagram_or_figure`; the table-grid heuristic fires only on
  a strong regular horizontal **and** vertical rule grid, and it did **not** recognize these **lightly-ruled**
  tables as tables — so every safe candidate landed in the same visual-type tier and selection fell back
  **byte-for-byte** to the prior Slice 60/62 quality-and-order pick. The classifier behaved exactly as designed
  (no regression); it simply had no clear table-vs-diagram signal to act on here. `decision_gate:
  diagram_first_ranking_did_not_change_real_outcome` · `next_recommended_slice:
  improve_visual_type_detection_before_ui_polish`.
- **Decision:** because `selected_visual_type: tables_only`, the next visual slice should **continue visual-type
  ranking / detection work before any UI or placement polish** — specifically strengthen table-vs-diagram
  detection (recognize borderless/lightly-ruled tables and/or detect genuine diagrams more strongly) so the
  ranking has a real signal. **Do not expand beyond cap 2, no UI count selector, no Chandra/Mistral/Gemini/
  model/provider/cloud integration.** Default remains exactly 1; hard cap remains 2.
- **Out of scope (unchanged):** no frontend/UI, no `/api/options`/route change, no cap change, no
  extraction/OCR-routing/prompt/render/export behavior change, no model/provider/cloud/`llama-server`/image-gen
  call. Chandra remains blocked by its own live-validation gate.
- **Safety / no-leak:** only sanitized closed-vocab fields recorded — no real PDF path/filename, document text,
  OCR text, image bytes, base64, data URI, full URL, raw argv, token, or model/mmproj/executable path in any
  doc/test/artifact/log; the host review folder lives outside the repo and **nothing binary/image/PDF/DOCX/ZIP/
  runtime was committed**. **Slice 65 is NOT committed.**

---

## Slice 64 — **Prefer diagrams over reconstructable tables (visual-type ranking)**, on `slice64-visual-pilot-diagram-first-ranking`. **COMMITTED + MERGED to `chrome-renderer-v1`.**

- **Production-behavior slice (ranking only).** Slice 63 proved the cap-2 plumbing on a real sample but
  selected **tables only**; tables are useful yet often **reconstructable** from extracted text into clean
  generated tables. Slice 64 adds a conservative, deterministic **visual-type ranking** so a hard-to-reconstruct
  **diagram/figure** is preferred over a reconstructable **table** when both are available — while a good table
  is still selected when it is the **best/only** useful visual. **Scope is ranking, not expansion.**
- **What changed (one file):** `pipeline/visual_markdown_insertion.py`. Added a pixel-only visual-type
  classifier (`classify_visual_markdown_candidate_type_for_pilot`), a priority scorer
  (`score_visual_type_priority_for_pilot`), and wired a **type-first / quality-second** selection tier into the
  existing single- and multi-figure pickers (`_pick_candidate`, `_pick_candidates` → `_select_multi`, via a new
  `_best_typed` helper). All Slice 60 quality gating and Slice 62 cap/secondary-floor/page-diversity rules are
  unchanged underneath.
- **Closed visual-type vocabulary:** `diagram_or_figure` · `reconstructable_table` ·
  `decorative_or_low_information` · `unknown`. **Preferred order:** `diagram_or_figure > reconstructable_table >
  unknown > decorative_or_low_information`.
- **How classification works (safe, deterministic):** only the **already-safe, already-job-dir-contained**
  `assets/<slug>.png` crop is opened (re-validated for ref + realpath containment first), read read-only with
  **Pillow**, converted to grayscale, bounded-downscaled, and summarized into a few **bounded non-sensitive**
  features (size, aspect, near-white blank ratio, full horizontal/vertical rule counts, rough edge density).
  Tables = strong regular horizontal+vertical grid; diagrams = substantial non-grid graphic content;
  decorative = near-empty / extreme banner with low edges. **It never OCRs, calls a model/provider/network,
  base64/serializes/logs image bytes, records a path or source text, or adds an artifact.**
- **Degrade-never-fail / backward-compatible:** if Pillow is unavailable, the crop is unreadable/corrupt, or it
  is too small to analyze, the type is **`unknown`** — which makes the type priority uniform, so selection
  **falls back byte-for-byte** to the prior Slice 60/62 quality-only behavior. Default-off output stays
  byte-identical; the two-key gate is unchanged; **default cap remains exactly 1**; **hard cap remains 2**;
  `fitz_local`/`extracted_figure`-only and all unsafe-ref / Chandra / Mistral / `page_visual_signal` rejections
  are unchanged.
- **Ranking behavior (proven in tests):** diagram beats table at cap 1; two diagrams beat a table at cap 2; one
  diagram + one table at cap 2 selects **both with the diagram first**; only-tables still selects a table;
  pixel-decorative is **not** preferred just to avoid a table; a lone metadata-accepted candidate is still
  inserted (no over-rejection).
- **Tests:** new `test_scripts/test_visual_pilot_visual_type_ranking.py` (runtime-built tiny PNG fixtures in
  temp dirs — diagram/table/decorative drawn with Pillow, solid/corrupt via stdlib; pixel cases skip cleanly
  without Pillow). Host: ranking **64/0/0**; existing multifigure / quality_gate / e2e / insertion / render /
  export_asset / options / anki / operator `--self-test` / offline eval all green; `git diff --check` clean.
  **In-container (full deps):** ranking **64/0/0**, multifigure **78/0/0**, quality_gate **54/0/0**, operator
  `--self-test` PASS (Pillow 12.2.0 present). **Docker:** `docker compose build` + `up --force-recreate` ok,
  `/api/health` `{"ok":true}`, `smoke_release.py` **29/0/0**.
- **Optional real operator revalidation:** **not run** this slice (no non-private operator sample available in
  this environment). The desired-but-not-assumed outcome is `selected_visual_type: diagrams_or_figures_present`
  / `irreplaceable_visual_selected: true`; the actual result must be recorded only if/when the harness is rerun.
- **Out of scope (unchanged):** no frontend/UI, no UI count selector, no `/api/options` change, no cap change,
  no new API route, no extraction/OCR-routing/prompt/render/export behavior change, no Chandra/Mistral/Gemini/
  model/provider/cloud/`llama-server` call, no image generation. Chandra remains blocked by its own
  live-validation gate.
- **Safety / no-leak:** classifier returns only closed-vocab tokens + bounded numerics in internal info dicts;
  no real PDF path/filename, document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token,
  or model/mmproj/executable path in any doc/test/artifact/log. No committed binary/image/PDF/DOCX/ZIP/runtime
  fixture. **Slice 64 is COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).** The optional real operator
  revalidation that this entry left *not run* was subsequently performed and recorded in **Slice 65** above.

---

## Slice 63 — **Cap-2 real operator validation record**, on `slice63-visual-pilot-cap2-operator-validation`. **COMMITTED + MERGED to `chrome-renderer-v1`.**

- **Validation/docs slice.** Records a real, sanitized operator validation of the **Slice 62 cap-2 path**
  against the same already-supplied non-private operator sample. Slice 62 validated the capped multi-figure
  pilot **synthetically and in Docker** but did not run the optional **real** cap-2 revalidation; Slice 63
  closes that one gap. **No production pipeline/API/frontend code changed; no new visual behavior added.**
- **What was done:** rebuilt/used the Slice 62 container, ran the existing operator harness
  (`validate_visual_pilot_operator_sample.py`) with `GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1`,
  `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION=1`, `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`, copied the rendered
  PDF/HTML/DOCX to a host folder, and inspected the inserted figures by hand.
- **One tiny safe harness correction (the only code touched):** the harness export check previously hard-coded
  **exactly one** bundled PNG (`len(png_entries) == 1`), which falsely reported `export_png_included: false`
  when the cap-2 path legitimately bundled **two** referenced PNGs. It now requires the bundled-PNG count to
  equal the sanitized `inserted_visual_count` and stay within `1..2`, each still a safe relative
  `assets/<slug>.png` ref. No production code/schema/vocabulary changed; `--self-test` (default cap, one
  figure) stays green with `export_png_included: true`.
- **Recorded result (sanitized, closed vocab):** `cap2_operator_visual_quality_review: run` · `status: ok` ·
  `pilot_inserted: true` · **`inserted_visual_count: 2`** · **`selected_figures_quality:
  all_useful_or_acceptable`** · `pdf_render_ok: true` · `pdf_image_visible: true` · `docx_render_ok: true` ·
  `export_zip_ok: true` · `export_png_included: true` · `warnings: [multiple_figures_present_one_inserted]` ·
  `failure_category: none` · `no_leak_sweep: clean`. The two inserted figures were genuine content-bearing
  material from **distinct source pages**, not decorative chrome; both rendered visibly and rode along in the
  export bundle.
- **Operator-review nuance (sanitized, closed vocab):** `selected_visual_type: tables_only` ·
  `irreplaceable_visual_selected: false` · `decision_gate:
  cap2_plumbing_passed_but_visual_type_priority_incomplete` · `next_recommended_slice:
  prefer_diagrams_over_reconstructable_tables`. Both selected visuals were **important tables**, not
  diagrams/figures that are hard to reconstruct.
- **Interpretation / decision gate:** Slice 63 **proves the cap-2 pipeline works on a real, non-private sample**
  (selection → capped multi-insertion → render → export). Slice 62 made cap 2 *available*, default stays 1; this
  record confirms the cap-2 **real** output is useful (`all_useful_or_acceptable`). **But** both inserted visuals
  were useful/acceptable **tables**, and tables are often reconstructable from extracted text into clean
  generated tables — so the irreplaceable-visual goal is only partially met. The visual/OCR feature exists
  especially to preserve visuals an LLM **cannot** recreate from text (diagrams, flowcharts, screenshots,
  labeled figures, network maps). **Therefore the next visual slice should NOT be placement/UI polish yet;** it
  should **improve visual-type ranking** — prefer diagrams/figures over reconstructable tables when both are
  available, while still allowing tables when they are the best/only useful visual. **Do not expand beyond cap
  2; do not add Chandra/Mistral/Gemini/model/provider/cloud integration.** A `mixed_quality` verdict would have
  meant improve ranking/placement first; `decorative_or_bad_present`/`unclear` would have meant keep doing
  selection-quality work. Chandra remains blocked by its own live-validation gate.
- **Files:** `docs/VISUAL_PILOT_OPERATOR_VALIDATION.md` (cap-2 record + interpretation), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`; tiny correction in
  `test_scripts/validate_visual_pilot_operator_sample.py`. No frontend/UI, extraction/OCR-routing, prompt,
  render, export, or route change. No Chandra/model/provider/cloud call.
- **Safety / no-leak:** only sanitized closed-vocab fields + safe relative refs; no real PDF path/filename,
  document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable
  path, or raw exception in any doc/test/artifact/log. No committed binary/image/PDF/DOCX/ZIP/runtime output.
  **Slice 63 is NOT committed.**

---

## Slice 62 — **Capped multi-figure visual pilot**, on `slice62-visual-pilot-capped-multifigure`. **COMMITTED + MERGED to `chrome-renderer-v1`.**

- **Cautiously extends the off-by-default visual markdown image pilot from "at most one figure" to "up to a
  small server-configured cap" (hard upper bound `2`).** Default behavior is **unchanged: exactly one figure**.
  Slices 59/60/61 cleared the single-figure plumbing + Slice 60 quality gate on a real non-private sample;
  Slice 62 is the first step beyond one figure, and it stays small on purpose.
- **Why:** the Slice 61 post-fix operator verdict was `selected_figure_quality: useful_diagram_or_table` — in the
  `useful_diagram_or_table` / `acceptable_but_not_best` band, the decision gate for "cautious multi-figure may be
  considered next." This slice takes exactly that step: up to **2** figures, never more, never user-selectable N.
- **Gate (unchanged) + new cap:** the existing **two-key gate** (global master env `…ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT`
  AND per-job opt-in `visual_markdown_image_pilot`) is untouched. A new **server-side env integer**
  `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES` sets the cap: default `1`, min `1`, **hard max `2`**;
  absent/empty/non-integer/`0`/negative/`>2`/huge all **degrade to `1`** (never clamp upward). The cap matters
  only when both gates are on AND local figure extraction produced safe candidates.
- **Selection (reuses the Slice 60 quality gate):** candidates stay `fitz_local` + `extracted_figure` + safe
  `assets/<slug>.png` (file present inside the job dir, realpath-contained) only — never Chandra/Mistral/
  page-visual-signal/unsafe refs. The first/strongest pick is **byte-for-byte the existing single-best
  decision**. Additional figures (up to the cap) must each clear a **secondary quality floor** (`score ≥ 1.15`,
  i.e. genuinely content-bearing, not merely neutral/penalized), must not duplicate an already-selected
  `asset_id` or `asset_ref`, and **prefer a distinct source page** (same-page second figure only when no
  better alternative qualifies). Strongest stays first. Only-decorative ⇒ insert none with a closed reason; a
  low-quality second ⇒ insert one. The cap is never filled with junk.
- **Insertion:** with exactly one figure the output is **byte-identical** to the pre-Slice-62 pilot (singular
  `## Visual Reference` heading / same anchored placement). With more than one, each figure with a deterministic
  `<!-- visual-anchor: source_page_NNNN -->` marker is placed at its anchor; the rest are appended together
  under a single trailing **`## Visual References`** (plural) section. Captions stay generic page-only —
  `Extracted figure from source page N` — never source captions, OCR text, document text, or image content.
- **Export:** the bundle now rides along **all and only** the referenced pilot PNGs, **capped at 2**, each a
  safe job-local `assets/<slug>.png` resolved inside the job dir (realpath-contained, regular file). Never the
  whole `assets/` dir, never an unreferenced/cropped extra. PNG ride-alongs **still do not** count toward
  `files_included` / `total_included`, so a pilot-PNG-only job with no requested artifact **still 404s**. Bundle
  index keeps `visual_pilot_asset` (first ref or `null`, backward-compatible) and adds `visual_pilot_assets`
  (the capped safe list). No absolute paths or image bytes recorded.
- **Out of scope (unchanged):** no Chandra/Mistral/Gemini/model/provider/cloud call, no llama-server/image
  generation, no OCR-routing/extraction/prompt/renderer change, no new API route, no arbitrary N-figure support,
  no UI count selector. Chandra remains blocked by its own live-validation gate.
- **Frontend / `/api/options`:** **untouched** — no UI count selector; payload behavior unchanged
  (`enable_visual_references` still sent only when checked).
- **Files (code):** `pipeline/visual_markdown_insertion.py` (cap reader + capped multi-select helpers + multi
  insertion + plural export helper), `api/server.py` (export bundle rides all referenced PNGs up to cap; index
  keeps `visual_pilot_asset` + adds `visual_pilot_assets`). **Tests:** new
  `test_scripts/test_visual_pilot_multifigure.py` (env cap, selection, safety gates, insertion, no-mutation,
  render-skippable, export-skippable, no-leak sweep — **63 passed / 0 failed / 3 host-skipped**);
  `validate_visual_pilot_operator_sample.py` gained a safe `inserted_visual_count` integer field and now accepts
  1..2 safe refs (self-test green).
- **Validation (host):** `compileall` clean; `test_visual_pilot_multifigure` 63/0/3; `test_visual_pilot_quality_gate`
  50/0/1; `test_visual_markdown_insertion` 53/0; `test_visual_markdown_render` 6/0/1; `test_visual_pilot_export_asset`
  9/0; `test_visual_pilot_options` 16/0; `test_anki_export` 46/0; operator `--self-test` PASS; `e2e_validation`
  16/0/3; offline eval no regression (delta 0.0); `git diff --check` clean. Docker rebuild + `/api/health` +
  `smoke_release.py` + container-side multifigure/quality-gate/operator self-test run separately.
- **Safety / no-leak:** only sanitized closed-vocab fields and safe relative refs; no real PDF path/filename,
  document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable
  path, or raw exception in any doc/test/artifact/log. No committed binary/image/PDF/DOCX/ZIP/runtime fixture
  (test PNGs are tiny runtime-built byte literals under temp dirs).
- **Slice 62 is NOT committed.** Parked Slice 60 trace stash remains untouched.

---

## Slice 61 — **Post-fix visual-quality operator review record**, on `slice61-visual-pilot-postfix-quality-review`. **NOT COMMITTED.**

- **Docs / validation-record only.** No production code, frontend/UI, export, extraction/OCR-routing, prompt,
  render, or route change; no multi-figure, no Chandra/model/provider/cloud call; no committed binary/image/
  PDF/DOCX/ZIP/runtime output. Slice 60 is committed and merged to trunk (`chrome-renderer-v1`) ahead of this.
- **Why:** Slice 60 fixed the quality gate and the PDF image-visibility check, and reran the real, non-private
  operator validation with `status: ok` · `pilot_inserted: true` · `pdf_render_ok: true` · `pdf_image_visible:
  true` · `docx_render_ok: true` · `export_zip_ok: true` · `export_png_included: true` ·
  `warnings: [multiple_figures_present_one_inserted]` · `failure_category: none` · `no_leak_sweep: clean`. The
  one thing Slice 60 deliberately left open was the **human** quality classification of the now-selected figure.
  This slice records that post-fix verdict as the decision gate for the next visual step.
- **What was done:** reran the existing operator harness (`validate_visual_pilot_operator_sample.py`) inside the
  freshly rebuilt Slice 60 container against the already-supplied non-private sample, copied the rendered
  PDF/HTML/DOCX to a host output folder, and had the operator classify the selected figure using only the closed
  vocabulary `useful_diagram_or_table` · `acceptable_but_not_best` · `decorative_or_low_information` ·
  `wrong_or_bad_crop` · `unclear`.
- **Recorded post-fix review (sanitized, closed vocab):**
  `postfix_operator_visual_quality_review: run` · `status: ok` · `pilot_inserted: true` ·
  **`selected_figure_quality: useful_diagram_or_table`** · `pdf_render_ok: true` · `pdf_image_visible: true` ·
  `docx_render_ok: true` · `export_zip_ok: true` · `export_png_included: true` ·
  `warnings: [multiple_figures_present_one_inserted]` · `failure_category: none` · `no_leak_sweep: clean`.
  The **pre-fix** Slice 60 review (`selected_figure_quality: decorative_or_low_information` ·
  `extraction_candidate_quality: mostly_usable` · `crop_quality: mostly_good_some_label_loss` ·
  `pdf_image_visible: false` · `docx_image_visible: true` ·
  `failure_category: selection_quality_insufficient` · `no_leak_sweep: clean`) is preserved for comparison.
- **Decision-gate outcome:** `useful_diagram_or_table` falls in the
  `useful_diagram_or_table` / `acceptable_but_not_best` band → **cautious multi-figure or improved placement may
  be considered next**, as a separately-designed slice and still one figure at a time until that slice is
  scoped. Chandra remains blocked by its own live-validation gate.
- **Files:** `docs/VISUAL_PILOT_OPERATOR_VALIDATION.md` (new Slice 61 section), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md` — **docs only**.
- **Safety / no-leak:** only sanitized closed-vocabulary fields recorded; no real PDF path/filename, document
  text, OCR text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable path, or
  raw exception. Harness temp files were copied into the container `/tmp`, run, then removed; nothing committed.
- **Slice 61 is NOT committed.**

---

## Slice 60 — **Visual-pilot quality gate + PDF image-visibility validation**, on `slice60-visual-pilot-quality-gate`. **COMMITTED & merged to trunk.**

- **Why this replaced the earlier trace direction:** an earlier Slice 60 attempt added a *selection trace
  artifact*. Manual operator review showed that was the wrong fix — the real problems were **selection quality**
  and **PDF image visibility**, not missing trace metadata. The trace work was **parked (stashed, not committed)**
  and this quality-gate slice took its place.
- **What manual review found (sanitized):** the real, non-private sample produced **multiple** extracted
  figures and **most table/figure crops were usable** (some label loss). But the pilot selected a **low-value
  chapter-title / title-page crop**, and the PDF check was too weak — it reported `pdf_render_ok: true` while
  manual inspection showed a **broken/missing image marker** instead of a visible embedded image.
  - Recorded **pre-fix** human-review result (closed vocab):
    `operator_visual_quality_review: run` · `selected_figure_quality: decorative_or_low_information` ·
    `extraction_candidate_quality: mostly_usable` · `crop_quality: mostly_good_some_label_loss` ·
    `pdf_image_visible: false` · `docx_image_visible: true` ·
    `failure_category: selection_quality_insufficient` · `no_leak_sweep: clean`.
  - Recorded **post-fix** sanitized result (in-container `--self-test`, and the same code path a real run
    uses): `status: ok` · `pilot_inserted: true` · `pdf_render_ok: true` · **`pdf_image_visible: true`** ·
    `docx_render_ok: true` · `export_zip_ok: true` · `export_png_included: true` · `warnings: []` ·
    `failure_category: none` · `no_leak_sweep: clean`. The earlier `pdf_image_visible: false` was the harness
    layout artifact described below, now resolved; the quality gate independently fixes the decorative-selection
    half.
- **Quality gate (`pipeline/visual_markdown_insertion.py`):** the hard safety gates are **unchanged**
  (`fitz_local` only · `extracted_figure` only · safe `assets/<slug>.png` · real file inside the job dir · one
  figure maximum · degrade-never-fail · never Chandra/Mistral/`page_visual_signal`). On top of those, the safe
  candidates are now **ranked** by a conservative, deterministic gate using **only already-available manifest
  metadata** — `source_page`, `bbox`, and the `signals` page/crop dimensions. It **never** inspects private
  text, OCR text, captions, source contents, or image bytes, and **never** calls a model.
  - New helpers: `score_visual_markdown_candidate_for_pilot(asset)` →
    `{score, decorative, reasons}`; `rank_visual_markdown_candidates(assets)` → best index or `None`;
    `is_decorative_visual_candidate(asset)`. Closed-vocab quality reasons only (`quality_title_page`,
    `quality_full_page_crop`, `quality_content_sized`, `quality_small_area`, `quality_banner_shape`,
    `quality_narrow_shape`, `quality_header_region`, `quality_footer_region`, `quality_tiny_crop`,
    `quality_metadata_sparse`).
  - Behavior: prefer content-sized figures; **drop** confident decorative chrome (title-page full crop,
    header/footer banner strips, tiny logos/icons); penalize banner/narrow/small/full-page shapes for ranking;
    **preserve replacement-plan / manifest priority order on ties and near-ties** (a rival only displaces it
    when clearly better, by a margin). When all safe candidates are decorative → **omit** with new closed reason
    `visual_candidate_low_quality` (no insertion, byte-identical guide). When metadata is **sparse** it degrades
    to a neutral, non-decorative score so a good figure is **never over-rejected** (the synthetic-fixture shape).
    Still **one figure maximum**; default-off / opt-in gates unchanged; no frontend/UI/export/extraction/OCR/
    prompt change, no new route.
- **PDF image-visibility validation (harness `test_scripts/validate_visual_pilot_operator_sample.py`):** new
  summary field **`pdf_image_visible`** distinguishes “a PDF rendered” (`pdf_render_ok`) from “the inserted
  figure is actually an **embedded, figure-sized image object**” (`pdf_image_visible`). Implemented with PyMuPDF
  (`page.get_images(full=True)`); a broken/missing ref renders only a tiny **~14×16 broken-image placeholder
  icon**, so the check counts only images ≥ 32 px on both sides (the placeholder does not register). Skips
  calmly (`null` + closed warning `pdf_image_check_skipped_no_fitz`) when PyMuPDF is unavailable on host; Docker
  covers it with 0 skips. Summary is now **eleven** closed-vocab fields; still no path/filename/text/OCR/bytes/
  base64.
- **Root cause of the “broken PDF marker” — a harness layout artifact, NOT a production bug.** `render_pdf`
  writes its intermediate HTML next to the **output PDF** (`pdf.with_suffix(".html")`), and Chromium resolves
  the relative `assets/<slug>.png` ref against **that** directory. Production always renders to **`job.final_pdf`**
  — a sibling of `clean.md` and `assets/` — so the figure embeds correctly. The Slice 59 harness wrote
  `operator_final.pdf` to the temp **base** dir (outside the job dir), so `assets/` resolved to a non-existent
  path and Chromium embedded only the broken-image placeholder — which is what manual review saw. **Fix:** the
  harness now renders the PDF **inside the job dir** (sibling of `assets/`), mirroring production exactly. No
  renderer change was needed (the renderer was already correct for the production layout).
- **Tests:** new `test_scripts/test_visual_pilot_quality_gate.py` (50 host PASS / 1 skip — PDF-visibility skips
  w/o PyMuPDF+Chromium on host): content-beats-decorative for title/banner/tiny/header-footer; single
  content-sized inserts; only-junk omits safely; unsafe refs & Chandra/Mistral/`page_visual_signal` excluded;
  one-figure rule, default-off byte-identical, two-key gate truth-table; no-mutation; full no-leak sweep; PDF
  **embedding** (not just non-empty) positive **and** negative (missing ref → not visible). `e2e` test gained a
  fitz-guarded `render.pdf_image_visible` check; operator `--self-test` updated for the new field.
- **Results (host):** `compileall` clean; new gate test 50/0/1; `validate_*_operator_sample.py --self-test`
  PASS; `test_visual_pilot_e2e_validation.py` 16/0/3; `test_visual_markdown_insertion.py` 53/0 (flag-off) and
  77/0 (flag-on); `test_visual_markdown_render.py` 6/0/1; export-asset 9/0; options 16/0; anki 46/0; eval
  `--offline --all` no regression; `git diff --check` clean. Docker validation: see handoff.
- **Boundaries reaffirmed:** still **one figure maximum**; **no** Chandra/Mistral/Gemini/cloud/model/provider/
  llama-server call; **no** multi-figure support; Chandra remains blocked by its own live-validation gate. The
  real sample PDF path/filename and document contents are **not** recorded anywhere.

---

## Slice 59 — **Visual-pilot manual operator validation harness + runbook**, on `slice59-visual-pilot-operator-validation-harness`. **NOT COMMITTED.**

- **Purpose:** make it safe and repeatable for an operator to validate the **current single-figure visual
  pilot** against a real, **non-private** sample PDF when one is available. Slice 58 proved the stitched path
  with synthetic data; Slice 59 adds an opt-in manual harness that drives the **genuine** pipeline over a real
  PDF. **Validation/harness slice only — adds NO production code and changes NO behavior.**
- **New harness `test_scripts/validate_visual_pilot_operator_sample.py`** — a manual CLI, NOT part of normal
  smoke. Two modes:
  - `--pdf "<non-private-sample.pdf>" [--output-dir <dir>]` — real run. Drives `extract_local_figures`
    (`fitz_local` only) → `write_visual_assets_manifest` → `write_visual_asset_scoring_report` →
    `write_visual_replacement_plan_report` → `apply_visual_markdown_pilot` (both gates on, via `save_clean_md`)
    → HTML/PDF/DOCX render → `export_bundle`. **Refuses to run without `--pdf`** (unless `--self-test`).
  - `--self-test` — synthetic dry run (runtime stdlib PNG + synthetic manifest, no fitz/provider/model/cloud)
    that exercises the **same** insertion/render/export + summary code and asserts the summary schema,
    closed-vocab values, and no-leak behavior. Explicitly **does not** pretend to be real operator validation.
- **Safety/no-leak (both modes):** never prints the PDF path/basename/text, OCR text, image bytes, base64,
  data URIs, tokens, headers, model/mmproj/executable paths, raw argv, or full URLs. Emits only a fixed
  **closed-vocabulary** summary (`status`, `pilot_inserted`, `safe_asset_ref_present`, `html_render_ok`,
  `pdf_render_ok`, `docx_render_ok`, `export_zip_ok`, `export_png_included`, `warnings`, `failure_category`)
  plus closed-vocab step markers; exceptions are sanitized to closed `failure_category` tokens (only an
  exception *type name* is surfaced); a final sweep scans every pipeline-derived string. All working files
  live under a temp/output dir — nothing committed.
- **New `docs/VISUAL_PILOT_OPERATOR_VALIDATION.md`** — runbook: why it exists, opt-in/non-private policy, the
  safe placeholder command template, the closed-vocab field tables, and the recorded status — now
  `manual_operator_pdf_validation: run` / `status: ok` (see below).
- **Real operator validation — RUN, successful (sanitized):** the harness was run on **one real, non-private,
  operator-supplied PDF**. Recorded sanitized result: `status: ok`, `pilot_inserted: true`,
  `safe_asset_ref_present: true`, `html_render_ok: true`, `pdf_render_ok: true`, `docx_render_ok: true`,
  `export_zip_ok: true`, `export_png_included: true`, `warnings: [multiple_figures_present_one_inserted]`,
  `failure_category: none`, `no_leak_sweep: clean`. The `fitz_local` pilot found **one or more** candidates and
  inserted **exactly one**, preserving the one-figure rule; the warning is **expected** and confirms the design
  rule was obeyed. **This clears the current single-figure visual-pilot operator-validation gate.** It does
  **not** clear the Chandra live-validation gate and does **not** approve multi-figure insertion. Only the
  sanitized closed-vocab summary was recorded — no real path, filename, document/OCR text, image bytes, base64,
  data URI, full URL, raw argv, token, or raw exception.
- **Results:** host `--self-test` PASS (HTML/PDF render real; DOCX/export skip calmly w/o python-docx/FastAPI);
  **in container `--self-test` PASS** (all of pilot_inserted / safe_asset_ref / html / pdf / docx / export_zip /
  export_png `true`, 0 warnings, no leak). Real `--pdf` operator run recorded successful (sanitized fields
  above). Refusal + sanitized missing-file paths verified (no path echoed).
  `compileall api pipeline test_scripts` + `git diff --check` clean; `/api/health` ok.
- **Scope / hard boundaries:** **no** production-code change, **no** frontend/UI change, **no** renderer /
  export / extraction / OCR-routing / prompt change, **no** new API route, **no** advisory schema change,
  **no** generic artifact-list change, **no** multi-figure / Chandra / Mistral / Gemini / cloud, **no**
  model/provider/llama-server/network call, **no** new image pipeline, **no** committed PDF/image/DOCX/ZIP
  fixture. **≤1 figure; `fitz_local` only; safe `assets/<slug>.png` only — unchanged.** The real operator
  validation pass is now **recorded**, clearing the single-figure operator gate; **Chandra extraction
  integration remains blocked by Slice 45 `status:not_run`; multi-figure stays deferred** (out of scope until
  separately designed).

---

## Slice 58 — **Visual-pilot stitched E2E validation harness + record**, on `slice58-visual-pilot-e2e-validation`. **COMMITTED `39dc162`, merged to trunk.**

- **Purpose:** prove the already-shipped **single-figure** visual pilot (Slices 52–57) works as **one connected
  chain** before any visual expansion. This is a **validation/harness slice only** — it adds **no** production
  code and changes **no** behavior.
- **Chain stitched (output of each stage feeds the next):** safe job-local `assets/<slug>.png` → existing
  visual manifest / replacement-plan shape → global pilot master flag ON → per-job opt-in ON → standard
  markdown image insertion (**exactly one** figure) → HTML/PDF/DOCX render compatibility → export ZIP
  portability including the single referenced PNG.
- **New harness `test_scripts/test_visual_pilot_e2e_validation.py`** — reuses the existing helpers/patterns
  from `test_visual_markdown_insertion.py`, `test_visual_markdown_render.py`, `test_visual_pilot_export_asset.py`,
  and `test_visual_pilot_options.py`. It builds a real `JobManager.Job`, regenerates `clean.md` via the real
  `apply_visual_markdown_pilot` (opted in through the persisted manifest) and `save_clean_md`, then renders +
  exports it. Verifies all 13 points: one image; safe `assets/<slug>.png` ref; generic page caption (real
  `None`-caption path, not raw OCR); unsafe refs rejected; manifest/plan/source-PNG unmutated; HTML safe
  relative `<img>` + no absolute path; non-empty PDF (SKIP w/o Chromium); non-empty DOCX (SKIP w/o
  python-docx); export carries exactly the one referenced PNG under `assets/`; extra crop / blanket assets dir
  excluded; `files_included` counts requested artifacts only and the PNG alone still `404`s the gate; bundle
  index records only the safe relative `visual_pilot_asset`; and a final no-leak sweep over every serialized
  output.
- **Synthetic data only:** the test PNG is generated at runtime by a tiny stdlib builder (`zlib` + `struct`);
  every PNG/PDF/DOCX/HTML/ZIP is written under a temp dir and removed. **No committed binary/image/PDF/DOCX/ZIP
  fixture, no base64, no data URI.**
- **New `docs/VISUAL_PILOT_E2E_VALIDATION.md`** — records what the harness proves, what it does **not** prove,
  the synthetic-data discipline, and the manual-review status: `manual_operator_pdf_validation: not_run`
  (reason `non_private_operator_sample_not_supplied`).
- **Results:** host `16 passed / 0 failed / 2 skipped` (DOCX + export skip w/o python-docx/FastAPI); **in
  container `29 passed / 0 failed / 0 skipped`** (full chain). Existing `test_visual_markdown_insertion`
  (53/0), `test_visual_markdown_render` (6/0/1), `test_visual_pilot_export_asset` (9/0),
  `test_visual_pilot_options` (16/0), `test_anki_export` (46/0), and offline eval all green;
  `compileall api pipeline test_scripts` + `git diff --check` clean; `/api/health` ok.
- **Scope / hard boundaries:** **no** production-code change, **no** frontend/UI change, **no** renderer /
  export / extraction / OCR-routing / prompt change, **no** new API route, **no** advisory schema change,
  **no** generic artifact-list change, **no** multi-figure / Chandra / Mistral / Gemini / cloud, **no**
  model/provider/llama-server/network call, **no** new image pipeline, **no** committed image fixture. **≤1
  figure; `fitz_local` only; safe `assets/<slug>.png` only — unchanged.** **Chandra extraction integration
  remains blocked by Slice 45 `status:not_run`.**

---

## Slice 57 — **Visual-pilot readiness capability + Builder guard**, on `slice57-visual-pilot-readiness-guard`. **COMMITTED `9c4ccc0`, merged to trunk.**

- **Purpose:** make the Builder's per-job visual opt-in **accurately reflect whether the pilot can realistically
  work for a new job**. The toggle stays **default-off**, but it is now **enabled only when the backend reports
  readiness** — i.e. both server-side switches are on. This is a **readiness/UX guard only**; it does **not**
  enable visual insertion, change the backend dual gate, or auto-enable extraction.
- **Why readiness needs two switches:** insertion needs (1) the global pilot master flag
  `GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT` AND (2) local figure extraction
  `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION` (which is what produces the `fitz_local` `extracted_figure` the pilot
  inserts for **new** jobs). With master on but extraction off, a fresh job has nothing to insert — so the
  opt-in would be a dead control. Readiness = master **AND** extraction.
- **Backend (`/api/options.capabilities`):** now reports three **non-secret booleans** (no env names, paths,
  tokens, or raw config):
  - `visual_markdown_image_pilot` — global pilot master flag (**preserved**; same meaning as Slice 54/55 —
    backward-compatible).
  - `local_figure_extraction` — local figure-extraction flag.
  - `visual_references_ready` — `true` **only when both** of the above are `true`.
- **Frontend (`visualPilotOptIn.js` + Builder):** two new pure helpers
  `isVisualReferencesReady(capabilities)` (trusts the backend's derived flag, falls back to AND-ing the two
  components for older/partial payloads) and `visualPilotReadinessNote(capabilities)` (fixed safe copy). The
  Builder mirrors readiness into the toggle's enabled/checked state and shows a **calm** note when not ready:
  - master flag off ⇒ *"Visual references are not enabled on this server."*
  - master on but extraction off ⇒ *"Visual references need local figure extraction to be enabled on this server."*
  - both on ⇒ toggle enabled, no note.
- **Request payload unchanged from Slice 55:** `enable_visual_references` is added **only** when the user opts
  in; a default / opted-out / not-ready request stays byte-identical.
- **Scope:** small `/api/options` capability refinement + small Builder guard + focused tests/docs. **No** new
  page, broad visual settings, export-bundle change, generic artifact-row change, advisory schema change,
  renderer/prompt/extraction/OCR-routing change, Chandra/Mistral/Gemini/cloud, model/llama-server/network
  call, image processing, image fixtures, or `clean.md` write. **No more than one figure; `fitz_local` only;
  safe `assets/<slug>.png` only — all unchanged.**
- **Backend gates unchanged (defence-in-depth):** the global master flag **cannot be bypassed**; the per-job
  opt-in still defaults false; readiness in `/api/options` is a **UI affordance only** and is **not** a new
  insertion gate — `apply_visual_markdown_pilot` still independently re-checks both switches and remains
  degrade-never-fail even if capabilities are stale/absent. Local figure extraction is **never** auto-enabled
  by the toggle and extraction is **never** run because of it.
- **Safety/no-leak:** capabilities expose only safe booleans; the readiness notes are fixed copy. No env
  names, paths, tokens, headers, socket/model/mmproj/executable paths, raw argv, image bytes, data URIs,
  base64, OCR text, or provider payloads in the API response, the UI, logs, docs, or tests.
- **Unchanged:** guide output; prompts; PDF/HTML/DOCX rendering; extraction/OCR routing; visual advisory JSON
  ride-alongs (Slice 51); the Slice 56 PNG export ride-along; Anki `.apkg` (Slice 53); CSV/TSV quiz exports;
  the default-off Slice 54/55 pilot gate. **Chandra extraction integration remains blocked by Slice 45
  `status:not_run`.**
- **Tests:**
  - New `test_scripts/test_visual_pilot_options.py` — Part A (pure, host): readiness truth table over all four
    env combinations (master off+figure off / on+off / off+on / on+on ⇒ ready only when both on), all plain
    booleans. Part B (FastAPI/Docker): `server.options()` capability subtree has the three keys with correct
    booleans, backward-compatible `visual_markdown_image_pilot`, a fixed safe key set, and no
    secret/path/env-name/url in the payload; default env ⇒ not ready. **16/0 on host** (Part B auto-skips).
  - Updated `frontend/scripts/verify-visual-pilot-opt-in.mjs` — readiness truth table, calm master-off and
    extraction-off messages, ready⇒enabled, payload field only when checked, and no path/token/env-name/
    url/data-uri leak in the notes.
  - Existing batteries still green: `test_visual_markdown_insertion`, `test_visual_markdown_render`,
    `test_visual_pilot_export_asset`, `test_anki_export`, visual planner/scoring/artifact/manifest/advisory,
    `test_local_figure_extraction`, OCR/Chandra suites, eval, frontend build + all verifies.
- **Status:** **NOT committed** (per instruction). Host validation green; Docker rebuild/recreate +
  `/api/health` + `smoke_release.py` + `/api/options` readiness spot-check run before any commit.

---

## Slice 56 — **Export the referenced visual-pilot PNG** with bundles, on `slice56-visual-pilot-export-asset`.

- **Purpose:** make exported Markdown/HTML **portable**. When a guide's `clean.md` contains the Slice 54
  pilot's safe image reference `![caption](assets/<slug>.png)`, the export bundle now includes **that single
  referenced job-local PNG** so the markdown image resolves outside the app too. Nothing else about export
  changes.
- **Scope:** **backend export-bundle logic only** (`api/server.py` `export_bundle`) plus two small read-only
  detection helpers in `pipeline/visual_markdown_insertion.py` and a focused test. **No frontend/UI, no new
  API route, no new generic artifact row, no schema change, no renderer/prompt/extraction/OCR-routing
  change, no Chandra, no model/llama-server/network call, no image processing, no `clean.md` write.**
- **Detection (read-only):**
  - `extract_visual_pilot_asset_refs(markdown_text)` — pure/string-only. Scans for `![...](assets/<slug>.png)`
    and keeps only refs that pass the existing Slice 54 `validate_visual_asset_ref` (fixed
    `assets/<slug>.png` shape; rejects absolute, `..`, backslash, URL, `data:`/base64, non-PNG, nested
    subdir, `-`/non-`[A-Za-z0-9_]` slugs). Order-preserving + de-duped; never raises.
  - `find_exportable_visual_pilot_asset(job)` — reads the job's `clean.md` read-only (new `_read_text`
    helper; never opens image bytes), returns the **first** referenced ref **only if** the file really
    exists **inside** the job dir (existing `_asset_file_ok` realpath containment ⇒ symlink escapes
    rejected). Returns **at most one** ref (pilot's one-figure rule); `None` on no clean.md / no safe ref /
    missing / unsafe file. Never raises.
- **Bundle wiring:** in `export_bundle`, after the Slice 51 advisory ride-alongs, the detected PNG is added
  as ZIP entry `<base_dir>/assets/<slug>.png` (preserves the existing per-job relative layout, so the
  bundled `clean.md`/`final.html` resolve it). Defence-in-depth re-check (`is_relative_to` + `is_file`)
  before writing. Any problem is caught and **skipped calmly** — export still succeeds.
- **Boundary decisions:**
  - **Not** counted toward `files_included` / `total_included` — like the advisory ride-alongs it can
    **never by itself** satisfy the "at least one requested artifact" gate (a pilot-PNG-only job with no
    requested artifact still 404s).
  - Includes **only** the one *referenced* PNG — **never** the whole `assets/` dir, **never** unreferenced
    or extra cropped images.
  - The bundle index records only the **safe relative ref** (`visual_pilot_asset: "assets/<slug>.png"` or
    `null`) — no absolute/local filesystem path, no image bytes.
- **Safety/no-leak:** no image bytes, absolute paths, `..`, backslashes, URLs, data URIs, base64, tokens,
  headers, socket/executable/model/mmproj paths, raw argv, OCR text, or provider payloads in logs, the ZIP
  metadata, the manifest, docs, or tests. Source PNG and `clean.md` are left **byte-identical** (no mutation).
- **Unchanged:** guide output; prompts; PDF/HTML/DOCX rendering; extraction/OCR routing; visual advisory
  JSON ride-alongs (Slice 51); Anki `.apkg` export (Slice 53); CSV/TSV quiz exports; the default-off visual
  pilot gate (Slices 54/55). **Chandra extraction integration remains blocked by Slice 45 `status:not_run`.**
- **Tests:** `test_scripts/test_visual_pilot_export_asset.py`.
  - **Part A (pure, host-runnable):** ref extraction order/de-dup; rejects every unsafe/non-pilot ref;
    `find_…` returns the first referenced+present ref, and `None` for missing-file / no-clean.md /
    unreferenced / **symlink-escape**. **9/0** on host.
  - **Part B (bundle, runs in Docker / when FastAPI importable):** referenced PNG rides along exactly once
    under `<base_dir>/assets/`; unreferenced extra PNG **not** bundled; entry is relative+safe; carries real
    bytes but the manifest does **not** echo image bytes/paths; records safe relative ref; `files_included`
    counts requested artifacts only; missing referenced file skipped calmly (export still succeeds, ref
    `null`); no-safe-ref job bundles no PNG; unsafe refs all rejected; pilot-PNG-only job still 404s; source
    PNG + `clean.md` byte-identical after export.
- **Status:** **NOT committed** (per instruction). Host validation green (Part A + full backend battery +
  eval + frontend build/test/verify); Docker rebuild + `/api/health` + `smoke_release.py` + Part B bundle
  section run before any commit.

---

## Slice 55 — **Per-job opt-in** for the visual markdown image pilot, on `slice55-visual-pilot-job-opt-in`.

- **Purpose:** make the proven Slice 54 pilot **user-controllable per job** while keeping it **default-off
  and safe**. The pilot now requires **two gates AND-ed together**: the global env master switch **and** an
  explicit per-job opt-in. A job opt-in can **never** bypass the master switch.
- **Gating truth table** (both required; only the last row may insert — still subject to all Slice 54
  candidate/path safety gates):
  - global **false** + job **false** ⇒ no insertion (`visual_pilot_disabled`)
  - global **false** + job **true**  ⇒ no insertion (`visual_pilot_disabled`) — opt-in cannot bypass env
  - global **true**  + job **false** ⇒ no insertion (`visual_pilot_job_opt_out`)
  - global **true**  + job **true**  ⇒ insertion *may* run (≤1 `fitz_local` `extracted_figure`, safe path)
- **Global master flag:** `GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT` (env; truthy ∈ {1,true,yes,on}),
  **still required, default false**. Unchanged from Slice 54.
- **Per-job option:** persisted job manifest key **`visual_markdown_image_pilot`** (bool, **default false**).
  An old job created before this option ⇒ key absent ⇒ treated as **false**. Coerced to a strict bool;
  any non-bool/malformed value ⇒ **false** (never accidentally on).
- **Request field:** **`enable_visual_references`** (bool, default false) on `LLMJobRequest`, wired into
  **both** the JSON and the multipart `_parse_llm_request` branches (multipart via `_form_bool(...,False)`).
  `create_llm_job` passes it to `run_llm_job(enable_visual_references=…)`, which stores it as the
  `visual_markdown_image_pilot` manifest option. **Only the LLM path** carries this (only LLM+PDF jobs ever
  produce a `fitz_local` `extracted_figure`); paste/upload paths are untouched (no dead toggle).
- **Pilot integration point:** `pipeline/visual_markdown_insertion.py` gained
  `is_job_visual_pilot_opt_in(job)` (reads the manifest key, total/never-raises) and
  `apply_visual_markdown_pilot` now checks the env switch **first**, then the per-job opt-in, before any
  candidate read. Env-off short-circuits without ever reading the job option. New closed-vocab reason
  `visual_pilot_job_opt_out`. **No change to the single `save_clean_md` chokepoint**; the helper is still
  wired at the same spot in `run_raw_markdown_pipeline`.
- **Capability flag (non-secret):** `/api/options` now returns
  `capabilities.visual_markdown_image_pilot` = the global master-switch state, so the Builder can render
  its opt-in **enabled** (master on) vs **disabled-with-note** (master off). Exposes only the experimental
  on/off bit — never a key/token/path/URL.
- **Frontend (Builder only, no redesign):** a single experimental toggle **"Add one visual reference
  (experimental)"** in the LLM settings block, **default unchecked**, **disabled with a short note when the
  server capability is off**. It adds the single `enable_visual_references: true` to the request **only when
  on** (default/opted-out request stays byte-equivalent). New pure helper `frontend/src/visualPilotOptIn.js`
  (`visualPilotPayloadFields`, `isVisualPilotEffectivelyOn`, `isVisualPilotToggleEnabled`) keeps the
  payload/toggle logic React-free + node-testable. **No new page, no broad visual settings, no export/
  artifact rows, no Job Details panel change.**
- **Slice 54 visual behaviour is unchanged:** ≤1 `fitz_local` `extracted_figure`; safe `assets/<slug>.png`
  only; existing markdown/render path; no renderer rewrite; no Chandra/Mistral/Gemini/cloud; degrade-never-
  fail. The opt-in only adds a *second* gate in front of the same Slice 54 path.
- **Tests:**
  - `test_scripts/test_visual_markdown_insertion.py` — added a **flag-independent truth-table** (sets/clears
    the env var itself) covering all four (global, job) combos incl. **(off,on) proving opt-in can't bypass
    env**, plus opt-in coercion unit checks (missing/None/false/`"banana"`/int ⇒ false; `true`/`"true"`/
    manifest-read ⇒ true; broken `read_manifest` degrades to false). **flag-off 53/0, flag-on 77/0.**
  - `test_scripts/test_visual_markdown_render.py` — added a **negative-gate** case (master switch on + job
    opted out ⇒ original markdown, renders with **no `<img>`**). **6/0, 1 skip** (docx host dep) both modes.
  - `frontend/scripts/verify-visual-pilot-opt-in.mjs` (added to `npm test`) — payload field present **only**
    when opted in; never serialises `false`; toggle forced off+disabled when capability off; exact safe
    field name `enable_visual_references` + label; full no-leak scan.
- **Scope guards:** default still **off**; master env flag still required (not optional); ≤1 figure; no
  Chandra/Mistral/Gemini/cloud images; no image generation; no broad visual settings; no export-bundle/
  artifact-list/advisory-schema change; no prompt/OCR-routing/extraction/broad-render rewrite; no model/
  llama-server/network call; no `clean.md` write outside `save_clean_md`.
  **Chandra extraction integration remains blocked by Slice 45 `status:not_run`.**
- **Status:** **NOT committed** (per instruction). Host validation green (backend battery + eval + frontend
  build/test/verify); Docker rebuild + `/api/health` + `smoke_release.py` + flag-on focused validation run
  before any commit.

---

## Slice 54 — Minimal **V4/V5 visual markdown image pilot**, off by default, on `slice54-visual-markdown-image-pilot`.

- **Purpose:** finally prove the *smallest possible* end-to-end visual path. When an explicit,
  off-by-default flag is set, insert **at most one** existing `fitz_local` `extracted_figure` (already
  cropped to the job's `assets/<slug>.png` by Slice 40) into the generated guide as a **standard
  Markdown image** — `![safe caption](assets/<slug>.png)` — flowing through the **existing**
  `JobManager.save_clean_md` chokepoint and the **existing** PDF/HTML/DOCX renderers. **No renderer was
  rewritten. No Chandra. No new image generation. No new artifact. No frontend toggle.**
- **Key finding (the thing this pilot set out to prove):** the existing render path *already* resolves a
  job-local relative `assets/<slug>.png` reference. PDF/HTML render from a `file://` URI rooted at the
  job dir (`final.html` sits beside `assets/`), so a relative `<img src="assets/…">` resolves locally;
  the DOCX renderer's `_resolve_image_path` already resolves relative refs against the job dir and
  degrades to an `[image missing: …]` marker rather than failing. **So no renderer change was needed.**
- **Feature flag:** `GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT` (env; truthy ∈ {1,true,yes,on}),
  **default false** — mirrors the existing `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION` pattern. With the flag
  unset the pilot is a **no-op**: it returns the sanitized clean Markdown **unchanged (byte-identical)**
  without reading any artifact, so default guide output is exactly as before this slice.
- **New module:** `pipeline/visual_markdown_insertion.py` (stdlib-only: `json`, `os`, `re`, `sys`,
  `typing`; imports nothing from `fitz`/Tesseract/llama.cpp/Chandra/Mistral/Gemini/LMM/renderers/server;
  reads only the job's already-persisted, already-sanitized `visual_assets_manifest.json` /
  `visual_replacement_plan.json` and the on-disk `assets/` PNG). Public API:
  - `is_visual_markdown_pilot_enabled() -> bool`
  - `apply_visual_markdown_pilot(job, clean_md) -> (str, info)` — the degrade-never-fail entry point.
  - `select_visual_markdown_candidate(job, *, manifest=None, replacement_plan=None) -> dict | None`
  - `validate_visual_asset_ref(asset_ref) -> str | None`
  - `build_visual_markdown_image(candidate) -> str`
  - `insert_visual_markdown_reference(clean_md, candidate) -> (str, info)`
- **Integration point (single, surgical):** `pipeline/run_markdown_job.py::run_raw_markdown_pipeline`,
  immediately **before** the existing `job.save_clean_md(...)` call — `clean = sanitize(raw)` →
  `clean, _ = apply_visual_markdown_pilot(job, clean)` → `save_clean_md(clean, "generated")`. **No new
  clean.md writer; the single chokepoint is preserved** (the figure is snapshotted into version history
  like any other clean.md write).
- **Candidate rules (narrow on purpose):** `fitz_local` only; `extracted_figure` only; **one maximum**.
  Preferred = a `visual_replacement_plan.json` item with `candidate_action:"candidate_include_as_figure"`
  whose `asset_id` resolves to a safe `extracted_figure` in `visual_assets_manifest.json`. Fallback
  (flag-on, all safety gates still applied) = the first safe `fitz_local` `extracted_figure` in the
  manifest. **Never** Chandra (`chandra_local` / a `chandra_blocked` marker), **never** `mistral_ocr`,
  **never** `page_visual_signal`. If no safe candidate exists, the figure is omitted and the job
  continues normally.
- **Safe asset-path gate:** the ref must be exactly `^assets/[A-Za-z0-9_]+\.png$` **and** the file must
  really exist *inside* the job directory (realpath-containment check rejects symlink escapes). Rejected:
  absolute paths, `..`, backslashes, URL-like refs, `data:`/base64, subdirs, non-PNG. The rendered
  Markdown never contains a host path; the renderer never receives an arbitrary host path from model
  output.
- **Caption:** a generic, plain-text, length-limited (≤80), safe-charset, Markdown-escaped string
  derived from the **source page only** (`Extracted figure from source page N`). Manifest captions are
  `None` in practice, so the generic path is always used. **No** raw caption / OCR text / provider
  payload / path / URL / token / image byte / data URI is ever emitted.
- **Placement (dumb v1):** if the guide carries a deterministic `<!-- visual-anchor: source_page_NNNN -->`
  marker for the figure's page, the image is placed at that anchor; otherwise a single trailing
  `## Visual Reference` section is appended. Never mid-prose, never semantic, never derived from raw
  source text.
- **Degrade-never-fail:** any failure (no candidate / unsafe ref / missing file / malformed artifact /
  insertion error) yields the **original** Markdown and a **closed-vocab** reason (`visual_pilot_disabled`,
  `visual_candidate_unavailable`, `visual_candidate_unsafe`, `visual_asset_missing`,
  `visual_asset_path_invalid`, `visual_markdown_insert_failed`, `visual_format_unsupported`,
  `visual_render_degraded`). The job never fails because of the pilot; reasons are stderr-only (no
  job.json field, no artifact-list change). Raw paths / exceptions are never logged.
- **PDF/HTML/DOCX validated separately:** PDF + HTML use the existing Markdown→render path (relative
  `assets/…` resolves from the job `file://` root); DOCX embeds the relative image via the existing
  `_resolve_image_path` or degrades to its existing `[image missing: …]` marker — never fails the export.
  No DOCX/Chromium rewrite.
- **New tests:** `test_scripts/test_visual_markdown_insertion.py` (**flag-off 26/0**, **flag-on 50/0**:
  flag-off byte-identical even with artifacts present; one-image-max; ref shape; reject absolute/`..`/
  backslash/url/data-uri/non-png/subdir; reject Chandra / chandra_blocked / page_visual_signal; missing
  file degrades; plan→manifest fallback; caption sanitization + length limit; anchor vs Visual-Reference
  placement; no mutation of manifest/plan on disk or in-memory; full no-leak scan) and
  `test_scripts/test_visual_markdown_render.py` (HTML `<img src="assets/…">` with **no host path**; PDF
  renders non-empty via Chromium; DOCX embeds/degrades without raising — each SKIPs cleanly when its host
  dep is absent). All existing visual/anki/ocr/eval/export tests still pass; frontend build/test/verify
  unchanged (no frontend change this slice).
- **Scope guards:** flag **off by default**; ≤1 figure; no Chandra/Mistral/Gemini/cloud images; no
  frontend toggle; no export-bundle change; no generic artifact-list change; no prompt change; no OCR
  routing change; no extraction behavior change (only reads already-produced advisory artifacts when the
  flag is on); no model/llama-server/network call; no `clean.md` write outside `save_clean_md`.
  **Chandra extraction integration remains blocked by Slice 45 `status:not_run`.**
- **Status:** **committed `cdebbaa` and fast-forward merged to `chrome-renderer-v1` (pushed).** Slice 55
  builds on it.

---

## Slice 53 — True Anki **`.apkg`** export (backend core + export route + tiny UI button) on `slice53-anki-apkg-export`.

- **Purpose:** add a **real, importable Anki `.apkg` package** export for the *already generated*
  quiz / flashcard items in `jobs/<id>/quizzes/<n>.json`, so the operator can study generated material
  in Anki. This is **direct user-visible study value**. It deliberately does **not** touch the visual
  advisory pipeline, visual rendering, Chandra, OCR routing, extraction, or guide-generation prompts.
- **New module:** `pipeline/anki_export.py` — **stdlib-only** (`sqlite3`, `zipfile`, `json`, `hashlib`,
  `html`, `io`, `os`, `re`, `tempfile`). An `.apkg` is a ZIP holding a SQLite `collection.anki2`
  (Anki **schema 11** — the long-stable, universally importable format) plus an empty `media` map.
  **No `genanki`/third-party dependency was added** (requirements.txt unchanged); no network, no
  model/provider call, no image/media, no LaTeX. Public API:
  - `build_apkg(items, *, job_id, quiz_n, title=None) -> bytes`
  - `normalize_cards(items) -> (list[(front_html, back_html)], skipped_counts)`
  - `deck_id_for(job_id, quiz_n) -> int`, `deck_name_for(title) -> str`,
    `apkg_filename(job_id, quiz_n) -> str`
- **Card model:** single shared **"GuideForge Basic"** 2-field model (`Front` / `Back`). Question →
  Front (MCQ also lists its options so the card is self-testable); answer → Back (MCQ resolves the
  answer letter to its full option text — mirrors the existing `_render_quiz_export` front/back rules).
  All field text is **HTML-escaped** (newlines → `<br>`) so user study text can't be mis-parsed as markup.
- **Deterministic deck/model IDs (no churn, no leaks):** model id is a **fixed app-level constant**
  (`MODEL_ID = 1010101010`) reused across every export; deck id is a stable SHA-256 of
  `"deck"+job_id+quiz_n` folded into a safe Anki id range (per-job deck under the `GuideForge::<title>`
  subdeck). Note **GUIDs are index-based** (derived from internal ids, **never** card text), so
  re-exporting the same quiz **updates** rather than duplicates on re-import. Creation/mod timestamps
  are **fixed constants** (never wall-clock) → re-export is byte-stable. The required Anki `csum` is the
  format's internal one-way duplicate checksum of the first field (not an externally meaningful id).
- **Route:** **no new route** — extended the existing `GET /api/jobs/{job_id}/quizzes/{quiz_n}/export`
  by adding `apkg` to `VALID_EXPORT_FORMATS` (now `{csv, anki_tsv, quizlet, apkg}`). For `apkg` the
  route returns `application/octet-stream`, `Content-Disposition: attachment; filename="quiz-<job>-<n>.apkg"`
  (existing naming convention; filename is path-sanitized). **CSV / anki_tsv / quizlet exports are
  unchanged.**
- **Degrade-safe input:** malformed / empty cards are skipped (closed-vocab counts:
  `skipped_empty`, `skipped_malformed`); **zero surviving cards → a valid empty-deck `.apkg`** (no
  exception), matching the existing route's "empty export, not an error" behaviour.
- **No-leak:** the package embeds only the user's own Front/Back study text + a sanitized deck name.
  It never embeds provider keys, headers, tokens, socket paths, local/host paths, executable paths,
  model/`mmproj` paths, raw argv, raw OCR dumps, raw provider/model payloads, image bytes, data URIs,
  base64, artifact URLs, or internal job-directory metadata. `job_id` only seeds derived numeric
  ids/guids/filename — it is never written into the package.
- **Frontend:** one-line addition to the existing quiz export-button row in `RecentJobsPanel.jsx`
  (`{ format: "apkg", label: "Anki .apkg" }`) using the existing `quizExportUrl(...)` helper. No new
  page, no redesign, no visual-advisory UI touched.
- **New test:** `test_scripts/test_anki_export.py` (**46/0** on host; route section runs in Docker) —
  valid non-empty ZIP w/ `collection.anki2`+`media`, schema-11 tables, correct note/card counts,
  field-separator + MCQ option/answer content, **byte-identical re-export**, stable GUIDs, per-job
  distinct decks, malformed/empty skip counts, empty-deck package, full no-leak scan (keys/paths/urls/
  data-uris/sockets/job-id), stdlib-only import assertion, and route-level checks (apkg status/
  content-type/disposition + **CSV/anki_tsv still work** + bad-format 400).
- **Scope guards (unchanged by this slice):** no FSRS / in-app spaced repetition; no images/audio/media
  in decks; no guide-generation prompt changes; no PDF/HTML/DOCX render changes; no visual insertion
  wired into guides; no OCR routing changes; **Chandra extraction integration remains blocked by
  Slice 45 `status:not_run`**; visual render insertion remains a separate decision.
- **Status:** **NOT committed** (per instruction). Validation pending Docker rebuild + `/api/health` +
  `smoke_release.py`.

---

## Slice 52 — Visual **insertion planner core** (pure, unwired; roadmap V3+) on `slice52-visual-insertion-planner-core`.

- **Purpose:** add a pure, deterministic **insertion planner core** — the next V3+ step after the
  replacement planner (`docs/VISION_ROADMAP.md` §8). It consumes an already-sanitized
  `visual_replacement_plan.json`-shaped replacement plan (and, optionally, a **safe-only** source-page
  anchor inventory) and returns a **separate advisory insertion-position plan** — a per-asset
  `insertion_mode` / `placement` / `anchor_status` with closed-vocab `reasons`. It does **not** mutate
  the replacement plan or anchors, persist an artifact, embed visuals, change extraction/guides/
  rendering, or wire into production. **Not** a Chandra integration slice, **not** a visual-embedding
  slice.
- **New module:** `pipeline/visual_insertion_planner.py` (stdlib-only: `re`, `typing`; imports nothing
  from `fitz`/Tesseract/llama.cpp/Chandra/Mistral/Gemini/LMM/renderers/server/job-manager/extraction/
  run-job/`visual_*` cores; no `json`/`os`/`pathlib`/`socket`/`subprocess`). Public API (small, pure,
  total):
  - `plan_visual_insertion_item(item, *, anchors_by_page=None) -> dict`
  - `plan_visual_insertions(items, *, anchors_by_page=None) -> list[dict]`
  - `build_visual_insertion_plan(replacement_plan, *, source_page_anchors=None) -> dict`
- **Insertion plan report shape:** `{version:1, kind:"visual_insertion_plan", status:"completed",
  source:"visual_replacement_plan.json", insertions:[…], summary:{insertion_count,
  figure_reference_count, table_reference_count, text_summary_reference_count, review_only_count,
  unknown_count, anchor_matched_count, anchor_missing_count}, warnings:[…]}`. Each insertion:
  `{asset_id, source_page, source_provider, asset_type, candidate_action, insertion_mode, placement,
  anchor_id, anchor_status, reasons:[…], warnings:[…]}`.
- **Closed vocab only:** `insertion_mode` ∈ {figure_reference, table_reference, text_summary_reference,
  review_only, unknown}; `placement` ∈ {source_page_reference, review_appendix, unknown};
  `anchor_status` ∈ {matched, missing, not_required, unknown}; `candidate_action` ∈
  {candidate_include_as_figure, candidate_convert_to_table, candidate_summarize_as_text, review_only,
  unknown}; `source_provider` ∈ {fitz_local, chandra_local, mistral_ocr, unknown}; `asset_type` ∈
  {page_visual_signal, extracted_figure, table, table_region, equation_block, diagram, figure,
  image_region, cropped_region, unknown_region, unknown}; closed `reasons`
  (candidate_include_as_figure/convert_to_table/summarize_as_text, review_only, anchor_matched,
  anchor_missing, source_page_reference, review_appendix, chandra_blocked, low_information_signal,
  unknown_candidate_action, input_sanitized); closed `warnings` (replacement_plan_malformed,
  replacement_item_malformed, asset_id_missing/invalid, source_page_invalid, source_provider_unrecognized,
  asset_type_unrecognized, candidate_action_unrecognized, anchor_id_invalid, anchor_lookup_missing,
  input_unrecognized).
- **Planning rules (advisory, conservative):** `candidate_include_as_figure` → `figure_reference`;
  `candidate_convert_to_table` → `table_reference`; `candidate_summarize_as_text` →
  `text_summary_reference`; `review_only` → `review_only` (placement `review_appendix`, anchor
  `not_required`); `unknown`/malformed → `unknown`. **Anchors are presence-only and safe-only:** for a
  reference mode, a matching source-page anchor yields `anchor_status:"matched"` + placement
  `source_page_reference` + a sanitized `anchor_id`; any miss (no inventory, uncovered page, or
  dropped/invalid anchor id) degrades to `anchor_status:"missing"` + placement `unknown` +
  `anchor_lookup_missing` — the item stays advisory and must not be placed without an anchor.
- **Chandra still blocked:** any `chandra_local` item (or one carrying a `chandra_blocked` marker on its
  input reasons) is **never** mapped to a direct `figure_reference`/`table_reference`/
  `text_summary_reference` mode — it degrades to `review_only` + `review_appendix` and always carries
  the closed reason `chandra_blocked`, because Chandra *extraction* integration remains gated by Slice
  45 `status:not_run` (`operator_input_not_supplied`). This core reads only the planned-item *shape*; it
  integrates nothing.
- **Pure / unwired / no production change:** not imported by `run_llm_job.py` or anything else; **no
  artifact written** (no `visual_insertion_plan.json` this slice); no API route; no frontend/UI; no
  export-bundle/generic artifact-list exposure; `visual_assets_manifest.json` /
  `visual_asset_scoring.json` / `visual_replacement_plan.json` schemas unchanged and **never mutated**;
  no extraction/OCR-routing/prompt/render/guide-output change; no `clean.md` write; no model/
  llama-server/cloud/network call; no image files/bytes. Captions/source text/provider payloads/paths/
  tokens/data-URIs/base64/argv are never read into output; an anchor inventory contributes only a
  sanitized slug-safe `anchor_id` (no raw anchor field echoed).
- **New test:** `test_scripts/test_visual_insertion_planner.py` (**243/0**) — include_as_figure/
  convert_to_table/summarize_as_text with a matching anchor → the matching reference mode; review_only
  needs no anchor; missing anchor degrades with `anchor_lookup_missing`/`anchor_missing`; malformed
  replacement plan → safe completed report with `replacement_plan_malformed`; malformed item → safe
  `unknown` fallback; invalid asset id → deterministic slug-safe fallback; invalid source page → `None`
  + `source_page_invalid`; invalid anchor id dropped (never emitted); chandra_local/chandra_blocked →
  `chandra_blocked` + never a direct insertion; no mutation of plan/anchors; smuggled
  captions/source-text/provider-payloads/paths/tokens/base64/data-URIs/image-bytes never leak; summary
  counts; determinism; no forbidden imports.
- **Validation:** `compileall api pipeline test_scripts` OK; insertion-planner **243/0**;
  replacement-planner **186/0**; replacement-plan-artifact **68/0**; scoring-core **146/0**;
  scoring-artifact **58/0**; advisory-export-bundle skips its endpoint section on host Python (FastAPI
  absent — covered live in Slice 51); manifest **65/0**; figure-extraction **50/0** (+2 skipped);
  chandra-normalizer **68/0**; chandra-local-provider **68/0**; chandra-live-harness **96/0**;
  ocr-modes **121/121**; ocr-routing-policy **120/120**; ocr-routing-integration **56/56**; offline
  eval scored 3 guides (no regression); frontend build + test green; verify-job-details-visual-advisory
  green; `git diff --check` clean. `smoke_release.py` / Docker **not required** (pure/unwired — no
  server/extraction/render/artifact/export/UI behavior touched). **Status:** NOT committed (per
  instruction) on `slice52-visual-insertion-planner-core`.

---

## Slice 50 — **Job Details "Visual advisory" diagnostics panel** (read-only UI) on `slice50-jobdetails-visual-advisory-panel`.

- **Purpose:** add a read-only Job Details drawer tab that surfaces the advisory **visual artifact
  chain** — `visual_assets_manifest.json` (Slice 40) → `visual_asset_scoring.json` (Slice 47) →
  `visual_replacement_plan.json` (Slice 49) — using **exact-name artifact fetches only**. It shows
  **safe COUNTS and closed-vocab status only**. It is a pure inspection slice: it does **not** change
  guide generation, prompts, extraction behavior, OCR routing, rendering, exports, or any artifact
  schema, it makes **no** production include/omit decision, and it does **not** embed visuals. **Not**
  a Chandra integration slice.
- **No backend changes.** Reuses the existing exact-name artifact routes
  (`/api/jobs/{id}/artifacts/<name>`) via the existing `getJobArtifact` / `artifactUrl` client helpers.
  The three advisory artifacts remain **out of** `ARTIFACTS` / `EXPORT_ARTIFACTS` / `_artifact_urls` /
  `_artifact_details` — they are **not** added to any generic artifact list, export bundle, or existing
  artifact UI row; they are reached only by exact filename through this read-only panel.
- **New frontend files:**
  - `frontend/src/visualAdvisoryArtifacts.js` — pure, React-free, node-testable helpers. Exposes the
    exact artifact-name constants, `isArtifactMissing(error)` (404 ⇒ "not generated for this job"),
    `safeToken(value)` (strict `^[a-z0-9_]+$`, ≤48 chars, else `unavailable`), and
    `summarizeVisualManifest` / `summarizeVisualScoring` / `summarizeVisualReplacementPlan`. Each
    returns a **count-only** view model (`state`/`tone`/`label` + non-negative integer counts); it
    never mutates input, never throws, and never passes through captions, OCR/source text, provider
    payloads, image refs/bytes, data URIs, base64, paths, URLs, or tokens — even closed-vocab reasons
    go through `safeToken` first.
  - `frontend/src/components/VisualAdvisoryPanel.jsx` — read-only drawer panel. Independently fetches
    the three exact-name artifacts (one missing/malformed artifact never blocks the others), treats
    **404 as a calm "Not available"** (no scary error), shows compact tiles (manifest:
    candidates / pages-with-signals / extracted-figures; scoring: scored + high/medium/low/unknown
    priority counts; plan: item count + candidate-action counts), summarizes
    `chandra_blocked` presence as an **advisory/blocked** notice with no raw detail, and renders
    exact-name "Open … JSON" links (`artifactUrl(jobId, name)` — the only permitted URL). No raw JSON
    is shown inline.
- **Wiring:** `frontend/src/components/RecentJobsPanel.jsx` (the Job Details drawer) gains a
  `Visual Advisory` tab (`Images` icon) rendering `<VisualAdvisoryPanel jobId={…} />`. Small additive
  `.sg-artifact-link` style in `frontend/src/design-system.css`.
- **New test:** `frontend/scripts/verify-job-details-visual-advisory.mjs` (added to `npm run test` and
  as `npm run verify-job-details-visual-advisory`) — exact artifact names; 404⇒missing; `safeToken`
  allowlist (rejects paths/free-text/over-long/non-string); manifest/scoring/plan completed counts;
  priority + candidate-action counts; `chandra_blocked` present via item reason AND top-level warning,
  absent otherwise; skipped/malformed degrade safely with closed-vocab reasons; and a serialized
  no-leak sweep over every produced view model (no caption/OCR/path/URL/data-URI/base64/token).
- **Confirmations:** guide output, prompts, rendering, extraction, OCR routing, and artifact schemas
  are **unchanged**; the manifest / scoring / plan artifacts are **not mutated** (read-only fetch);
  candidate actions remain **advisory only**; no generic artifact-list / export-bundle / existing-row
  exposure was added; no model / llama-server / cloud / network call beyond normal app API artifact
  fetches; no image file read, no image bytes, no `clean.md` write. Chandra *extraction* integration
  remains **blocked** by Slice 45 `status:not_run` (`operator_input_not_supplied`).
- **Validation:** `compileall api pipeline test_scripts` OK; planner **186/0**; plan-artifact **68/0**;
  scoring-core **146/0**; scoring-artifact **58/0**; manifest **65/0**; figure-extraction **50/0**
  (+2 skipped); chandra-normalizer **68/0**; chandra-local-provider **68/0**; chandra-live-harness
  **96/0**; ocr-modes **121/121**; ocr-routing-policy **120/120**; ocr-routing-integration **56/56**;
  extraction-metadata **9/9**; offline eval scored 3 guides (no regression); frontend build green;
  `npm run test` green (incl. new visual-advisory harness); `git diff --check` clean. Full Docker
  rebuild/recreate + `/api/health` + `smoke_release.py` run (UI/artifact-inspection slice).
  **Status:** committed (`1ed94c9`) and fast-forward merged to `chrome-renderer-v1` (pushed).

---

## Slice 51 — Include **visual advisory JSON artifacts** in **export bundles** when present on `slice51-visual-advisory-export-bundle`.

- **Purpose:** make multi-job export bundles more complete and portable by bundling the three advisory
  visual **JSON diagnostics** — `visual_assets_manifest.json` (Slice 40), `visual_asset_scoring.json`
  (Slice 47), `visual_replacement_plan.json` (Slice 49) — **alongside** the requested exports **only
  when they exist** for a job. This is an export-bundle **inclusion** slice only.
- **What it includes:** **JSON diagnostics only.** It does **not** include cropped image files or image
  bytes; the per-job `assets/*.png` crops are never bundled. It makes **no** production include/omit
  decision and embeds **no** visuals.
- **Backend code path:** `api/server.py` → `export_bundle` (`POST /api/exports/bundle`). A new narrow
  constant `VISUAL_ADVISORY_EXPORT_ARTIFACTS = ("visual_assets_manifest.json",
  "visual_asset_scoring.json", "visual_replacement_plan.json")` drives a small ride-along loop after
  the existing selector loop: for each name present (`_artifact_path(...).exists()`), the file is added
  to the job's bundle folder. The advisory files are **not** user selectors and are **deliberately kept
  out of** `EXPORT_ARTIFACTS` / `EXPORT_ARTIFACT_ALIASES` / `ARTIFACTS`, so no export-UI artifact type
  and no generic artifact UI row is added, and `artifact_types` is unchanged.
- **Gate / partial / absent behavior:** ride-along advisory files do **not** count toward
  `total_included`, so they never by themselves satisfy the "at least one requested artifact" gate — a
  bundle whose requested artifacts are all absent still returns the same `404`. If only some advisory
  files exist, only those are bundled; if none exist, bundle behavior is exactly as before. An absent
  advisory file is skipped calmly, never an error, and never fails the whole export.
- **Bundle index (`manifest.json`):** each job entry gains a `visual_advisory_included` list of the
  **filenames** bundled (presence/safe-metadata only). No raw artifact JSON content is inlined into the
  index, logs, or terminal output.
- **Comment hygiene:** the now-inaccurate "never in export bundles" notes in
  `api/server.py:_artifact_path` and `pipeline/job_manager.py` (scoring/plan properties) were corrected
  to "bundled as a ride-along JSON diagnostic when present, without adding a generic UI row." The
  `assets_dir` (PNG) comment is unchanged — image bytes are still never exported.
- **No-leak:** advisory files are read **read-only** and never mutated; no image bytes / data URIs /
  base64 / paths / URLs / headers / tokens / socket paths / executable paths / model/mmproj paths / raw
  argv / private document text / raw OCR / raw provider payloads enter logs, docs, tests, or the safe
  bundle metadata.
- **New test:** `test_scripts/test_visual_advisory_export_bundle.py` — drives `export_bundle` against
  temp-dir Jobs (monkeypatched `_get_job`): all-three-present inclusion; partial set; none-present =
  unchanged; **no `.png` / `assets/` entries**; index `visual_advisory_included` carries filenames only
  with no raw body / leak; advisory-only job still `404`s for an absent requested artifact; export
  leaves all three artifacts **byte-identical**; the three names stay out of `ARTIFACTS` /
  `EXPORT_ARTIFACTS` / aliases / `_artifact_urls` / `_artifact_details` while exact-name routes still
  resolve. Skips automatically when FastAPI is unavailable in host Python (full coverage in Docker).
- **Confirmations:** generated guide output, prompts, rendering, extraction behavior, OCR routing, and
  artifact schemas are **unchanged**; visual artifacts are **not mutated** by export; candidate actions
  remain **advisory only**; **no** generic artifact UI rows / export-UI exposure added; no frontend
  change; no API route change (existing `/api/exports/bundle` only); no `clean.md` write; no model /
  llama-server / cloud / network call. Chandra *extraction* integration remains **blocked** by Slice 45
  `status:not_run` (`operator_input_not_supplied`).
- **Validation:** `compileall api pipeline test_scripts` OK; new export-bundle test (host: SKIP — no
  FastAPI; Docker: full); planner **186/0**; plan-artifact **68/0**; scoring-core **146/0**;
  scoring-artifact **58/0**; manifest **65/0**; figure-extraction **50/0** (+2 skipped);
  chandra-normalizer **68/0**; chandra-local-provider **68/0**; chandra-live-harness **96/0**;
  ocr-modes **121/121**; ocr-routing-policy **120/120**; ocr-routing-integration **56/56**;
  extraction-metadata **9/9**; offline eval scored 3 guides (no regression); frontend build green;
  `npm run test` green; advisory mjs green; `git diff --check` clean. Full Docker rebuild/recreate +
  `/api/health` + `smoke_release.py` (export-behavior slice).
  **Status:** NOT committed (awaiting operator review).

---

## Slice 49 — Persist `visual_replacement_plan.json` as an **advisory exact-name artifact** on `slice49-visual-replacement-plan-artifact`.

- **Purpose:** wire the Slice 48 replacement-planner core into the job artifact flow as the sibling
  artifact `visual_replacement_plan.json`, **derived from** the already-written
  `visual_asset_scoring.json` report (with the manifest passed only for a **presence-only** asset-id
  cross-check). Pure artifact writing/serving — it does **not** change guide output, prompts,
  extraction, OCR routing, visual embedding, include/omit decisions, UI, or export bundles, and is
  **not** a Chandra integration slice. This is a second-level advisory artifact: manifest (V1 source)
  → scoring (Slice 47 advisory) → replacement plan (Slice 49 advisory, derived from scoring).
- **Artifact:** exact name `visual_replacement_plan.json`, written as a sibling of the scoring report.
  Reachable **only by exact name** at `/api/jobs/{id}/artifacts/visual_replacement_plan.json`; absent
  → graceful 404 ("Artifact not found."), like the other exact-name advisory siblings.
- **Wiring (production):**
  - `pipeline/job_manager.py` — new `Job.visual_replacement_plan_json` property
    (`<job>/visual_replacement_plan.json`).
  - `api/server.py` — dedicated `_artifact_path` branch mapping the exact name → that path
    (`application/json`). Deliberately **NOT** added to `ARTIFACTS` / `EXPORT_ARTIFACTS` /
    `_artifact_urls` / `_artifact_details` → no generic artifact-list, export-bundle, or UI row.
  - `pipeline/visual_replacement_planner.py` — new degrade-not-fail writers
    `write_visual_replacement_plan_report(job, scoring_report, *, manifest=None)` and
    `write_skipped_visual_replacement_plan_report(job, *, reason=…, safe_message=…)`. Added stdlib
    imports `json` + `sys`; the writers take a duck-typed `job` and call only its `save_text` /
    `visual_replacement_plan_json` (no `job_manager` import). The pure planning core is unchanged.
  - `pipeline/run_llm_job.py` — after `write_visual_asset_scoring_report(...)`, calls
    `write_visual_replacement_plan_report(job, scoring_report, manifest=visual_manifest_obj)` reusing
    the already-read manifest object and the returned scoring report (no re-read).
- **Writer behavior:** when the scoring report is a `completed` report with a list of `scores`, builds
  the plan via `build_visual_replacement_plan(scoring_report, manifest=…)` and writes it
  (`json.dumps(..., indent=2, sort_keys=True)`). When scoring is skipped/unavailable, writes a safe
  **skipped** plan (`status:"skipped"`, closed `reason` + short `safe_message`, `items:[]`) for
  consistency with the Slice 47 posture. Any write failure degrades to a `write_failed` skipped plan.
  Never raises into job generation, never gates/fails the job, never touches job status / validation /
  `clean.md`. Closed skip reasons: `visual_scoring_unavailable`, `visual_manifest_unavailable`,
  `visual_replacement_planning_unavailable`, `write_failed`.
- **Report shape preserved (Slice 48):** `{version:1, kind:"visual_replacement_plan",
  status:"completed"|"skipped", source:"visual_asset_scoring.json", items, summary, warnings}`.
  Candidate actions remain **advisory only** (`candidate_include_as_figure` / `candidate_convert_to_table`
  / `candidate_summarize_as_text` / `review_only` / `unknown`) — no production include/omit/render/
  prompt decision is made, no visual is embedded.
- **No mutation / no leak:** `visual_assets_manifest.json` and `visual_asset_scoring.json` are read
  only and **never mutated** (manifest contributes presence only — no field echoed). The plan never
  carries `image_ref`/`caption`/`source_text`, image bytes, data URIs, base64, paths, URLs, headers,
  tokens, socket/model/mmproj/executable paths, raw argv, raw provider/OCR payloads, or private
  document text; reasons/warnings are closed vocabulary.
- **Chandra still blocked:** any `chandra_local` item is planned **only as advisory** and carries
  `chandra_blocked`; Chandra *extraction* integration remains gated by Slice 45 `status:not_run`
  (`operator_input_not_supplied`).
- **New test:** `test_scripts/test_visual_replacement_plan_artifact.py` (**68/0**, api.server section
  auto-skipped in host Python) — completed write shape + summary counts; one item per score; advisory
  actions only; chandra item blocked+advisory; no caption/image_ref/source/path/url/base64 leak; no
  `image_ref`/`caption` field on items; scoring report + manifest not mutated (in-memory + on-disk
  bytes); manifest→scoring→plan integration with `has_manifest_match`; skipped on unavailable scoring
  (none/empty/skipped/scores-not-list/non-dict); skipped on write failure (no raw exception, no file
  left); explicit skipped writer defaults + out-of-vocab reason coercion; malformed scoring plans
  safely; exact-name route maps + not in ARTIFACTS/EXPORT_ARTIFACTS/_artifact_urls/_artifact_details.
  Existing planner test updated (**186/0**) — import hygiene now allows `json`/`sys`.
- **Validation:** `compileall api pipeline test_scripts` OK; planner **186/0**; plan-artifact **68/0**;
  scoring-core **146/0**; scoring-artifact **58/0**; manifest **65/0**; figure-extraction **50/0**
  (+2 skipped); chandra-normalizer **68/0**; chandra-local-provider **68/0**; chandra-live-harness
  **96/0**; ocr-modes **121/121**; ocr-routing-policy **120/120**; ocr-routing-integration **56/56**;
  extraction-metadata **9/9**; offline eval scored 3 guides (no regression); frontend build + test
  green; `git diff --check` clean. Full Docker rebuild/recreate + `/api/health` + `smoke_release.py`
  required (touches `api/server.py` + `job_manager.py` + `run_llm_job.py`). **Status:** NOT committed
  (awaiting operator review).

---

## Slice 48 — Visual **replacement planner core** (pure, unwired; roadmap V3) on `slice48-visual-replacement-planner-core`.

- **Purpose:** add a pure, deterministic **replacement planner core** — the next V3
  step after candidate scoring (`docs/VISION_ROADMAP.md` §8). It consumes an
  already-sanitized `visual_asset_scoring.json`-shaped scoring report (and, optionally, a
  `visual_assets_manifest.json`-shaped manifest for a **presence-only** cross-check) and returns a
  **separate advisory replacement plan** — a per-asset `candidate_action` / `placement` / `priority`
  with closed-vocab `reasons`. It does **not** mutate the scoring report or manifest, persist an
  artifact, embed visuals, change extraction/guides/rendering, or wire into production. **Not** a
  Chandra integration slice.
- **New module:** `pipeline/visual_replacement_planner.py` (stdlib-only: `re`, `typing`; imports
  nothing from `fitz`/Tesseract/llama.cpp/Chandra/Mistral/Gemini/LMM/renderers/server/job-manager/
  extraction/run-job/`visual_asset_scoring`/`visual_assets_manifest`). Public API (small, pure, total):
  - `plan_visual_replacement_candidate(score, *, asset=None) -> dict`
  - `plan_visual_replacement_candidates(scores, *, assets_by_id=None) -> list[dict]`
  - `build_visual_replacement_plan(scoring_report, *, manifest=None) -> dict`
- **Plan report shape:** `{version:1, kind:"visual_replacement_plan", status:"completed",
  source:"visual_asset_scoring.json", items:[…], summary:{item_count,
  candidate_include_as_figure_count, candidate_convert_to_table_count,
  candidate_summarize_as_text_count, review_only_count, unknown_count}, warnings:[…]}`. Each item:
  `{asset_id, source_page, source_provider, asset_type, priority, candidate_action, placement,
  reasons:[…], warnings:[…]}`.
- **Closed vocab only:** `candidate_action` ∈ {candidate_include_as_figure, candidate_convert_to_table,
  candidate_summarize_as_text, review_only, unknown}; `placement` ∈ {source_page_reference, unknown};
  `priority` ∈ {high, medium, low, unknown}; `source_provider` ∈ {fitz_local, chandra_local,
  mistral_ocr, unknown}; `asset_type` ∈ {page_visual_signal, extracted_figure, table, table_region,
  equation_block, diagram, figure, image_region, cropped_region, unknown_region, unknown}; closed
  `reasons` (score_high/medium/low, asset_type_diagram/figure/table/equation/page_signal,
  has_manifest_match, missing_manifest_match, review_required, chandra_blocked, low_information_signal,
  unknown_asset_type, input_sanitized); closed `warnings` (scoring_report_malformed,
  score_item_malformed, asset_lookup_missing, asset_id_missing/invalid, asset_type_unrecognized,
  source_provider_unrecognized, priority_unrecognized, candidate_action_unresolved, input_unrecognized).
- **Planning rules (advisory, conservative):** high/medium visual figure types (diagram, figure,
  image_region, cropped_region, extracted_figure) → `candidate_include_as_figure`; high/medium
  table/table_region → `candidate_convert_to_table`; high/medium equation_block (or a *legitimately*
  unknown visual block) → `candidate_summarize_as_text`; low priority / bare page signal →
  `review_only`; malformed/unknown-priority → `unknown`. A recognized-but-unmapped or
  coerced-unrecognized type at actionable priority falls back to `review_only` +
  `candidate_action_unresolved` (never guesses an embedding). `placement` is `source_page_reference`
  only for an actionable candidate with a known source page, else `unknown`.
- **Chandra still blocked:** any `chandra_local` item is planned **only as advisory** and always
  carries the closed reason `chandra_blocked`, because Chandra *extraction* integration remains gated
  by Slice 45 `status:not_run` (`operator_input_not_supplied`). This core reads only the asset
  *shape*; it integrates nothing.
- **Pure / unwired / no production change:** not imported by `run_llm_job.py` or anything else; no
  artifact written (no `visual_replacement_plan.json` this slice); no API route; no frontend/UI; no
  export-bundle/generic artifact-list exposure; `visual_assets_manifest.json` /
  `visual_asset_scoring.json` schemas unchanged and **never mutated**; no extraction/OCR-routing/
  prompt/render/guide-output change; no `clean.md` write; no model/llama-server/cloud/network call; no
  image files/bytes. Captions/source text/provider payloads are never read into output; a manifest
  cross-check contributes **presence only** (no manifest field echoed).
- **New test:** `test_scripts/test_visual_replacement_planner.py` (**186/0**) — include_as_figure for
  all high-priority visual types; medium/high table→convert; high/medium equation (and legit-unknown
  block)→summarize; low/page-signal→review_only; malformed score item→safe `unknown` fallback;
  malformed scoring report→safe completed report with `scoring_report_malformed`; manifest
  presence-match without field leak; missing match→`missing_manifest_match`+`asset_lookup_missing`;
  chandra_local→`chandra_blocked` + still advisory; no mutation of report/manifest; smuggled
  secrets/paths/base64/data-URIs/argv never leak; invalid asset ids→deterministic slug-safe fallback;
  summary counts; determinism; no forbidden imports.
- **Validation:** `compileall api pipeline test_scripts` OK; planner **186/0**; scoring-core **146/0**;
  scoring-artifact **58/0**; manifest **65/0**; figure-extraction **50/0** (+2 skipped);
  chandra-normalizer **68/0**; chandra-local-provider **68/0**; chandra-live-harness **96/0**;
  ocr-modes **121/121**; ocr-routing-policy **120/120**; ocr-routing-integration **56/56**; offline
  eval scored 3 guides (no regression); frontend build + test green; `git diff --check` clean.
  `smoke_release.py` / Docker **not required** (pure/unwired — no server/extraction/render/artifact
  behavior touched). **Status:** committed (`967748a`) and fast-forward-merged to
  `chrome-renderer-v1`; pushed.

---

## Slice 47 — Persist `visual_asset_scoring.json` as an **advisory exact-name artifact** on `slice47-visual-asset-scoring-artifact`.

- **Purpose:** persist the Slice 46 scoring report as the sibling artifact
  `visual_asset_scoring.json`, **derived from** the already-written `visual_assets_manifest.json`.
  Pure artifact writing/serving — it does **not** change guide output, prompts, extraction, OCR
  routing, visual embedding, include/omit decisions, UI, or export bundles, and is **not** a Chandra
  integration slice.
- **Artifact:** exact name `visual_asset_scoring.json`, written as a sibling of the manifest.
  Reachable **only by exact name** at `/api/jobs/{id}/artifacts/visual_asset_scoring.json`; absent →
  graceful 404 ("Artifact not found."), like the other exact-name advisory siblings.
- **Wiring (production):**
  - `pipeline/job_manager.py` — new `Job.visual_asset_scoring_json` property (`<job>/visual_asset_scoring.json`).
  - `api/server.py` — dedicated `_artifact_path` branch mapping the exact name → that path
    (`application/json`). **Deliberately NOT** added to `ARTIFACTS`, `EXPORT_ARTIFACTS`,
    `_artifact_urls`, `_artifact_details`, export bundles, or any UI row.
  - `pipeline/run_llm_job.py` — in `_attach_sources`, immediately after
    `write_visual_assets_manifest(...)`, calls
    `write_visual_asset_scoring_report(job, _read_visual_manifest_for_scoring(job))`. The helper
    reads the just-written manifest back off disk and returns `None` on any read/parse error
    (total, never raises, never mutates). Written **exactly when** the manifest is written; non-PDF /
    no-extraction jobs omit **both** artifacts (no call).
  - `pipeline/visual_asset_scoring.py` — thin degrade-not-fail writer
    `write_visual_asset_scoring_report(job, manifest)` (+ `write_skipped_visual_asset_scoring_report`,
    `_is_scorable_manifest`, `_skipped_report`); stable JSON (`indent=2, sort_keys=True`). Closed
    skip reasons only: `visual_manifest_unavailable`, `visual_scoring_unavailable`, `write_failed`.
    `safe_message` is a fixed constant; stderr (if reached) carries an **exception class name only**.
    The Slice 46 `score_visual_assets_manifest(...)` report shape is unchanged.
- **Degrade-not-fail / no mutation:** the writer never raises into job generation, never gates/fails
  the job, never touches job status / validation / `clean.md`, and **never mutates**
  `visual_assets_manifest.json`. A non-scorable/unavailable manifest → `skipped`
  (`visual_manifest_unavailable`); a write error → `skipped` (`write_failed`).
- **`recommended_action` stays `unknown`** for every score (no include/omit decision); no model /
  `llama-server` / Chandra / Mistral / Gemini / network / image-file access; no `clean.md` write.
- **Chandra still blocked:** Chandra **extraction** integration remains gated by Slice 45
  `status:not_run` (`operator_input_not_supplied`); this slice only persists a report derived from
  whatever manifest the existing `fitz_local` path produced — it integrates nothing.
- **New test:** `test_scripts/test_visual_asset_scoring_artifact.py` (**58/0**; api.server endpoint
  section auto-skips when FastAPI is absent in host Python — covered in Docker) — completed write +
  shape/summary counts; `recommended_action` all `unknown`; no caption/image_ref/path/url/base64
  leak in artifact bytes; manifest file+dict unmutated; manifest→read-back→score integration;
  skipped on unavailable/malformed manifest (5 cases); write-failure degrades to `write_failed`
  (via a `save_text`-raising `Job` subclass; no raw exception text in the report); explicit-skipped
  defaults + out-of-vocab reason coerced; exact-name route resolves & not in
  `ARTIFACTS`/`EXPORT_ARTIFACTS`/`_artifact_urls`/`_artifact_details`. Also updated
  `test_scripts/test_visual_asset_scoring.py` to allow stdlib `json`/`sys` (now **146/0**).
- **Validation:** `compileall api pipeline test_scripts` OK; scoring-core **146/0**; scoring-artifact
  **58/0**; manifest **65/0**; figure-extraction **50/0** (+2 skipped); chandra-normalizer **68/0**;
  chandra-local-provider **68/0**; chandra-live-harness **96/0**; ocr-modes **121/121**;
  ocr-routing-policy **120/120**; ocr-routing-integration **56/56**; extraction-metadata **9/9**;
  offline eval scored 3 guides (no regression); frontend build + test green; fresh Docker
  build + `/api/health` ok + `smoke_release.py`; `git diff --check` clean. **Status:** NOT committed
  (awaiting operator review).

---

## Slice 46 — Visual asset **scoring core** (pure, unwired; roadmap V3) on `slice46-visual-asset-scoring-core`.

- **Purpose:** add a pure, deterministic **scoring core** for visual asset candidates — the V3
  "candidate scoring" step from `docs/VISION_ROADMAP.md` §8, sitting between the advisory manifest
  (V1) and any future guide-inclusion decision (V4+). It scores existing
  `visual_assets_manifest.json`-shaped assets and returns a **separate advisory scoring report**;
  it does **not** mutate the manifest, change guides/rendering, embed visuals, or wire into
  production. **Not** a Chandra integration slice.
- **New module:** `pipeline/visual_asset_scoring.py` (stdlib-only: `re`, `typing`; imports nothing
  from `fitz`/Tesseract/llama.cpp/Chandra/Mistral/Gemini/LMM/renderers/server/job-manager/
  extraction). Public API (small, pure, total):
  - `score_visual_asset_candidate(asset, *, page_context=None) -> dict`
  - `score_visual_asset_candidates(assets, *, page_context_by_page=None) -> list[dict]`
  - `score_visual_assets_manifest(manifest, *, page_context_by_page=None) -> dict`
- **Report shape:** `{version:1, kind:"visual_asset_scoring", status:"completed",
  source:"visual_assets_manifest.json", scores:[…], summary:{asset_count, high/medium/low/
  unknown_priority_count}, warnings:[…]}`. Each score:
  `{asset_id, source_page, source_provider, asset_type, recommended_action:"unknown", priority,
  include_score, reasons:[…], warnings:[…]}`.
- **Closed vocab only:** `priority` ∈ {high, medium, low, unknown}; `recommended_action` stays
  **`unknown` for every score** this slice; `source_provider` ∈ {fitz_local, chandra_local,
  mistral_ocr, unknown}; `asset_type` ∈ {page_visual_signal, extracted_figure, table, table_region,
  equation_block, diagram, figure, image_region, cropped_region, unknown_region, unknown};
  closed `reasons` tokens (asset_type_table/diagram/equation/extracted_figure, has_bbox,
  has_caption, large_region, page_has_images, page_has_drawings, provider_*, low_information_signal,
  unknown_asset_type, input_sanitized); closed `warnings` tokens (asset_id_missing/invalid,
  source_page_invalid, asset_type_unrecognized, source_provider_unrecognized, bbox_invalid,
  signals_invalid, manifest_malformed, input_unrecognized).
- **Behavior:** pure/deterministic/total — never raises, never mutates input, no clock/random/
  network/file/image access. Invalid/missing asset ids → deterministic slug-safe fallback
  (`asset_0001`); source page coerced to a positive int or `None`; bbox parsed only as 4 finite
  ordered numbers; **captions used only as a boolean `has_caption` signal and never emitted**;
  unknown/malformed assets score `unknown`/`low` with closed warnings. Heuristics keep
  tables/diagrams/equations/extracted-figures above a bare `page_visual_signal`; strong page
  signals lift a page signal at most low→medium (conservative).
- **Unwired / no production change:** not imported by `pipeline/run_llm_job.py` or anything else;
  no artifact written; `pipeline/visual_assets_manifest.py` unchanged (no schema change); no
  extraction/OCR-routing change; no Chandra provider/harness change; no model/llama-server/cloud
  calls; no API route; no frontend/UI; no Provider Settings/LMM change; no prompt/render/export
  change; no `clean.md` write; no image files/bytes.
- **Chandra still blocked:** Chandra **extraction** integration remains gated by Slice 45
  `status:not_run` (`operator_input_not_supplied`) until a live harness pass is recorded. This
  slice only *reads the asset shape* the Slice 42 normalizer would emit; it integrates nothing.
- **New test:** `test_scripts/test_visual_asset_scoring.py` (**146/0**) — minimal page_visual_signal;
  extracted_figure with bbox+large-region; Chandra diagram/table/equation_block shapes; deterministic
  priority ordering; action-always-unknown; bbox invalid → `bbox_invalid`; id missing/unsafe →
  safe fallback; malformed/non-dict manifest+assets safe; no input mutation; no raw caption emitted;
  smuggled path/URL/token/header/base64/data-URI/argv/socket/gguf/mmproj strings never appear;
  source_page coercion; no forbidden imports.
- **Validation:** `compileall api pipeline test_scripts` OK; scoring **146/0**; manifest **65/0**;
  figure-extraction **50/0** (+2 skipped); chandra-normalizer **68/0**; chandra-local-provider
  **68/0**; chandra-live-harness **96/0**; ocr-modes **121/121**; ocr-routing-policy **120/120**;
  ocr-routing-integration **56/56**; offline eval scored 3 guides (no regression); frontend
  build OK + frontend test green; `git diff --check` clean. `smoke_release.py` **not required** —
  no production-wired/server/extraction/render/artifact behavior is touched (pure unwired module).
- **Status: NOT committed** (awaiting operator review).

---

## Slice 45 — Chandra live-harness validation report + operator runbook (DOCS-ONLY) — committed `591d664`, fast-forward merged + pushed to trunk `chrome-renderer-v1`.

- **Purpose:** a **docs-only gate/report** slice that records (a) **how to safely run** the
  Slice 44 Chandra live validation harness and (b) a **sanitized** live validation result if an
  operator has a local Chandra-capable `llama-server` available. **Not** an integration slice —
  no code/test/app behavior changes.
- **New doc:** `docs/CHANDRA_LIVE_HARNESS_VALIDATION.md` (§1 purpose · §2 operator-owned
  preconditions · §3 placeholder-only run command template · §4 safe-output policy · §5
  recordable summary fields + this slice's result · §6 gate decision · §7 future-slice notes).
  - **Run template uses placeholders only** (`--endpoint "<local-openai-compatible-endpoint>"`,
    `--image "<non-private-test-image>"`) — no real path/endpoint/port/token/socket/model/mmproj/
    executable recorded.
  - **Safe-output policy:** record only closed-vocabulary summary fields (`reachable`,
    `request_ok`, `parse_status`, `normalized_kind`, `normalized_status`, `source_text_char_count`,
    `asset_count`, closed-vocab `parse_warnings`/`normalize_warnings`, `failure_category`,
    `elapsed_ms` if safe). Never raw OCR text, raw provider response, image path/basename/bytes,
    base64/data URI, full URL/query, headers/tokens, or model/mmproj/exec/socket paths.
- **Recorded validation result this slice:** `status: not_run`, reason `operator_input_not_supplied`.
  No live Chandra `llama-server` endpoint and no non-private test image were supplied during this
  docs-only slice, so **no live HTTP request was made** and **no result was fabricated**. The
  Slice 44 harness remains proven only by its fake-transport suite (`test_chandra_live_harness`
  **96/0**).
- **Gate decision:** current state is `not_run` ⇒ the **disabled extraction-side adapter slice
  stays blocked** until a live run passes. A pass ⇒ proceed to a still-**disabled**, off-by-default
  extraction-side adapter (Tesseract/`fitz` fallback, degrade-not-fail); a fail/`not_run` ⇒ fix the
  harness/provider boundary or rerun first.
- **Scope (docs-only):** no code, no tests, no app integration, no extraction wiring, no
  `ocr_routing`/`extraction_metadata.json`/`visual_assets_manifest.json` change, no API route, no
  frontend/UI, no Provider Settings, no Local Model Manager, no render/export/artifact change, no
  `clean.md` write, no `llama-server` management, no subprocess/Docker, no model/mmproj/quant file,
  no raw OCR/provider output committed.
- **Validation:** `git diff --check` clean; `git diff --name-only` docs-only (new
  `docs/CHANDRA_LIVE_HARNESS_VALIDATION.md` + `CURRENT_TASK.md` + `NEXT_CHAT_HANDOFF.md` +
  `DECISIONS.md`). No build/smoke required — no code touched.
- **Status: committed `591d664`, fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

---

## Slice 44 — Chandra local provider **live validation harness** (manual / opt-in only) — committed `8468c16`, merged + pushed to trunk `chrome-renderer-v1`.

- **Purpose:** add a **manual, opt-in** live validation harness so an operator can prove —
  *outside production app flow* — that a local Chandra-capable `llama-server` **they started
  themselves** can accept one page image and return output that flows cleanly through the
  Slice 43 boundary: operator's local server response →
  `parse_chandra_chat_response(...)` → `normalize_chandra_chat_response(...)` →
  Slice 42 normalizer output → **safe closed-vocabulary summary only**. Harness slice only.
- **Manual / opt-in:** a real HTTP request happens **only** when the operator runs the CLI with
  their own `--endpoint` and `--image`. **Not** part of release smoke. Importing the module
  triggers **no** network / file read / model call / subprocess / Docker / server check.
- **What it does NOT do (unchanged production behavior):** does **not** wire Chandra into
  `pipeline/extract.py`, OCR routing, `ocr_routing`, `extraction_metadata.json`, or the
  `visual_assets_manifest.json` schema; writes no `clean.md`; adds **no** API route, frontend/UI,
  Provider Settings, or Local Model Manager change; touches no renderers/exports/artifacts or
  study-guide prompt assembly; starts/stops/manages **no** `llama-server`; uses **no** subprocess,
  shell, or Docker call; downloads **no** model; commits **no** model/mmproj/quant file, raw OCR
  dump, screenshot, or image fixture (tests use tiny synthetic bytes in a temp file).
- **Script:** new **`test_scripts/validate_chandra_local_provider_live.py`** — stdlib transport
  (`urllib`) used **only** when the operator runs it; tests inject a fake transport. Shape:
  - `run_validation(endpoint, image_path, *, transport=None, timeout_seconds=60.0, prompt=None) -> dict`
    — **total/leak-safe**: builds the request via the Slice 43
    `build_chandra_image_message_payload(...)`, sends it (injected/real transport), parses +
    normalizes, and returns a closed-vocabulary summary. Every failure path resolves to a closed
    `failure_category`; nothing raises to the caller.
  - `redact_endpoint_for_display(endpoint) -> str` — keeps only scheme+host, masks the port
    (`<port>`), drops path/query and any `user:token@` userinfo; non-http(s)/unparseable →
    `"local_endpoint_supplied"`.
  - `safe_summary_from_normalized(normalized, parse_warnings=None) -> dict` — projects the Slice 42
    output to counts + filtered closed-vocab warnings (source text reported only as a **char
    count**, never echoed).
  - `http_transport(url, payload, timeout) -> response` — stdlib `urllib` POST, **no auth header**;
    maps connection/HTTP/decoding errors to `connection_failed` / `request_failed` /
    `response_malformed` carrying **only** the category.
  - `print_safe_summary(summary, *, verbose=False)` — prints a **whitelisted** key set as JSON.
- **Safe summary fields (closed vocabulary):** `reachable`, `request_ok`, `image_supplied`,
  `endpoint_display` (redacted), `parse_status` (`none`/`ok`/`empty`/`malformed`), `normalized_kind`,
  `normalized_status`, `source_text_char_count`, `asset_count`, `parse_warnings`,
  `normalize_warnings`, `failure_category` (`connection_failed` / `request_failed` /
  `response_malformed` / `provider_empty_content` / `normalization_failed` / `image_read_failed` /
  `invalid_endpoint`), and `elapsed_ms` (verbose only). **Never** prints/returns raw OCR text, the
  raw provider payload, the image path, image bytes, a base64/data URI, a full URL, query strings,
  headers, `Authorization`/`Bearer` fragments, raw argv, or model/mmproj/executable/socket paths.
- **Tests:** new **`test_scripts/test_chandra_live_harness.py`** — **96/0**, fake transport only,
  no live server: success parse+normalize; safe-summary counts/tokens only + no raw OCR text;
  malformed-shape and `response_malformed`/`connection_failed`/`request_failed` categories
  (no traceback/secret echo); endpoint redaction of query/token/userinfo/Bearer/path-token →
  `http://<host>:<port>/...`; image path/basename not echoed; base64 data URI in the *request* but
  never in the summary/print; raw malicious payload (URL/path/auth/key/socket/argv/gguf/`<script>`)
  never leaked; request built via the Slice 43 payload builder; `provider_empty_content` and
  `image_read_failed` categories; real `http_transport` never invoked; no forbidden imports.
- **Validation (all green):** `npm --prefix frontend run build` + `run test`;
  `python -m compileall api pipeline test_scripts`; `test_chandra_local_provider` 68/0;
  `test_chandra_live_harness` 96/0; `test_chandra_normalizer` 68/0; `test_visual_assets_manifest`
  65/0; `test_local_figure_extraction` 50/0/2; `test_ocr_provider` 18/18; `test_ocr_routing_policy`
  120/120; `test_ocr_routing_integration` 56/56; `test_ocr_modes` 121/121; `test_extraction_metadata`
  9/9; `test_pdf_visual_signals` 44/44; `test_pdf_page_classification` 56/56; `test_math_verifier`
  74/74; `test_guide_lint` 74/74; `test_eval_harness` 64/64; `test_page_anchor_reachability` 21/21;
  `test_source_page_citations` 19/19; `test_ask_retrieval_relevance` 12/0; `test_ask_lexical_hygiene`
  34/0; `test_guide_lint_artifact` 26/26; `eval/run_eval.py --offline --all` (3 guides, no
  regression); `git diff --check` clean. `smoke_release.py` **not** required — no
  server/extraction/render/artifact/UI behavior is touched (manual-harness-only).
- **Files:** new `test_scripts/validate_chandra_local_provider_live.py`, new
  `test_scripts/test_chandra_live_harness.py`, docs (`CURRENT_TASK.md`, `NEXT_CHAT_HANDOFF.md`,
  `DECISIONS.md`). **Status: committed `8468c16`, fast-forward merged + pushed to trunk
  `chrome-renderer-v1`.**
- **Next (deferred, separate slice):** only after this harness proves stable on real hardware,
  decide whether to add a **disabled** extraction-side adapter (still off-by-default, with
  Tesseract/`fitz` fallback and degrade-not-fail) — no extraction wiring before then.

---

## Slice 43 — Chandra local provider/client skeleton (committed `2bc14ef`, merged to trunk; DISABLED / UNWIRED).

- **Purpose:** add a small, **disabled/unwired** Chandra local provider/client skeleton
  that names the third boundary in the Chandra chain and makes it testable —
  **without running any model**:
  page image bytes → **OpenAI-compatible `llama-server` request shape** →
  (a future integration runs the model) → raw Chandra output string →
  **Slice 42 normalizer** → safe normalized output. **Foundation slice only**, not a
  provider integration: nothing in a production path constructs or calls it.
- **What it does NOT do:** does not run Chandra / `llama-server`; opens no socket; makes
  no real model/server/network call (tests use injected fake responses only); does not
  download or open any model / mmproj / quant file; does not wire into
  `pipeline/extract.py` or OCR routing; does not change `ocr_routing`,
  `extraction_metadata.json`, or the `visual_assets_manifest.json` schema; writes no
  `clean.md`; embeds no visuals; adds no API route, frontend toggle, Provider Settings,
  or Local Model Manager change; does not touch prompts/render/exports or any generated
  guide. `ChandraLocalProvider.enabled is False` by construction.
- **Module:** new **`pipeline/chandra_local_provider.py`** — stdlib-only (`base64`,
  `typing`) + the Slice 42 normalizer; **no new dependency**, **no import** of
  `fitz`/Tesseract/llama.cpp/`openai`/Mistral/Gemini/Chandra-runtime/LMM/`socket`/
  `subprocess`/HTTP client. Public API:
  - `build_chandra_image_message_payload(image_bytes, *, mime_type="image/png", prompt=None) -> dict`
    — OpenAI-compatible multimodal chat payload (`messages=[{role:"user", content:[text, image_url]}]`,
    conservative `temperature=0.0` + `max_tokens`); image → base64 data URI **only here**;
    no model id / base URL / host path / argv embedded. Non-bytes input raises `TypeError`
    (developer-misuse guard) without echoing the value; unknown/hostile `mime_type` collapses to PNG.
  - `parse_chandra_chat_response(response) -> {"content": str, "warnings": [...]}` — accepts the
    `{"choices":[{"message":{"content":...}}]}` dict shape and SDK-object equivalents; **total**
    (never raises), degrades to closed-vocab warnings (`empty_response`/`no_choices`/`no_message`/
    `no_content`/`malformed_response`), and **never echoes the raw provider payload**.
  - `normalize_chandra_chat_response(response, *, source_page=1) -> dict` — bridges parse →
    `normalize_chandra_output(...)`; returns the Slice 42 `kind:"chandra_normalized_output"`
    envelope (all leak-scrubbing delegated to the normalizer); empty/malformed → valid
    `completed` output with `empty_output`.
  - `class ChandraLocalProvider` (`provider_id="chandra_local"`, `enabled=False`,
    `is_enabled() -> False`) — thin handle delegating to the module functions.
- **Default OCR/layout prompt:** `CHANDRA_OCR_LAYOUT_PROMPT` constant requests layout HTML with
  `data-label` + `data-bbox`, HTML tables, LaTeX math, and captioned diagrams/figures. It is a
  fixed template constant, **not** wired into guide generation.
- **Tests:** new **`test_scripts/test_chandra_local_provider.py`** — **68/0** (payload shape +
  no model/path/argv leak; prompt requests `data-label`/`data-bbox`/tables/LaTeX/captions; image
  data URI only in the request, not in parsed/normalized output; mime whitelist; non-bytes
  rejected w/o echo; parse normal/object/degrade/no-echo; normalizer bridge incl. empty + malicious
  scrub; provider disabled/unwired; no-forbidden-imports). Injected fake responses only — no real
  Chandra dump, model file, or local path.
- **Validation (all green):** `python -m compileall api pipeline test_scripts`;
  `test_chandra_normalizer` 68/0; `test_chandra_local_provider` 68/0; `test_visual_assets_manifest`
  65/0 (manifest unchanged); `test_local_figure_extraction` 50/0/2-skip; `test_ocr_provider` 18/18;
  `test_ocr_routing_policy` 120/120; `test_ocr_routing_integration` 56/56; `eval/run_eval.py
  --offline --all` (3 guides, no regression, delta 0.0); frontend `build` + `test` green;
  `git diff --check` clean. `smoke_release.py` not required — no server/extraction/render/artifact
  behavior is touched (no production wiring).
- **Files:** new `pipeline/chandra_local_provider.py`, new `test_scripts/test_chandra_local_provider.py`,
  this log, `NEXT_CHAT_HANDOFF.md`, `DECISIONS.md`. **No app integration, no manifest schema change,
  no extraction/OCR/prompt/render/UI/export change.** **Do not commit until the operator says so.**
- **Next (design, not built):** a `chandra_local` integration slice that flips `enabled` behind an
  explicit, **off-by-default** local OCR route on the LMM `llama-server` path — running the model,
  handing its raw string to this bridge, with **Tesseract/`fitz` fallback and degrade-not-fail**
  behavior; then candidate scoring/`recommended_action` and asset-aware prompt/render embed.

---

## Slice 42 — Chandra output normalizer core (committed `6e7f55f`, merged + pushed to trunk `chrome-renderer-v1`).

- **Purpose:** add a **pure, deterministic Chandra output normalizer** that turns a
  *raw Chandra layout string* (the `data-bbox` + `data-label` HTML-ish output Slice 41
  confirmed) into two GuideForge-shaped products — a safe **`source_text`** fragment
  and **`visual_assets_manifest.json`-shaped asset candidates** — **without running
  Chandra, `llama-server`, or any model.** Normalization-core slice, **not** provider
  integration. Off the wire entirely; nothing is wired into extraction.
- **What it does NOT do:** does not call Chandra / `llama-server`; does not download or
  open any model / mmproj / quant file; does not wire Chandra into extraction or OCR
  routing; does not write `clean.md` or any image bytes; does not score candidates
  (`recommended_action` stays `"unknown"`, `asset_ref` stays `null`); does not change
  the `visual_assets_manifest.json` schema, prompts, render, exports, UI, or any
  generated guide.
- **Module:** new **`pipeline/chandra_normalizer.py`** — pure stdlib (`re`,
  `html.parser.HTMLParser`, `typing`), **no new dependency**, **no import** of
  `fitz`/Tesseract/llama.cpp/Mistral/Gemini/Chandra-runtime/LMM. Public API:
  - `normalize_chandra_output(raw_output, *, source_page=1) -> dict` (total; never raises)
  - `extract_chandra_blocks(raw_output) -> list[dict]`
  - `chandra_blocks_to_source_text(blocks) -> str`
  - `chandra_blocks_to_manifest_assets(blocks, *, source_page) -> list[dict]`
- **Output shape:** `{version:1, kind:"chandra_normalized_output", status:"completed",
  source_provider:"chandra_local", source_text, assets[], warnings[]}`. Each asset
  mirrors the Slice 38/40 manifest asset (`asset_id` `page_<NNNN>_chandra_<II>`,
  `source_page`, `asset_type`, `bbox`, `caption`, `source_provider:"chandra_local"`,
  `recommended_action:"unknown"`, `dedupe_group:null`, `scores:{}`, **`asset_ref:null`**,
  `signals.chandra_label`, `warnings[]`).
- **Asset mapping (closed vocab):** `Table→table`, `Equation/Formula/Math→equation_block`,
  `Diagram/Chart/Graph→diagram`, `Figure→figure`, `Image/Picture→image_region`,
  unrecognized label → `unknown_region` (+ `label_unrecognized`). **Text/caption blocks
  are NOT emitted as visual assets** (they feed `source_text` only).
- **`source_text` behavior:** deterministic; headers → Markdown `#`/`##`, tables → simple
  Markdown grid, equations → preserved LaTeX/text, visual-region captions → plain line;
  no raw HTML/script/style, image bytes/base64, paths, URLs, or secrets.
- **Bbox behavior:** parses 4 finite, well-ordered floats from `data-bbox` → `[x0,y0,x1,y1]`;
  missing → `null` + `bbox_missing` (visual regions), unparseable/ill-ordered → `null` +
  `bbox_invalid`. Raw bbox strings are never echoed.
- **Safety / no-leak:** every captured/raw string is scrubbed field-by-field — strips
  URLs, abs/UNC/Windows paths, `.sock`, `Authorization`/`Bearer`, `sk-`/`pk-`-style keys,
  `--flag` argv, `data:…;base64`/long base64 runs, `<script>`/`<style>`, residual tags,
  control chars. Output is JSON-safe and uses closed-vocab warnings only.
- **Tests:** new **`test_scripts/test_chandra_normalizer.py`** — **68/0** (envelope +
  determinism, table/equation/diagram+caption, invalid/missing bbox, unrecognized label,
  plain-text/markdown fallback, never-raises on malformed + non-string, smuggled-secret
  no-leak sweep, multi-region ids/ordering, helper functions, no-forbidden-imports).
  Tiny **handcrafted synthetic** fixtures only — no real Chandra dump / private doc /
  screenshot / local path.
- **Validation (all green):** `python -m compileall api pipeline test_scripts`;
  `git diff --check`; the full focused battery incl. `test_visual_assets_manifest`
  (manifest unchanged) and `test_local_figure_extraction`; `test_chandra_normalizer`
  68/0; `eval/run_eval.py --offline --all` (3 guides, no regression); frontend `build` +
  `test` green; `smoke_release.py` **29/0/0**.
- **Files:** new `pipeline/chandra_normalizer.py`, new `test_scripts/test_chandra_normalizer.py`,
  this log, `NEXT_CHAT_HANDOFF.md`, `DECISIONS.md`. **No app integration, no manifest
  schema change, no extraction/OCR/prompt/render/UI/export change.** **Do not commit until
  the operator says so.**
- **Next (design, not built):** a `chandra_local` provider/integration slice that actually
  runs the model on the LMM `llama-server` path and feeds this normalizer; candidate
  scoring/`recommended_action`; asset-aware prompt/render embed.

---

## Slice 41 — Chandra GGUF hands-on spike (committed `218de18`, merged + pushed to trunk `chrome-renderer-v1`; docs-only).

- **Purpose:** the **hands-on** follow-up to Slice 39's docs-only Chandra gate —
  actually download, convert, and **run Chandra OCR 2 as GGUF through the existing
  `llama.cpp`/`llama-server` path** to decide whether it can produce useful
  OCR/document-extraction for GuideForge. **Spike/report only — no app integration.**
  Full write-up: **`docs/CHANDRA_GGUF_SPIKE_REPORT.md`**.
- **Verdict: PROCEED TO PROVIDER DESIGN** (strong pass), gated behind the LMM /
  `llama-server` path + a small mmproj build step + an output-normalisation slice.
- **What ran (on RTX 5070 Ti 16 GB, `llama.cpp` build 9307 / `549b9d8`, CUDA):**
  - Confirmed arch support: `libllama` has `qwen35`(text)+`qwen3vl`(vision) loaders;
    convert tooling's `MMPROJ_MODEL_MAP` routes `Qwen3_5ForConditionalGeneration →
    qwen3vl`, so this build **can export a Chandra mmproj**.
  - **Key blocker found + solved:** the only public GGUF
    (`hyojk2001/chandra-ocr-2-Q4_K_M-GGUF`) is **text-only, NO mmproj** (gguf-my-repo)
    → can't OCR as-is. Generated **mmproj-chandra-f16.gguf (~676 MB)** + text quants
    **Q4_K_M/Q5_K_M/Q8_0** from the **official** `datalab-to/chandra-ocr-2` (~10.6 GB)
    with build-9307 convert tooling.
  - **Load:** success on both `llama-mtmd-cli` and `llama-server` (`-ngl 99`,
    `--mmproj`, `-c 8192`).
  - **Image input:** works via CLI **and** the **OpenAI-compatible**
    `llama-server /v1/chat/completions` `image_url` data-URI path (the LMM-style path).
  - **Quality (3 synthetic, non-private, hand-checked pages):** near-perfect.
    Native output is **layout-HTML with `data-bbox` + `data-label`**
    (Section-Header/Text/**Table**/**Equation-Block**/**Diagram**), **HTML tables**,
    **LaTeX math**, diagram regions w/ captions. Held **even at Q4_K_M**.
  - **VRAM (not the blocker):** Q4 ~5.4 GB · Q5 ~5.8 GB · Q8 ~7.2 GB (8K ctx);
    resident server ~7.3 GB, frees cleanly on stop. Model trains at **256K ctx**.
  - **Throughput:** ~121 gen tok/s warm server → ~**8–20 pages/min** (batch-OK, not
    interactive). Long decks **not** run.
- **Fit:** runs on the **same `llama-server` the LMM already supervises** — **no new
  service**; only adds an mmproj + image message. Output maps to **`clean.md`** source
  text and (strongly) to **`visual_assets_manifest.json`** asset candidates (bbox /
  type / caption / table / equation), complementing Slice 40's `fitz` crops. **No
  manifest schema change made** (forbidden this slice).
- **Files (docs-only):** new `docs/CHANDRA_GGUF_SPIKE_REPORT.md`; this log;
  `docs/NEXT_CHAT_HANDOFF.md`. **No app/build/smoke** (no app code touched). Model
  files / weights / mmproj / quants live in a **throwaway workspace outside the repo**
  — none committed.
- **Recommended next slices (design, not yet built):** (1) host-companion **mmproj/
  quant build** step w/ a **pinned llama.cpp build**; (2) pure **output→clean.md +
  manifest normaliser** (reusing the Slice 38/40 schema); (3) **prompt/template**
  lock for reliable bbox+label output (`--image-min-tokens 1024` for grounding).
  **Fallback contract preserved:** Chandra unavailable → Tesseract/`fitz`; Chandra
  bad/timeout → degrade, never fail generation. Keep off-by-default + local-only.
- **Validation (docs/spike slice):** `git status --short`, `git diff --check`,
  `git diff --name-only` — changes are **docs-only**; repo clean of model artifacts.

---

## Slice 40 — Local figure extraction / cropping into the visual manifest (uncommitted on `slice40-local-figure-extraction-into-manifest`).

- **Purpose:** the **first real extractor-output change** in the visual stack (roadmap
  V1→V2 bridge). Where Slice 38 only emitted page-level `page_visual_signal` candidates
  (`bbox: null`), Slice 40 actually **crops embedded image regions out of the PDF** with
  PyMuPDF (`fitz`) and adds real **`extracted_figure`** assets — real `bbox`, a **safe
  relative `image_ref`** (`assets/<slug>.png`), and a saved PNG under the job's new
  `assets/` dir. **`fitz_local` only** — no Chandra/Mistral/Gemini/VLM, no network, no OCR.
- **Gated / off by default:** `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION` (truthy = on). When
  unset/false the extractor is never invoked and the manifest is **byte-identical to
  Slice 38**. Verified flag-on (1 figure cropped, PNG written, in-page bbox) and flag-off
  (no work) live in the container.
- **No guide/prompt/render/export/UI change:** assets do **not** reach the generated
  guide this slice — Slice 40 only writes the **manifest + asset PNGs**. (Asset-aware
  prompt/render is a later V4/V5 slice; orphan-`{{figure}}`/coverage tests belong there.)
- **Files:**
  - `pipeline/visual_asset_extractor.py` (new) — `fitz` crop module:
    `local_figure_extraction_enabled()` + `extract_local_figures(pdf, assets_dir,
    source_index, pages, remaining_budget)`. Degrade-not-fail (missing fitz / corrupt PDF
    / bad image ⇒ fewer/zero assets, never a job failure). **Explosion prevention:** skips
    tiny/decorative regions (`MIN_SIDE_POINTS=24pt`, `MIN_AREA_FRACTION=0.004`), collapses
    duplicate placements of the same region, caps `MAX_FIGURES_PER_PAGE=12` /
    `MAX_FIGURES_PER_JOB=200`; crops at `CROP_DPI=150`. Deterministic ids/filenames
    (`s{src:02d}_page_{NNNN}_figure_{MM}`).
  - `pipeline/visual_assets_manifest.py` — `build_/write_visual_assets_manifest(... ,
    extracted_assets=None)`; the manifest **re-sanitises every extracted record
    field-by-field** (asset-id slug, `extracted_figure` type, finite/ordered `bbox`,
    strict `^assets/[A-Za-z0-9_]+\.png$` `image_ref`, whitelisted numeric `signals`) so the
    **manifest — not the fitz extractor — stays the security boundary** and cannot be
    poisoned. Summary gains `extracted_figure_count`. **Stays fitz-free / pure.**
  - `pipeline/job_manager.py` — new `Job.assets_dir` (`<job>/assets`), advisory, not in
    exports / `ARTIFACTS` / DTOs.
  - `pipeline/run_llm_job.py` — tracks saved PDF path + page set in lockstep with
    extraction-metadata sources; `_extract_local_figures(job, pdf_inputs)` runs the gated
    extractor and passes results to the manifest writer (off-by-default → no-op).
  - `test_scripts/test_local_figure_extraction.py` (new) — 59 checks: pure
    re-sanitisation (bbox validity, id slugging, safe relative refs, leak prevention,
    backward-compat) + real-fitz crops (file existence, in-page bbox, tiny/duplicate
    collapse, per-page cap, determinism).
- **Validation (green):** `python -m compileall api pipeline` OK; `git diff --check` clean;
  `test_local_figure_extraction.py` **50/0 host (2 fitz cases skip) → 59/0/0 in Docker**;
  `test_visual_assets_manifest.py` **65/0** (backward-compatible); fresh
  `docker compose build` + `up --force-recreate`; `/api/health` `{"ok":true}`;
  `smoke_release.py` **29/0/0** on live :8000 (default flag-off ⇒ guide output unchanged).
- **Next:** Slice 41 — dedup + decorative filtering (V2, perceptual-hash `dedupe_group`),
  then Slice 42 candidate scoring (V3). Chandra GGUF spike runs shortly after (not in
  parallel with this slice's validation).

---

## Slice 39 — Chandra local feasibility verification (COMMITTED `7b97146`, merged to `chrome-renderer-v1`).

- **Purpose:** the **Chandra equivalent of Slice 35's Mistral gate** — a docs-only
  feasibility verification of **Chandra (Datalab)** as a future **high-quality local**
  OCR / document-extraction / visual-asset provider (`chandra_local`) for the
  Local/Private mode. **No** install, run, clone, build, weight download, dependency,
  provider code, API route, setting, key, prompt, routing, extraction, render, or
  `visual_assets_manifest.json` schema change. Chandra was **not** installed or run;
  facts come from official Datalab sources (GitHub repo, HF model cards, `MODEL_LICENSE`)
  checked **June 2026**.
- **Deliverable:** new **`docs/CHANDRA_OCR_VERIFICATION.md`** (§0–§12): which artifact
  is which (Chandra 1 `datalab-to/chandra` 9B vs **Chandra 2 `datalab-to/chandra-ocr-2`
  ~4B, the target**), product status/maintainer, capabilities (official vs
  reported-but-unverified), GuideForge integration shape (maps into the **Slice 38**
  manifest; modeled as OCR + document + visual-asset provider; sits behind the Slice 32
  contract for text + a future manifest-feeding extraction path; powers the Slice 37
  `local_private` mode; coexists with `tesseract_local`/`fitz_local`/`mistral_ocr`),
  **hardware feasibility on RTX 5070 Ti 16 GB**, operational complexity (heavy CUDA/vLLM
  GPU service; best fit = LMM host-companion pattern but heavier than the GGUF case),
  **license** (Apache-2.0 code + **modified OpenRAIL-M weights**), cost/privacy,
  hands-on spike plan, risks/unknowns, sources, recommendation, next slice.
- **Key verified facts:** Chandra **2** (released **3/2026**), `datalab-to/chandra-ocr-2`,
  pip `chandra-ocr`, vLLM (recommended) or HF transformers; **olmOCR 85.9**; outputs
  **MD/HTML/JSON with detailed layout info**, image+diagram extraction **with captions
  + structured data**, tables/math/forms/handwriting/multi-column, 90+ languages.
  **Throughput: 1.44 pages/s on H100 80 GB @96 concurrency (~2 pages/s real-world est.)**
  — expect **much less** on a 16 GB consumer GPU.
- **PATCHED with GGUF evidence (the feasibility-changing update):** a community
  **`prithivMLmods/chandra-ocr-2-GGUF`** conversion exists, reporting **5B params /
  `qwen35`** and a quant ladder (**Q4_K_M ≈ 3.07 GB · Q5_K_M ≈ 3.51 GB · Q6_K ≈ 3.99 GB ·
  Q8_0 ≈ 5.16 GB · BF16/F16 ≈ 9.7 GB**) + separate **`mmproj` ≈ 367–676 MB** — **community
  GGUF evidence, not the official `datalab-to` distribution** (a community quant may
  lag/diverge; re-verify before the spike). Consequences recorded in the doc:
  - **Param count is no longer stated as "4B official":** secondary ~4B vs GGUF-card 5B/
    `qwen35`, none pinned on the official card → **re-verify at spike time.**
  - **Hardware verdict revised** from `uncertain-but-promising` to **GGUF-quantized
    Chandra OCR 2 likely feasible on the RTX 5070 Ti 16 GB (esp. Q4/Q5/Q8); VRAM is
    likely not the main blocker.** Real blockers are now **multimodal `llama.cpp`
    support, `mmproj` loading, OCR quality, throughput, long-document behavior, and
    integration stability.** Throughput caveat kept: a 500–2,000-page deck may still be
    slow on one consumer GPU.
  - **Integration reframed into two paths:** **official** = vLLM / HF Transformers via
    Chandra CLI/server; **practical first spike** = GGUF through the **existing
    `llama.cpp`/`llama-server`/Local Model Manager** pattern — which **could avoid a
    brand-new companion/service** if multimodal `llama-server` works. **First hands-on
    checkpoint:** *can current `llama-server` load Chandra GGUF + `mmproj` and do
    image/PDF-page → markdown OCR?*
- **License conclusion unchanged:** code Apache-2.0; weights "AI PUBS OPEN RAIL-M
  (MODIFIED)" — free for research/personal/startups < $2M revenue OR funding, no competing
  with Datalab's OCR API ⇒ **fine for personal/single-operator; multi-user/commercial
  needs Datalab license review** (non-legal guidance).
- **Honest correction to roadmap §6:** the rich Mermaid / chart-data / LaTeX / per-block
  bbox / typed-block claims are **reported / implied by "JSON with layout info" but NOT
  itemized on the official card/README** — flagged for confirmation against the real
  output in the hands-on spike (the GGUF path may emit a different format).
- **Recommendation (revised):** **`Proceed to hands-on GGUF spike after manifest schema`**
  (manifest schema already shipped in Slice 38) — **with an explicit license caveat for
  multi-user / commercial use. Still NOT approval to implement Chandra as a provider.**
  The spike tests: model load · `mmproj` availability/loading · image input through
  `llama-server` · output-format quality · **Q4_K_M / Q5_K_M / Q8_0 comparison** ·
  pages/minute · VRAM/RAM · fallback behavior · mapping output into
  `visual_assets_manifest.json`.
- **Proposed next:** continue the **local** visual stack first (Slice 40 fitz figure
  extraction/cropping into the manifest → V2 dedup → V3 candidate scoring — no GPU / no
  license question), then run the **Chandra 2 GGUF spike shortly *after* Slice 40 (NOT in
  parallel with Slice 40 validation** — GPU/`llama-server` noise would disturb the fresh
  extraction smoke), GGUF/`llama-server` first against a known-good reference, to gate
  whether `chandra_local` becomes a real provider and whether it can reuse the existing
  LMM `llama-server` path; only then a disabled/unwired `chandra_local` provider-design
  slice. **Visual measurement is staged:** Slice 40 only writes manifest/assets (test
  asset existence/bbox/ids/refs/caps/dup-explosion); `{{figure}}` orphan/coverage tests
  come **after** the asset-aware prompt/render slices.
- **Files (docs only):** `docs/CHANDRA_OCR_VERIFICATION.md` (new), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `git status --short`, `git diff --check` clean, `git diff --name-only`
  docs-only (no build/smoke required — no code touched). **Do not commit Slice 39 yet**
  unless directed.

---

## Slice 38 — Visual assets manifest schema from existing signals (COMMITTED `8a788c7`, merged to `chrome-renderer-v1`).

- **Purpose:** add the first **provider-agnostic** `visual_assets_manifest.json`
  advisory artifact — the **normalization boundary** Slice 36 called for — populated
  **only** from existing page-level visual/page signals already collected for
  `extraction_metadata.json` (Slice 30/31/34). This is a **schema/advisory-artifact**
  slice, **not** an image-extraction slice.
- **Deliverable:** new `pipeline/visual_assets_manifest.py` — a stdlib-only module
  (`json` + `typing`, **no** `fitz`/Tesseract/Mistral/Gemini/Chandra/`ocr_provider`
  imports) with:
  - **Pure builder** `build_visual_assets_manifest(sources) -> dict` — takes the
    same already-sanitized extraction-metadata source records persisted in
    `extraction_metadata.json` and returns the manifest dict. Pure & total: never
    raises, never opens a PDF, never crops, never calls a provider; degrades to an
    empty-but-valid manifest on any bad input.
  - **Wrapped writers** `write_visual_assets_manifest(job, sources)` (advisory,
    never raises, degrades to a `skipped` artifact on write failure) and
    `write_skipped_visual_assets_manifest(job, ...)`.
- **Manifest top-level shape:** `{version:1, kind:"visual_assets_manifest",
  status:"completed", source:"extraction_metadata.json", assets:[...],
  summary:{asset_count, pages_with_visual_signals, source_providers:[...]},
  warnings:[]}`.
- **Asset record (page-level visual *candidate*):** `{asset_id:"page_NNNN_visual_01",
  source_page, asset_type:"page_visual_signal", bbox:null, caption:null,
  source_provider:"fitz_local", recommended_action:"unknown", dedupe_group:null,
  scores:{}, signals:{image_object_count, drawing_object_count, has_images,
  has_drawings, page_width, page_height, classification, ocr_route_action},
  warnings:[]}`. One candidate is emitted **per page** that carries a positive image
  OR drawing signal; a page with **both** yields exactly **one** candidate (its
  `signals` records both).
- **Because nothing is cropped, each asset is a page-level visual *candidate***
  ("this page has a visual signal worth a closer look later"), **not** a real
  extracted figure. `bbox` is always `null` this slice.
- **Closed vocabulary, leak-free:** `source_provider` only ever `fitz_local`
  (future-reserved `chandra_local`/`mistral_ocr`/`vlm_*` documented but **not**
  emitted); `asset_type` only `page_visual_signal`; `recommended_action` only
  `unknown` (no scoring yet); `classification`/`ocr_route_action` coerced to closed
  Slice 31/34 vocab; dimensions/counts coerced numerically. Every field is a fixed
  token / int / float / `None` / empty dict / deterministic `asset_id` — inputs are
  coerced field-by-field and **never echoed**, so no raw path, host path, image byte,
  raw PDF object, provider payload, OCR error, key/token/header, URL, socket, or argv
  can survive even from a smuggled record.
- **Persistence convention (smallest approach):** the manifest is **derived from
  `extraction_metadata.json`** and is written **exactly when those PDF sources
  exist** — wired in `run_llm_job.py` immediately after
  `write_extraction_metadata(...)`. Non-PDF jobs / unavailable metadata **omit** the
  artifact entirely (matching how non-applicable artifacts are handled). A page set
  with zero visual signals still writes a valid `completed` manifest with an empty
  `assets` list.
- **Access:** exact-name download via the existing
  `/api/jobs/{id}/artifacts/visual_assets_manifest.json` route (one `_artifact_path`
  entry + a `Job.visual_assets_manifest_json` property). **Not** added to the generic
  `ARTIFACTS` list, `_artifact_urls`/`_artifact_details`, export bundles, or any
  frontend tab — same posture as `math_verification.json` / `guide_lint.json` /
  `extraction_metadata.json`.
- **No API route added/changed** beyond the exact-name `_artifact_path` mapping (no
  new endpoint). **No** extraction/text/OCR/routing/prompt/render change; guide text
  and `clean.md` are byte-identical when this feature is unused (it only writes one
  sibling JSON).
- **Out of scope (later slices):** local figure extraction/cropping, dedup,
  decorative filtering, candidate scoring/text replacement, Chandra verification,
  Mistral skeleton, Gemini/VLM, any external API, UI, export-bundle wiring.
- **Files:** `pipeline/visual_assets_manifest.py` (new),
  `test_scripts/test_visual_assets_manifest.py` (new, 65 checks — pure builder +
  integration), `pipeline/job_manager.py` (+`visual_assets_manifest_json` property),
  `api/server.py` (+exact-name `_artifact_path` entry), `pipeline/run_llm_job.py`
  (+wrapped writer call), docs.
- **Validation (all green):** `test_visual_assets_manifest` 65/65, `compileall`,
  fresh Docker rebuild + `--force-recreate`, `/api/health` 200, `smoke_release.py`
  **29 passed / 0 failed / 0 skipped** on live :8000, exact-name route confirmed wired
  (`visual_assets_manifest.json` → graceful 404 on a non-PDF job, `clean.md` → 200),
  `git diff --check` clean. **Committed `8a788c7`, fast-forward merged to
  `chrome-renderer-v1`, pushed.**

---

## Slice 37 — OCR/extraction mode + cost/budget skeleton (COMMITTED `9fbbb1d`, merged to `chrome-renderer-v1`).

- **Purpose:** add a **pure, provider-agnostic** mode + cost/budget *framework*
  that later visual-manifest and cloud/Chandra provider slices can plug into —
  **without** changing any behavior. Framework/skeleton only; **no provider is
  implemented, no cloud call is made, cloud OCR stays disabled by default.**
- **Deliverable:** new `pipeline/ocr_modes.py` — a stdlib-only module
  (`dataclasses` + `typing`, **no** `fitz`/Tesseract/`ocr_provider`/cloud SDK
  imports) defining:
  - **Modes** (Slice 36 vocab): `local_private` (default) · `smart_cloud_assist`
    · `maximum_fidelity`.
  - **Provider roles:** `local_ocr_provider` · `cloud_document_provider` ·
    `cloud_vision_provider`. **Provider ids:** `tesseract_local` (impl today) ·
    `chandra_local` · `mistral_ocr` (future; naming them wires nothing).
  - **DTOs:** `OcrModeSettings` (mode, `cloud_opt_in`, `local_ocr_available`,
    `page_cap`, `dollar_cap`, `selected_page_count`) · `OcrBudget` ·
    `OcrProviderPricing` · `OcrCostEstimate` (mode, provider id/role, billing
    unit, billed pages, `estimated_cost_usd`, `currency:"USD"`, `is_estimate`,
    `status`, `price_source`, closed-vocab `warnings`).
  - **Functions:** `default_ocr_mode_settings()` · `resolve_ocr_mode_config()` ·
    `ocr_budget()` · `provider_pricing()` · `estimate_ocr_cost()` ·
    `safe_ocr_mode_settings_dict()` · `safe_ocr_cost_estimate_dict()` ·
    `ocr_provider_pricing_snapshot()`.
- **Mapping to Slice 33 routing:** `resolve_ocr_mode_config(settings)` returns the
  exact `pipeline.ocr_routing.default_config()` shape (`allow_cloud_ocr`,
  `local_ocr_available`, `max_ocr_pages`, `page_budget_remaining`) plus an
  advisory `mode` echo the routing core ignores. **Default mode `local_private`
  ⇒ `allow_cloud_ocr=False`.** `allow_cloud_ocr` is `True` **only** when the mode
  is cloud-capable **AND** `cloud_opt_in is True` (a real bool — truthy strings
  are rejected). A mode name alone never enables cloud; even when allowed, the
  Slice 33 policy only returns an *advisory* `cloud_ocr_candidate` — no cloud OCR
  is wired into extraction.
- **Cost skeleton:** static, documented price snapshot only (no network).
  `mistral_ocr` = **per page, ~$2/1,000 (standard) / ~$1/1,000 (batch),
  `is_estimate:true`, `price_source:"docs/MISTRAL_OCR_VERIFICATION.md"` (June 2026
  estimate, re-verify before any billing UI)**. Local providers are free/exact.
  Unknown providers ⇒ safe `status:"unavailable"/"unknown"`. 500 pages on
  `smart_cloud_assist` ⇒ advisory `$1.00`, `is_estimate:true`, page/dollar caps
  applied as advisory warnings.
- **Leak-safety:** every output field is a closed-vocab token / int / float /
  `None` / `"USD"` / the repo-relative `price_source`; hostile keys (api_key,
  base_url, authorization, host/socket path, argv) are dropped, never echoed.
- **No API route added or changed; no frontend.** Not wired into extraction,
  routing, prompts, `/api/jobs/llm` fields, Ask/retrieval, render, artifacts,
  exports, or `extraction_metadata.json`/manifest schemas.
- **Files changed:** `pipeline/ocr_modes.py` (new),
  `test_scripts/test_ocr_modes.py` (new, 121 checks), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** frontend build + `npm run test` green · `compileall api
  pipeline test_scripts` clean · full backend OCR/eval/lint/ask suite green ·
  `test_ocr_modes.py` 121/121 · eval `--offline --all` no regression ·
  `git diff --check` clean · `smoke_release.py` green (live :8000).
- **Proposed next:** `visual_assets_manifest.json` normalization-boundary skeleton
  (still no provider/extraction change), per `docs/VISION_ROADMAP.md`.

---

## Slice 36 — Revised visual / cost / provider-strategy roadmap (COMMITTED + MERGED to `chrome-renderer-v1`, commit `976aebc`).

- **Purpose:** capture the operator's revised long-range vision as a **planning
  doc**, before any visual-asset or cloud-OCR code. **Implements nothing** — no
  code, dependency, provider setting, key, prompt, routing, extraction, schema,
  or render change; no external OCR/vision API (Mistral / Gemini / Chandra) was
  called.
- **Deliverable:** new `docs/VISION_ROADMAP.md` covering: planning-status caveats
  (repo is source of truth; re-verify every provider fact at impl time); the
  **Capture → Explain → Show → Trust → Retain** north star; current gap analysis
  (Explain strong, Capture text-only, Show unbuilt, Trust partial, cost/privacy
  primitive); the **three-mode** strategy (Local/Private default · Smart Cloud
  Assist · Maximum Fidelity); the **provider-agnostic `visual_assets_manifest.json`
  normalization boundary** (sources `fitz_local` / `chandra_local` / `mistral_ocr`
  / future `vlm_*`; closed-vocab asset records: `asset_id`, `source_page`,
  `asset_type`, `bbox`, `caption`, `source_provider`, `recommended_action`,
  `dedupe_group`, `scores`; no raw paths/keys/URLs/payloads); provider roles;
  **Chandra framing** (near-roadmap high-quality *local* mode, license caveat,
  **not** production-approved until docs slice + RTX 5070 Ti hands-on spike);
  privacy-as-disclosure/consent (not a hard blocker); the **dependency-ordered
  visual stack V1–V7** (render-embed late/high-risk); the **OCR-classification vs
  visual-candidate-scoring** separation; a **proposed** Slice 37–43 order; and the
  carried slice principles.
- **Key reframing:** this **resequences (does not cancel)** the old
  `HYBRID_OCR_DESIGN.md` §9 "Slice 36 = Mistral provider" item — the Mistral
  provider skeleton is now **proposed Slice 43** (disabled/unwired), so the
  provider-agnostic mode/budget + visual-manifest layer can land first.
- **Mistral kept on the near map** as a visual/table enabler (likely first cloud
  document-extraction provider), **not shelved**; **Chandra captured** as the
  near-roadmap high-quality *local* option that could make Local/Private mode
  high quality for GPU users (still gated).
- **Proposed next:** **Slice 37 — provider-agnostic OCR/extraction mode +
  cost/budget skeleton** (framework only; no provider wired, no cloud call).
- **Files changed (docs only):** `docs/VISION_ROADMAP.md` (new),
  `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`,
  `docs/ROADMAP_INPUT_SUMMARY.md`, `docs/DECISIONS.md`.
- **Validation:** `git diff --name-only` shows docs only · `git diff --check`
  clean · no build/smoke needed (no code touched).
- **Note on numbering:** Slices 37–43 in `docs/VISION_ROADMAP.md` are **proposed
  future work, not completed** — do not treat them as existing.

---

## Slice 35 — Mistral OCR prerequisite verification (COMMITTED + MERGED to `chrome-renderer-v1`, commit `45a54d2`).

- **Purpose:** prerequisite **gate** before *any* cloud-OCR code. Verify whether
  **Mistral OCR / Document AI** is safe and suitable as a future cloud OCR provider,
  from official Mistral sources. **Implements nothing** — no code, dependency,
  provider setting, key, prompt, routing, extraction, or schema change. No Mistral
  API was called with any document.
- **Deliverable:** new `docs/MISTRAL_OCR_VERIFICATION.md` covering product status,
  request/response format, pricing, rate limits, privacy/data-handling, fit with the
  Slice 32 boundary + Slice 33/34 routing, implementation risks, unknowns, sources,
  and a recommendation.
- **Key facts verified (June 2026, re-confirm at impl time):** GA & versioned —
  original Mistral OCR plus **Mistral OCR 3** (`mistral-ocr-2512`, GA 2025-12-17);
  `mistral-ocr-latest` alias. Endpoint `POST https://api.mistral.ai/v1/ocr`
  (SDK `client.ocr.process`). Inputs: PDF/PPTX/DOCX or image via public URL, base64,
  or uploaded file id; **≤ 50 MB, ≤ 1,000 pages**; Batch API (async, −50%). Output:
  **per-page Markdown** + tables (md/HTML) + images + dimensions + optional
  confidence scores. Pricing **per page** (~$1/1,000 original, ~$2/1,000 OCR 3;
  half via batch). Rate limits per API key (RPS/TPM/monthly, tiered). Privacy: API
  data **not used for training**; default **30-day** abuse-retention unless **ZDR**
  (Scale plan, stateless calls only); self-host option for sensitive orgs.
- **Architecture fit:** **no blockers** — Slice 32 `OcrProvider`/`OcrResult` boundary,
  Slice 33 `cloud_ocr_candidate`/`allow_cloud_ocr`/shared budget, and Slice 34
  advisory `ocr_route_*` recorder already provide the exact seams. A future
  `MistralCloudOcrProvider` plugs into the Slice 32 contract; routing flips the
  Slice 33 candidate into a real dispatch only under explicit opt-in, page-budgeted,
  with mandatory local-Tesseract fallback. Key/`Authorization`/raw provider
  errors/URLs/doc paths stay **server-side only** (provider-settings DTO posture).
- **Recommendation:** **Proceed only after the operator confirms pricing and
  privacy**, then implement strictly behind an explicit, off-by-default opt-in. The
  gating concerns are **policy** (confirm live per-page price; accept third-party
  processing of student notes with default 30-day retention, mitigable via opt-in +
  ZDR + no public URLs), **not** technical. **Not** a green light to route real
  documents through Mistral yet.
- **Proposed next:** **Slice 36 — Mistral OCR provider skeleton / OCR provider-settings
  + key-storage design, disabled by default** (no network to generation).
- **Files changed (docs only):** `docs/MISTRAL_OCR_VERIFICATION.md` (new),
  `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `git diff --name-only` shows docs only · `git diff --check` clean ·
  no build/smoke needed (no code touched).
- **Note on prior position:** trunk HEAD is now **Slice 34 committed**
  (`25e3fd3`), not the uncommitted state the older handoff text below describes.

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
