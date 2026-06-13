# VISUAL_PILOT_OPERATOR_VALIDATION.md — Slice 59 manual operator validation runbook

> **This is a manual validation harness / runbook, not production behavior.** It adds
> NO production code and changes nothing in the app. It only *drives* the existing
> pipeline so an operator can validate the **current single-figure visual pilot**
> against a real, **non-private** sample PDF when one is available.

Harness: `test_scripts/validate_visual_pilot_operator_sample.py`.

---

## Why this slice exists

Slice 58 proved the stitched single-figure path end-to-end with **synthetic** temp
data (`docs/VISUAL_PILOT_E2E_VALIDATION.md`). The next gate before any visual
expansion is a **real** non-private operator sample run through the same path. This
slice provides a safe, repeatable, opt-in tool for that, plus a synthetic `--self-test`
mode so the harness itself can be exercised in CI / on a host with no operator PDF.

Multi-figure expansion and Chandra integration stay deferred until a real operator
validation pass is recorded against the current single-figure pilot.

---

## Opt-in and privacy policy

- **Opt-in only.** The harness refuses to run without `--pdf` (unless `--self-test`).
- **Non-private material only.** Never run *recorded* validation on student / private /
  confidential documents. The harness prints this warning on every operator run.
- **The harness never prints or records** the PDF path, basename, filename, document
  text, OCR text, image bytes, base64, data URIs, full URLs, tokens, model / mmproj /
  executable paths, or raw argv. Output is a fixed closed-vocabulary summary plus
  closed-vocab step markers; a final no-leak sweep scans every pipeline-derived string.
- **Exceptions are sanitized** to closed `failure_category` tokens — only an exception
  *type name* is ever surfaced, never a message that could carry a path or private text.
- **All working files** live under a temp/output directory; **nothing is committed**
  (no PDF/image/DOCX/ZIP fixtures, no synthetic artifacts in the repo tree).

---

## Safe command template (placeholders only)

```bash
# Synthetic dry run — verifies harness schema + no-leak, no operator PDF needed:
python test_scripts/validate_visual_pilot_operator_sample.py --self-test

# Real operator run — supply a NON-PRIVATE sample (path is never printed/recorded):
python test_scripts/validate_visual_pilot_operator_sample.py \
  --pdf "<non-private-sample.pdf>" \
  --output-dir "<temp-output-dir>"
```

> Do **not** paste a real command with a real path into docs or chat. Do **not** record
> the filename, the extracted text, image bytes, or raw exceptions. Record only the
> sanitized closed-vocabulary summary fields below.

For the full single-figure path inside the lean container (PyMuPDF / Chromium /
python-docx / FastAPI all present), copy the harness to `/tmp`, run, and remove it —
never bake it into the production image, never run `docker compose config`.

---

## Safe output policy — closed-vocabulary summary fields

The harness emits exactly these ten fields (and nothing else of substance):

| field | values |
| --- | --- |
| `status` | `ok` · `skipped` · `failed` |
| `pilot_inserted` | `true` · `false` |
| `safe_asset_ref_present` | `true` · `false` |
| `html_render_ok` | `true` · `false` · `null` (skipped) |
| `pdf_render_ok` | `true` · `false` · `null` (skipped) |
| `docx_render_ok` | `true` · `false` · `null` (skipped) |
| `export_zip_ok` | `true` · `false` · `null` (skipped) |
| `export_png_included` | `true` · `false` · `null` (skipped) |
| `warnings` | closed-vocab list (see below) |
| `failure_category` | closed-vocab token (see below) |

**`failure_category` vocabulary:** `none` · `pdf_unreadable` ·
`extraction_dependency_unavailable` · `no_safe_figure_found` · `insertion_failed` ·
`render_failed` · `export_failed` · `harness_error`.

**`warnings` vocabulary:** `no_extracted_figure` · `extraction_dependency_unavailable` ·
`html_render_skipped_no_dependency` · `pdf_render_skipped_no_chromium` ·
`docx_render_skipped_no_dependency` · `export_skipped_no_fastapi` ·
`multiple_figures_present_one_inserted`.

When a host/container dependency (PyMuPDF, Chromium, python-docx, FastAPI) is missing,
the relevant stage **skips calmly** with a closed-vocab token rather than failing.

---

## What it validates (single-figure path, unchanged)

On a real PDF the harness runs the genuine pipeline: `extract_local_figures`
(`fitz_local` only) → `write_visual_assets_manifest` → `write_visual_asset_scoring_report`
→ `write_visual_replacement_plan_report` → `apply_visual_markdown_pilot` (both gates on,
written via `save_clean_md`) → HTML/PDF/DOCX render → `export_bundle`. It confirms **at
most one** `extracted_figure` is inserted, the ref is exactly `assets/<slug>.png`, the
renderers resolve the relative ref, and the export ZIP carries exactly the single
referenced PNG with a safe relative bundle-index ref.

`--self-test` exercises the same insertion/render/export + summary code on synthetic
non-private temp data (a runtime stdlib-built PNG and a synthetic manifest), then asserts
the summary schema, closed-vocab values, and no-leak behavior. It does **not** pretend to
be a real operator PDF validation.

---

## Current recorded status

```
manual_operator_pdf_validation: run
status: ok
pilot_inserted: true
safe_asset_ref_present: true
html_render_ok: true
pdf_render_ok: true
docx_render_ok: true
export_zip_ok: true
export_png_included: true
warnings:
  - multiple_figures_present_one_inserted
failure_category: none
no_leak_sweep: clean
```

### Interpretation

- The manual harness was run on **one real, non-private, operator-supplied PDF**.
- The current `fitz_local` single-figure pilot found **one or more** figure candidates.
- The pilot inserted **exactly one** figure, preserving the current one-figure rule.
- **HTML, PDF, DOCX, export ZIP, and referenced PNG inclusion** all validated successfully.
- The warning `multiple_figures_present_one_inserted` is **expected** and confirms the
  current design rule was obeyed (multiple candidates present, only one inserted).
- This **clears the current single-figure visual-pilot operator-validation gate.**
- It does **not** clear the Chandra live-validation gate.
- It does **not** approve multi-figure insertion yet.

Only the sanitized closed-vocabulary summary above was recorded. No real PDF path,
filename, document text, OCR text, image bytes, base64, data URI, full URL, raw argv,
token, or raw exception was recorded.

- **Chandra extraction integration remains blocked by Slice 45 `status:not_run`.**
- **Multi-figure expansion remains deferred**; the single-figure operator validation pass
  is now recorded, but multi-figure insertion stays out of scope until separately designed.

---

## Slice 75 — diverse visual-pilot exit validation (not run)

> Docs/validation-record only. **No production code, frontend, export, extraction/OCR
> routing, prompt, render, caption, ranking, classification, cap, or selection behavior
> changed.** This slice is an exit-decision checkpoint for the default-off visual markdown
> pilot, not another visual-polish or table/diagram morphology slice.

Slice 74 was the final in-lab caption/source-page polish slice. The morphology loop remains
paused after Slice 73's real-sample success, the caption micro-loop is not starting, and
Chandra remains blocked by its own live-validation gate.

### Availability result

```
diverse_visual_pilot_exit_validation: not_run
reason: non_private_diverse_samples_not_available
```

An operator-local sample count was present, but no safe manual category mapping was
available for the requested diverse validation categories. A sample count alone is not a
category assignment, and this slice explicitly forbids guessing categories from local PDFs.
No harness run was performed, no runtime trace/render/export artifacts were produced, and
no sample path or filename was recorded.

### Per-category sanitized records

Each target category below was unavailable for this slice because no manually mapped
non-private sample was provided.

```text
category: math_heavy_deck
status: skipped
skip_reason: sample_not_available
trace_artifact_present: not_applicable
trace_no_leak_sweep: not_applicable
effective_max_images: not_applicable
inserted_visual_count: 0
safe_candidate_count: 0
unsafe_candidate_count: 0
selected_count: 0
type_counts:
  diagram_or_figure: 0
  reconstructable_table: 0
  unknown: 0
  decorative_or_low_information: 0
selected_visual_type: none_inserted
irreplaceable_visual_selected: not_applicable
selected_figures_quality: none_inserted
caption_status: not_applicable
graceful_omission: not_applicable
pdf_render_ok: not_applicable
pdf_image_visible: not_applicable
docx_render_ok: not_applicable
export_zip_ok: not_applicable
export_png_included: not_applicable
warnings:
  - sample_unavailable
failure_category: sample_unavailable
no_leak_sweep: clean

category: mostly_text_only_pdf
status: skipped
skip_reason: sample_not_available
trace_artifact_present: not_applicable
trace_no_leak_sweep: not_applicable
effective_max_images: not_applicable
inserted_visual_count: 0
safe_candidate_count: 0
unsafe_candidate_count: 0
selected_count: 0
type_counts:
  diagram_or_figure: 0
  reconstructable_table: 0
  unknown: 0
  decorative_or_low_information: 0
selected_visual_type: none_inserted
irreplaceable_visual_selected: not_applicable
selected_figures_quality: none_inserted
caption_status: not_applicable
graceful_omission: not_applicable
pdf_render_ok: not_applicable
pdf_image_visible: not_applicable
docx_render_ok: not_applicable
export_zip_ok: not_applicable
export_png_included: not_applicable
warnings:
  - sample_unavailable
failure_category: sample_unavailable
no_leak_sweep: clean

category: low_quality_or_scan_like_pdf
status: skipped
skip_reason: sample_not_available
trace_artifact_present: not_applicable
trace_no_leak_sweep: not_applicable
effective_max_images: not_applicable
inserted_visual_count: 0
safe_candidate_count: 0
unsafe_candidate_count: 0
selected_count: 0
type_counts:
  diagram_or_figure: 0
  reconstructable_table: 0
  unknown: 0
  decorative_or_low_information: 0
selected_visual_type: none_inserted
irreplaceable_visual_selected: not_applicable
selected_figures_quality: none_inserted
caption_status: not_applicable
graceful_omission: not_applicable
pdf_render_ok: not_applicable
pdf_image_visible: not_applicable
docx_render_ok: not_applicable
export_zip_ok: not_applicable
export_png_included: not_applicable
warnings:
  - sample_unavailable
failure_category: sample_unavailable
no_leak_sweep: clean

category: mixed_diagrams_tables_deck
status: skipped
skip_reason: sample_not_available
trace_artifact_present: not_applicable
trace_no_leak_sweep: not_applicable
effective_max_images: not_applicable
inserted_visual_count: 0
safe_candidate_count: 0
unsafe_candidate_count: 0
selected_count: 0
type_counts:
  diagram_or_figure: 0
  reconstructable_table: 0
  unknown: 0
  decorative_or_low_information: 0
selected_visual_type: none_inserted
irreplaceable_visual_selected: not_applicable
selected_figures_quality: none_inserted
caption_status: not_applicable
graceful_omission: not_applicable
pdf_render_ok: not_applicable
pdf_image_visible: not_applicable
docx_render_ok: not_applicable
export_zip_ok: not_applicable
export_png_included: not_applicable
warnings:
  - sample_unavailable
failure_category: sample_unavailable
no_leak_sweep: clean

category: no_good_figures_deck
status: skipped
skip_reason: sample_not_available
trace_artifact_present: not_applicable
trace_no_leak_sweep: not_applicable
effective_max_images: not_applicable
inserted_visual_count: 0
safe_candidate_count: 0
unsafe_candidate_count: 0
selected_count: 0
type_counts:
  diagram_or_figure: 0
  reconstructable_table: 0
  unknown: 0
  decorative_or_low_information: 0
selected_visual_type: none_inserted
irreplaceable_visual_selected: not_applicable
selected_figures_quality: none_inserted
caption_status: not_applicable
graceful_omission: not_applicable
pdf_render_ok: not_applicable
pdf_image_visible: not_applicable
docx_render_ok: not_applicable
export_zip_ok: not_applicable
export_png_included: not_applicable
warnings:
  - sample_unavailable
failure_category: sample_unavailable
no_leak_sweep: clean
```

### Aggregate exit record

```text
diverse_visual_pilot_exit_validation: not_run
validated_category_count: 0
available_category_count: 0
pilot_inserted_count: 0
graceful_omission_count: 0
bad_selection_count: 0
caption_safe_count: 0
pdf_image_visible_count: 0
docx_render_ok_count: 0
export_png_included_count: 0
no_leak_sweep: clean
exit_recommendation: insufficient_evidence
exit_reason: diverse_validation_insufficient_sample_count
```

### Decision

The current evidence is insufficient to make the visual markdown pilot more discoverable.
Keep it default-off / opt-in until multiple known non-private samples are manually mapped
to closed categories and validated without changing visual behavior. Do not resume the
caption micro-loop or table/diagram morphology loop from this result.

Only sanitized closed-vocabulary and bounded numeric fields were recorded. No real PDF
path, filename, document text, OCR text, source caption/table text, image bytes, base64,
data URI, full URL, provider payload, token, raw argv, model/mmproj/executable path, or
raw exception was recorded.

---

## Slice 61 — post-fix operator visual-quality review (decision gate)

> Docs/validation-record only. **No production code, frontend, export, extraction/OCR
> routing, prompt, or render behavior changed.** This records a sanitized **post-fix**
> human quality review of the single figure the pilot selects **after** the Slice 60
> quality gate, run against the same non-private operator sample through the freshly
> rebuilt Slice 60 container. It is the decision gate for whether the next visual step
> is multi-figure / improved placement or continued selection-quality work.

### Why this review exists

Slice 59 (real operator run) and Slice 60 proved the **visual plumbing and the
`fitz_local` extraction source are viable** — figures extract, one is inserted, and the
embedded image is now actually visible in the rendered PDF. The remaining open question
was purely **human**: is the figure the pilot now picks actually *worth* showing? The
pre-fix selection picked a **low-value chapter-title / title-page crop**. Slice 60 added
deterministic quality gating (drop decorative chrome, prefer content figures) **and**
fixed the harness PDF layout so the embedded image renders. This slice records the
operator's post-fix verdict on the selected figure.

### Post-fix review — recorded result (sanitized, closed vocab)

```
postfix_operator_visual_quality_review: run
status: ok
pilot_inserted: true
selected_figure_quality: useful_diagram_or_table
pdf_render_ok: true
pdf_image_visible: true
docx_render_ok: true
export_zip_ok: true
export_png_included: true
warnings:
  - multiple_figures_present_one_inserted
failure_category: none
no_leak_sweep: clean
```

The operator classified the post-fix selected figure using only the closed vocabulary
`useful_diagram_or_table` · `acceptable_but_not_best` · `decorative_or_low_information` ·
`wrong_or_bad_crop` · `unclear`, after inspecting the rendered PDF / HTML / DOCX from a
host output folder (the real sample path/filename and the figure's source contents are
**not** recorded here).

### Pre-fix review — preserved for comparison (Slice 60, sanitized)

```
operator_visual_quality_review: run
selected_figure_quality: decorative_or_low_information
extraction_candidate_quality: mostly_usable
crop_quality: mostly_good_some_label_loss
pdf_image_visible: false
docx_image_visible: true
failure_category: selection_quality_insufficient
no_leak_sweep: clean
```

### Interpretation

- Slice 59 / Slice 60 proved the **visual plumbing and the extraction source are viable**.
- The **pre-fix** selection picked a **low-value title / chapter crop**, and the pre-fix
  PDF check was a harness-layout artifact that showed only a broken-image placeholder.
- Slice 60 added **deterministic quality gating** (drop decorative chrome, prefer content
  figures) and **fixed the harness PDF layout** so the embedded image renders.
- The **post-fix operator review is the decision gate** for the next visual step.
- **Recorded verdict: `useful_diagram_or_table`.** This is in the
  `useful_diagram_or_table` / `acceptable_but_not_best` band, so **cautious multi-figure
  or improved placement may be considered next** — as a separately-designed slice, still
  one figure at a time until that slice is scoped.
- A `decorative_or_low_information`, `wrong_or_bad_crop`, or `unclear` verdict would
  instead have meant **keep improving selection quality before any multi-figure work**.
- **Chandra extraction integration remains blocked by its own live-validation gate**
  (Slice 45 `status:not_run`); this review does not touch it.
- Only the sanitized closed-vocabulary fields above were recorded — **no** real PDF path,
  filename, document text, OCR text, image bytes, base64, data URI, full URL, raw argv,
  token, model/mmproj/executable path, or raw exception.

---

## Slice 63 — cap-2 real operator validation (post-Slice-62 decision check)

> Validation-record slice. **No production pipeline/API/frontend code changed.** It adds
> NO visual behavior. It only *reran* the existing manual harness against the same real,
> **non-private** operator sample with the Slice 62 cap raised to `2`, to answer the one
> question Slice 62 left open: is the **cap-2 output actually useful**, or does the second
> figure drag quality down? One tiny safe harness correction was needed (below).

### Why this record exists

Slice 62 made the visual pilot able to insert **up to 2** figures (hard upper bound 2;
default still exactly 1), and validated that path **synthetically and in Docker**. What it
did **not** do was an optional **real** operator revalidation of the cap-2 output. Slice 63
closes that: same harness, same already-supplied non-private sample, run inside the rebuilt
container with `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`, then a human inspection of the
rendered PDF / HTML / DOCX copied to a host folder.

### Tiny safe harness correction (the only code touched)

`test_scripts/validate_visual_pilot_operator_sample.py` previously hard-coded the export
check to **exactly one** bundled PNG (`len(png_entries) == 1`), which was correct for the
single-figure pilot but reported `export_png_included: false` whenever the cap-2 path
legitimately bundled two referenced PNGs. The check now requires the bundled-PNG count to
equal the sanitized `inserted_visual_count` and stay within `1..2`, each still a safe
relative `assets/<slug>.png` ref. No production code, schema, or vocabulary changed; the
`--self-test` (default cap, one figure) stays green and still records `export_png_included:
true`.

### Cap-2 review — recorded result (sanitized, closed vocab)

```
cap2_operator_visual_quality_review: run
status: ok
pilot_inserted: true
inserted_visual_count: 2
selected_figures_quality: all_useful_or_acceptable
pdf_render_ok: true
pdf_image_visible: true
docx_render_ok: true
export_zip_ok: true
export_png_included: true
warnings:
  - multiple_figures_present_one_inserted
failure_category: none
no_leak_sweep: clean
```

The operator classified the cap-2 selected figures using only the closed vocabulary
`all_useful_or_acceptable` · `mixed_quality` · `decorative_or_bad_present` · `unclear`,
after inspecting the rendered PDF / HTML / DOCX from a host output folder (the real sample
path/filename and the figures' source contents are **not** recorded here).

### Operator-review nuance — visual *type* priority (sanitized, closed vocab)

The cap-2 plumbing passed, but the operator review surfaced one important nuance about the
**kind** of visual selected. Recorded with safe closed-vocabulary tokens:

```
selected_figures_quality: all_useful_or_acceptable
selected_visual_type: tables_only
irreplaceable_visual_selected: false
decision_gate: cap2_plumbing_passed_but_visual_type_priority_incomplete
next_recommended_slice: prefer_diagrams_over_reconstructable_tables
```

Both selected visuals were **important tables**, not diagrams/figures that are hard to
reconstruct. The point of the visual/OCR feature is not merely to embed *any* useful crop;
it is especially to preserve visuals an LLM **cannot reliably recreate** from extracted
text. Tables are frequently reconstructable from extracted text into clean generated tables,
so a table-only cap-2 result clears the pipeline gate but leaves the higher-value goal —
preserving truly irreplaceable visuals — only partially met.

> Note on the `multiple_figures_present_one_inserted` warning: it is the existing
> closed-vocabulary token, emitted whenever **the source held more than one figure
> candidate**. Under cap-2 its `_one_inserted` suffix is a slight legacy misnomer — two
> figures were inserted here — but the token's trigger condition is still literally true and
> the actual count is recorded unambiguously in `inserted_visual_count: 2`. Renaming a
> closed-vocab token is deliberately out of scope for a validation slice.

### Interpretation

- Slice 62 made **cap 2 available**, but the **default remains exactly 1**.
- This Slice 63 record checks whether the **cap-2 real output is actually useful**.
- **Slice 63 proves the cap-2 pipeline works on a real, non-private sample** —
  selection → capped multi-insertion → PDF/HTML/DOCX render → export bundle all functioned.
- **Recorded verdict: `all_useful_or_acceptable`** with **2 figures inserted** — both
  inserted figures were genuine content-bearing material from distinct source pages, not
  decorative title/header/footer/logo/banner crops, and both rendered visibly in the PDF and
  rode along in the export bundle.
- **However, both selected visuals were useful/acceptable *tables*** (`selected_visual_type:
  tables_only`, `irreplaceable_visual_selected: false`). Tables are often **reconstructable**
  from extracted text into clean generated tables, so a table is rarely the irreplaceable
  case the visual feature exists to protect.
- **The higher-value target for visual embedding** is diagrams, flowcharts, screenshots,
  labeled figures, network maps, and other visuals that **cannot be reliably recreated from
  text alone**.
- **Therefore the next visual slice should not be placement/UI polish yet.** The decision
  gate is `cap2_plumbing_passed_but_visual_type_priority_incomplete`: the plumbing is proven,
  but visual-*type* prioritization is not.
- **The next visual slice should improve visual-type ranking**
  (`next_recommended_slice: prefer_diagrams_over_reconstructable_tables`): prefer
  diagrams/figures over reconstructable tables when both are available, while still allowing
  tables when they are the best/only useful visual. **Do not expand beyond cap 2.** **Do not
  add Chandra/Mistral/Gemini/model/provider/cloud integration.**
- A `mixed_quality` verdict would instead have meant **improve ranking/placement before
  expanding further**; `decorative_or_bad_present` or `unclear` would have meant **do not
  expand visuals — keep doing selection-quality work**.
- **Chandra extraction integration remains blocked by its own live-validation gate**; this
  record does not touch it.
- Only the sanitized closed-vocabulary fields above were recorded — **no** real PDF path,
  filename, document text, OCR text, image bytes, base64, data URI, full URL, raw argv,
  token, model/mmproj/executable path, or raw exception. No binary/image/PDF/DOCX/ZIP/runtime
  output was committed.

---

## Slice 65 — diagram-first real operator validation (post-Slice-64 decision check)

> Validation-record slice. **No production pipeline/API/frontend code changed.** It adds
> NO visual behavior. It only *reran* the existing manual harness against the same real,
> **non-private** operator sample with the Slice 62 cap kept at `2` and the **Slice 64
> diagram-first ranking now in production**, to answer the one question Slice 64 left open:
> does diagram-first ranking actually make the **real** sample select hard-to-reconstruct
> diagrams/figures over reconstructable tables? **Docs-only — no harness correction needed.**

### Why this record exists

Slice 64 proved **synthetically** (and in Docker) that, when both are present, a
diagram/figure outranks a reconstructable table. What it explicitly did **not** do was a
**real** operator revalidation — its `CURRENT_TASK` note recorded the optional real run as
*not run* and warned the desired outcome (`selected_visual_type: diagrams_or_figures_present` /
`irreplaceable_visual_selected: true`) must **not** be assumed. Slice 65 closes that: same
harness, same already-supplied non-private sample, run inside the rebuilt Slice 64 container
with `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`, then a human inspection of the rendered PDF /
HTML / DOCX copied to a host folder.

### Diagram-first review — recorded result (sanitized, closed vocab)

```
diagram_first_operator_visual_quality_review: run
status: ok
pilot_inserted: true
inserted_visual_count: 2
selected_visual_type: tables_only
irreplaceable_visual_selected: false
selected_figures_quality: all_useful_or_acceptable
pdf_render_ok: true
pdf_image_visible: true
docx_render_ok: true
export_zip_ok: true
export_png_included: true
warnings:
  - multiple_figures_present_one_inserted
failure_category: none
no_leak_sweep: clean
```

The operator classified the selected visuals using only the closed vocabularies
`selected_visual_type: diagrams_or_figures_present · tables_only · mixed_diagram_and_table ·
unclear`, `irreplaceable_visual_selected: true · false · unknown`, and
`selected_figures_quality: all_useful_or_acceptable · mixed_quality ·
decorative_or_bad_present · unclear`, after inspecting the rendered PDF / HTML / DOCX from a
host output folder (the real sample path/filename and the figures' source contents are **not**
recorded here).

### Why diagram-first did not change the real-sample outcome (sanitized)

The honest result is that, on this real sample, the diagram-first ranking did **not** change
the selection from the Slice 63 outcome: the two inserted visuals are still
**reconstructable tables**, and the genuinely irreplaceable visual content present elsewhere
in the sample was **not** selected. Recorded with safe closed-vocabulary tokens:

```
selected_visual_type: tables_only
irreplaceable_visual_selected: false
decision_gate: diagram_first_ranking_did_not_change_real_outcome
root_cause: table_grid_heuristic_did_not_classify_lightly_ruled_tables_as_table
next_recommended_slice: improve_visual_type_detection_before_ui_polish
```

The Slice 64 ranking only re-orders candidates when its deterministic pixel classifier can
tell a `reconstructable_table` apart from a `diagram_or_figure`. On this sample the table-grid
heuristic — which fires only on a strong regular **horizontal *and* vertical** rule grid — did
**not** recognize the inserted visuals as tables (they lack a full ruled grid), so every safe
candidate landed in the same visual-type tier and selection fell back **byte-for-byte** to the
prior Slice 60/62 quality-and-order pick. The classifier behaved exactly as designed (no
regression); it simply had no clear table-vs-diagram signal to act on for these particular
visuals. So the visual-type *priority* tier was real but **uniform** here, and the diagram-first
preference never engaged.

> Note on the `multiple_figures_present_one_inserted` warning: it is the existing
> closed-vocabulary token, emitted whenever the source held more than one figure candidate.
> Under cap-2 its `_one_inserted` suffix is a known legacy misnomer — two figures were inserted
> here — but the trigger condition is still literally true and the actual count is recorded
> unambiguously in `inserted_visual_count: 2`. Renaming a closed-vocab token stays out of scope
> for a validation slice.

### Interpretation

- Slice 64 made diagram-first ranking **production behavior** and proved it **synthetically**.
- This Slice 65 record checks whether the real sample now selects diagrams/figures,
  mixed diagram+table, or still tables-only.
- **Recorded verdict: `selected_visual_type: tables_only`, `irreplaceable_visual_selected:
  false`, `selected_figures_quality: all_useful_or_acceptable`** with **2 figures inserted** —
  the plumbing again worked end-to-end (selection → capped multi-insertion → PDF/HTML/DOCX
  render → export bundle), and both inserted visuals are legible, content-bearing, non-decorative
  material that rendered visibly and rode along in the export ZIP.
- **But the higher-value goal is still unmet on the real sample:** the selected visuals are
  reconstructable tables, not the irreplaceable diagrams/figures the feature exists to protect,
  because the table-grid classifier did not fire for these lightly-ruled tables and therefore had
  nothing to deprioritize.
- **Per the desired-outcome rule, this is recorded honestly as the actual result, not a pass.**
  Because `selected_visual_type: tables_only`, **future work should continue visual-type ranking
  before any UI/placement polish** — specifically, strengthen table-vs-diagram detection (e.g.
  recognize borderless / lightly-ruled tables and/or detect genuine diagrams more strongly) so
  the ranking has a real signal to act on. **Do not expand beyond cap 2.** **Do not add a UI count
  selector.** **Do not add Chandra/Mistral/Gemini/model/provider/cloud integration.**
- A `mixed_diagram_and_table` or `diagrams_or_figures_present` / `irreplaceable_visual_selected:
  true` result would instead have meant the ranking is now working on real material and **future
  work could consider placement/citation polish**; `decorative_or_bad_present` or `unclear` would
  have meant **do not expand visual behavior — keep doing selection-quality work**.
- **Chandra extraction integration remains blocked by its own live-validation gate**; this record
  does not touch it.
- Only the sanitized closed-vocabulary fields above were recorded — **no** real PDF path,
  filename, document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token,
  model/mmproj/executable path, or raw exception. No binary/image/PDF/DOCX/ZIP/runtime output was
  committed.

---

## Slice 67 — improved-light-table real operator validation (post-Slice-66 decision check)

> Validation-record slice. **No production pipeline/API/frontend code changed.** It adds NO
> visual behavior. Its only purpose is to *rerun* the existing manual harness against the same
> real, **non-private** operator sample now that **Slice 66's improved lightly-ruled /
> text-heavy table detection is in production**, to answer the one question Slice 66 left open:
> does the strengthened classifier finally let diagram-first ranking pick a hard-to-reconstruct
> diagram/figure on the **real** sample, or does it still land on tables only? **Docs-only — no
> harness correction was needed.**

### Why this record exists

Slice 66 strengthened the deterministic, local, pixel-only visual-type detector so a
lightly-ruled / text-heavy table classifies as `reconstructable_table` instead of `unknown`,
giving diagram-first ranking a real signal. It proved this **synthetically and in Docker** but
explicitly left the **optional real operator revalidation NOT run** — the non-private operator
sample was unavailable in that session, and the desired flip
(`selected_visual_type: diagrams_or_figures_present` / `irreplaceable_visual_selected: true`)
was **not** assumed. Slice 67 exists to close that one gap: same harness, same already-supplied
non-private sample, run inside the rebuilt Slice 66 container with cap 2, then a human
inspection of the rendered PDF / HTML / DOCX copied to a host folder — **recorded only if true
after inspection.**

### Light-table review — recorded result (sanitized, closed vocab)

```
light_table_operator_visual_quality_review: run
status: ok
pilot_inserted: true
inserted_visual_count: 2
selected_visual_type: tables_only
irreplaceable_visual_selected: false
selected_figures_quality: all_useful_or_acceptable
pdf_render_ok: true
pdf_image_visible: true
docx_render_ok: true
export_zip_ok: true
export_png_included: true
warnings:
  - multiple_figures_present_one_inserted
failure_category: none
no_leak_sweep: clean
```

The non-private operator sample was available again at the operator-local location, so the
cap-2 operator harness **was** run inside the rebuilt Slice 66 container
(`GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1`, `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION=1`,
`GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`), the rendered PDF / HTML / DOCX were copied to a
host folder, and the operator inspected the inserted visuals by hand. The operator classified
the selected visuals using only the closed vocabularies
`selected_visual_type: diagrams_or_figures_present · tables_only · mixed_diagram_and_table ·
unclear`, `irreplaceable_visual_selected: true · false · unknown`, and
`selected_figures_quality: all_useful_or_acceptable · mixed_quality ·
decorative_or_bad_present · unclear` (the real sample path/filename and the figures' source
contents are **not** recorded here).

### Why improved light-table detection did not change the real-sample outcome (sanitized)

The honest result is that, on this real sample, Slice 66's strengthened lightly-ruled /
text-heavy table detection did **not** change the selection from the Slice 65 outcome: the two
inserted visuals are still **useful/acceptable but reconstructable tables**, and the genuinely
irreplaceable visual content present elsewhere in the sample was **not** selected. Recorded with
safe closed-vocabulary tokens:

```
selected_visual_type: tables_only
irreplaceable_visual_selected: false
decision_gate: light_table_detection_did_not_change_real_outcome
next_recommended_slice: add_sanitized_selection_trace_before_more_heuristics
```

> Note on the `multiple_figures_present_one_inserted` warning: it is the existing
> closed-vocabulary token, emitted whenever the source held more than one figure candidate.
> Under cap-2 its `_one_inserted` suffix is a known legacy misnomer — two figures were inserted
> here — but the trigger condition is still literally true and the actual count is recorded
> unambiguously in `inserted_visual_count: 2`. Renaming a closed-vocab token stays out of scope
> for a validation slice.

### Interpretation

- Slice 66 improved the **synthetic / light-table detection tests**, classifying lightly-ruled /
  text-heavy tables as `reconstructable_table` so diagram-first ranking has a real signal; it
  proved this synthetically and in Docker.
- The **real** post-Slice-66 cap-2 run still selected **two useful tables only**
  (`selected_visual_type: tables_only`, `inserted_visual_count: 2`) — the plumbing again worked
  end-to-end (selection → capped multi-insertion → PDF/HTML/DOCX render → export bundle), and
  both inserted visuals are legible, content-bearing, non-decorative material that rendered
  visibly and rode along in the export ZIP.
- These tables are **readable and useful, but reconstructable from extracted text** into clean
  generated tables.
- **No irreplaceable diagram/figure was selected.** The higher-value target the visual feature
  exists to protect — diagrams/flowcharts/labeled figures that cannot be reliably recreated from
  text — was again missed.
- **Therefore visual-type selection is still not solved for the real sample.** Per the
  desired-outcome rule this is recorded honestly as the actual result, not a pass.
- **Do not proceed to UI polish or cap expansion.** `decision_gate:
  light_table_detection_did_not_change_real_outcome`.
- **Before further heuristic tuning, add a sanitized selection trace / candidate audit** so future
  runs can explain *why* diagrams were not selected (which candidates existed, their classified
  visual type, and why the chosen tables outranked them) — all in closed-vocab / bounded-numeric
  form only. `next_recommended_slice: add_sanitized_selection_trace_before_more_heuristics`.
- **Do not expand beyond cap 2. Do not add a UI count selector. Do not add
  Chandra/Mistral/Gemini/model/provider/cloud integration.**
- A `mixed_diagram_and_table` or `diagrams_or_figures_present` /
  `irreplaceable_visual_selected: true` result would instead have meant the ranking is now working
  on real material and future work could consider placement/citation polish;
  `decorative_or_bad_present` or `unclear` would have meant **do not expand visual behavior — keep
  doing selection-quality work**.
- **Chandra extraction integration remains blocked by its own live-validation gate**; this
  record does not touch it.
- Only the sanitized closed-vocabulary fields above were recorded — **no** real PDF path,
  filename, document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token,
  model/mmproj/executable path, provider payload, or raw exception. No binary/image/PDF/DOCX/ZIP/
  runtime output was committed.

---

## Slice 69 — selection-trace operator audit (post-Slice-68 root-cause check)

> Validation-record slice. **No production pipeline/API/frontend code changed.** It adds NO
> visual behavior and changes no ranking/cap/default/gate/render/export/extraction-OCR routing.
> Its only purpose is to *rerun* the existing manual harness against the same real,
> **non-private** operator sample now that **Slice 68's sanitized selection trace
> (`visual_markdown_selection_trace.json`) is available**, and to read that trace to explain
> *why* the real sample still selects tables instead of irreplaceable diagrams — without
> leaking any source material. **Docs-only — no harness correction was needed.**

### Why this record exists

Slices 63/65/67 all recorded the same honest real-sample outcome — `selected_visual_type:
tables_only`, `irreplaceable_visual_selected: false` — but none could explain the *mechanism*
without inspecting source material. Slice 67's decision gate was explicit:
`next_recommended_slice: add_sanitized_selection_trace_before_more_heuristics`. Slice 68
delivered that trace (diagnostic only, closed-vocab / bounded-numeric, degrade-never-fail).
Slice 69 closes the loop: same harness, same already-supplied non-private sample, run inside the
rebuilt Slice 68 container with cap 2 and the trace enabled, then a human inspection of the
rendered PDF / HTML / DOCX **and** of the sanitized trace, recorded only as the actual result.

### Selection-trace audit — recorded result (sanitized, closed vocab)

```
selection_trace_operator_audit: run
status: ok
trace_artifact_present: true
trace_no_leak_sweep: clean
effective_max_images: 2
inserted_visual_count: 2
safe_candidate_count: 11
unsafe_candidate_count: 0
selected_count: 2
type_counts:
  diagram_or_figure: 11
  reconstructable_table: 0
  unknown: 0
  decorative_or_low_information: 0
selected_visual_type: tables_only
irreplaceable_visual_selected: false
selected_figures_quality: all_useful_or_acceptable
selection_explanation: tables_misclassified_as_diagram_or_figure
```

The non-private operator sample was available at the operator-local location, so the cap-2
operator harness **was** run inside the rebuilt Slice 68 container
(`GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1`, `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION=1`,
`GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`). The generated `visual_markdown_selection_trace.json`
plus the rendered PDF / HTML / DOCX were copied to a host folder; the trace was inspected for
leaks **before** any field was transcribed (it carried only closed-vocab tokens, bounded
integers / rounded floats, page numbers, and already-safe `assets/<slug>.png` refs — clean), and
the operator inspected the inserted visuals by hand using only the closed vocabularies
`selected_visual_type`, `irreplaceable_visual_selected`, and `selected_figures_quality`. The real
sample path/filename and the figures' source contents are **not** recorded here.

### What the trace revealed — the root cause (sanitized)

The trace newly explains the long-standing `tables_only` outcome, and the explanation is a
**classification** problem, not extraction or pure ranking:

- **Extraction is not the bottleneck.** There were **11 safe candidates** (`safe_candidate_count:
  11`, `unsafe_candidate_count: 0`); manual inspection confirmed at least one genuinely
  irreplaceable schematic diagram (a labeled multi-step figure that cannot be reconstructed from
  text) **was** present among them and was correctly extracted.
- **The deterministic pixel visual-type classifier over-accepts.** The trace's `type_counts` shows
  **all 11 safe candidates classified as `diagram_or_figure`** and **zero** as
  `reconstructable_table` / `unknown` / `decorative_or_low_information`. In reality the bucket
  contained reconstructable two-column definition/glossary tables, a decorative chapter-title
  banner, code/pseudocode boxes, **and** the genuine schematic figure — yet the classifier could
  not tell them apart and labelled them identically.
- **Diagram-first ranking is therefore starved of signal.** With every candidate carrying the same
  `visual_type_score: 3`, Slice 64's diagram-first ordering has nothing to discriminate on, so
  selection falls back to pure quality score. The two clean, content-sized definition tables
  (`quality_score: 1.2`, `selected_by_quality_ranking` / `selected_by_priority_order`) outranked
  the genuine schematic figure and were selected; the irreplaceable diagram was **not** selected.

```
selected_visual_type: tables_only
irreplaceable_visual_selected: false
selection_explanation: tables_misclassified_as_diagram_or_figure
root_cause: visual_type_classifier_cannot_distinguish_tables_from_diagrams
decision_gate: classification_precision_is_the_real_bottleneck
next_recommended_slice: improve_visual_type_classification_table_vs_diagram_precision
```

### Interpretation

- Slice 68 added the sanitized selection trace; Slice 69 used it on the real non-private sample to
  understand **why tables still win over diagrams** without leaking source material — exactly the
  question Slices 63/65/67 could not answer.
- The trace shows **diagrams are present among the safe candidates** (so the next work is **not**
  extraction / candidate generation) and that they are **classified correctly *enough* to be
  selectable** — the failure is that **reconstructable tables are *also* classified as
  `diagram_or_figure`**, collapsing every candidate into one bucket and neutralizing diagram-first
  ranking.
- Per the prompt's branch logic this is the **classification** branch: *diagrams exist but the
  visual-type signal is wrong* (tables are not being separated from diagrams). The next work is
  **visual-type classification precision — specifically table-vs-diagram discrimination** — not a
  blind ranking/threshold change (ranking is correct but signal-starved) and not extraction.
- The trace is **sufficient** to localize the bottleneck (the `type_counts` collapse is
  conclusive). Its per-candidate **rejection-reason coverage is sparse** for non-selected,
  above-floor candidates (only `rejected_secondary_below_quality_floor: 1` was recorded for the
  nine unselected safe candidates), because the trace assigns soft-rejection tokens only in narrow
  cases. That is a possible future *trace* refinement, but it does **not** block this slice's
  conclusion and is **not** a reason to guess heuristics.
- **Do not proceed to UI polish or cap expansion** until an irreplaceable diagram/figure is
  actually selected in real validation, or there is a deliberate product decision to accept tables.
  `decision_gate: classification_precision_is_the_real_bottleneck`.
- **Do not expand beyond cap 2. Do not add a UI count selector. Do not add
  Chandra/Mistral/Gemini/model/provider/cloud integration.** Chandra extraction integration remains
  blocked by its own live-validation gate; this record does not touch it.
- All render/export plumbing again worked end-to-end (`pdf_render_ok` / `pdf_image_visible` /
  `docx_render_ok` / `export_zip_ok` / `export_png_included: true`, `warnings:
  [multiple_figures_present_one_inserted]`, `failure_category: none`); the two selected tables are
  legible, content-bearing, non-decorative material — `selected_figures_quality:
  all_useful_or_acceptable` — they are simply **reconstructable, not irreplaceable**.
- Only the sanitized closed-vocabulary fields above were recorded — **no** real PDF path,
  filename, document text, OCR text, source caption/table text, image bytes, base64, data URI,
  full URL, raw argv, token, model/mmproj/executable path, provider payload, or raw exception. The
  runtime `visual_markdown_selection_trace.json` was **inspected but not committed**; no
  binary/image/PDF/DOCX/ZIP/runtime output was committed.

---

## Slice 71 — table-vs-diagram precision operator validation (post-Slice-70 real-sample check)

> Validation-record slice. **No production pipeline/API/frontend code changed; no heuristic was
> tuned.** It reruns the existing manual harness against the same real, **non-private** operator
> sample now that **Slice 70's table-vs-diagram classifier precision fix** is on trunk, then
> reads the sanitized selection trace and manually inspects the rendered PDF/HTML/DOCX to record
> — using closed vocabularies only — whether the pilot now selects an irreplaceable
> diagram/figure instead of only reconstructable tables. **Docs-only — no harness correction was
> needed.**

### Why this record exists

Slice 69 localized the failure to classification (all 11 safe candidates collapsed to
`diagram_or_figure`); Slice 70 added a deterministic, pixel-only two-column-split signal so
two-column/glossary/definition tables classify as `reconstructable_table`, giving diagram-first
ranking a real signal. Slice 71 closes the loop on the real sample: same harness, same
already-supplied non-private sample, cap 2, both enable gates, inside the rebuilt container, then
a human inspection of the rendered output **and** the sanitized trace, recorded only as the
actual result.

### Table-vs-diagram precision audit — recorded result (sanitized, closed vocab)

```
table_diagram_precision_operator_validation: run
status: ok
trace_artifact_present: true
trace_no_leak_sweep: clean
effective_max_images: 2
inserted_visual_count: 2
safe_candidate_count: 11
unsafe_candidate_count: 0
selected_count: 2
type_counts:
  diagram_or_figure: 9
  reconstructable_table: 2
  unknown: 0
  decorative_or_low_information: 0
selected_visual_type: tables_only
irreplaceable_visual_selected: false
selected_figures_quality: all_useful_or_acceptable
selection_explanation: tables_still_misclassified_as_diagram_or_figure
pdf_render_ok: true
pdf_image_visible: true
docx_render_ok: true
export_zip_ok: true
export_png_included: true
warnings:
  - multiple_figures_present_one_inserted
failure_category: none
no_leak_sweep: clean
```

The non-private sample was available, so the cap-2 harness **was** run inside the rebuilt
container (`GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1`,
`GUIDEFORGE_LOCAL_FIGURE_EXTRACTION=1`, `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`). The generated
`visual_markdown_selection_trace.json` plus the rendered PDF/HTML/DOCX were copied to a host
folder; the trace was inspected for leaks **before** any field was transcribed (it carried only
closed-vocab tokens, bounded integers/rounded floats, page numbers, and already-safe
`assets/<slug>.png` refs — clean), and the operator inspected the inserted visuals by hand using
only the closed vocabularies. The real sample path/filename and the figures' source contents are
**not** recorded here.

### What the trace + manual inspection revealed (sanitized)

- **Slice 70 measurably improved classification.** The trace's `type_counts` is **no longer
  collapsed** to a single bucket: it now reads `diagram_or_figure: 9` **and** `reconstructable_table: 2`
  (Slice 69 read `diagram_or_figure: 11`, `reconstructable_table: 0`). Two reconstructable
  candidates are now correctly typed and were **deprioritized** behind the diagram tier
  (`rejection_reason_counts.deprioritized_reconstructable_table: 2`).
- **But the two SELECTED visuals are still reconstructable two-column definition tables.** Manual
  inspection of the rendered output ground-truths that both inserted visuals are clean
  header-plus-rows **definition/glossary tables**, not irreplaceable graphics
  (`selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`). They are legible,
  content-bearing, non-decorative material (`selected_figures_quality: all_useful_or_acceptable`)
  — simply reconstructable, not irreplaceable.
- **The residual gap is still classification precision, not extraction or ranking.** Genuine
  irreplaceable diagrams/figures (multi-panel schematics, network-flow diagrams, a propagation
  chart) **were present and correctly extracted** among the safe candidates — so this is **not**
  `diagrams_absent_from_safe_candidates`. The two selected definition tables are densely ruled
  with wrapped multi-line description cells; the Slice 70 two-column-split guard (which requires
  several *separated* horizontal text bands per column) does not fire when the wide
  description column's wrapped lines merge into too few bands, so those specific tables still fall
  through to `diagram_or_figure` and, appearing first in priority order within the diagram tier,
  are selected ahead of the real diagrams. `selection_explanation:
  tables_still_misclassified_as_diagram_or_figure`.

```
selected_visual_type: tables_only
irreplaceable_visual_selected: false
selection_explanation: tables_still_misclassified_as_diagram_or_figure
root_cause: dense_ruled_wrapped_two_column_tables_still_typed_as_diagram_or_figure
decision_gate: classification_precision_still_the_bottleneck
next_recommended_slice: continue_table_vs_diagram_classification_precision
```

### Interpretation

- Slice 70 was a real, measurable improvement (the type buckets split for the first time), but the
  real-sample **end result is still `tables_only`** — the precision fix did not yet generalize to
  the sample's densely-ruled, wrapped-text two-column definition tables.
- Because **irreplaceable diagrams/figures are present among the safe candidates** but were not
  selected, the next work is **not** extraction/candidate generation and **not** a blind
  ranking/threshold change — it is **continued table-vs-diagram classification precision** (or,
  alternatively, a separately-designed, controlled understanding layer). Do not guess heuristics;
  the trace + manual ground-truth localize the exact residual case.
- **Do not proceed to UI polish or cap expansion** until an irreplaceable diagram/figure is
  actually selected in real validation, or there is a deliberate product decision to accept tables.
  `decision_gate: classification_precision_still_the_bottleneck`.
- **Do not expand beyond cap 2. Do not add a UI count selector. Do not add
  Chandra/Mistral/Gemini/model/provider/cloud integration.** Chandra extraction integration remains
  blocked by its own live-validation gate; this record does not touch it.
- All render/export plumbing again worked end-to-end (`pdf_render_ok` / `pdf_image_visible` /
  `docx_render_ok` / `export_zip_ok` / `export_png_included: true`, `warnings:
  [multiple_figures_present_one_inserted]`, `failure_category: none`).
- Only the sanitized closed-vocabulary fields above were recorded — **no** real PDF path,
  filename, document text, OCR text, source caption/table text, image bytes, base64, data URI,
  full URL, raw argv, token, model/mmproj/executable path, provider payload, or raw exception. The
  runtime `visual_markdown_selection_trace.json` was **inspected but not committed**; no
  binary/image/PDF/DOCX/ZIP/runtime output was committed.

---

## Slice 73 — dense-wrapped-table real operator validation (post-Slice-72 decision check)

> Validation-record slice. **No production pipeline/API/frontend code changed; no heuristic was
> tuned.** It reruns the existing manual harness against the same real, **non-private** operator
> sample now that **Slice 72's dense / wrapped-cell table detection fix** is on trunk, then reads
> the sanitized selection trace and manually inspects the rendered PDF/HTML/DOCX to record — using
> closed vocabularies only — whether the pilot now selects at least one irreplaceable
> diagram/figure instead of only reconstructable tables. **Docs-only — no harness correction was
> needed.**

### Why this record exists

Slices 63/65/67/69/71 all recorded the same honest real-sample outcome — `selected_visual_type:
tables_only`, `irreplaceable_visual_selected: false`. Slice 69 localized the cause to
classification (every safe candidate collapsed to `diagram_or_figure`); Slice 70 split the buckets
for the first time; Slice 71 showed the residual gap was that the sample's **densely-ruled,
wrapped-multi-line two-column definition tables** still fell through to `diagram_or_figure` and were
selected ahead of the genuine diagrams. Slice 72 added a deterministic, pixel-only dense / wrapped
ruled-table signal so those tables classify as `reconstructable_table`. Slice 73 closes the loop on
the real sample: same harness, same already-supplied non-private sample, cap 2, both enable gates,
inside the rebuilt container, then a human inspection of the rendered output **and** the sanitized
trace, recorded only as the actual result.

### Dense-wrapped-table audit — recorded result (sanitized, closed vocab)

```
dense_wrapped_table_operator_validation: run
status: ok
trace_artifact_present: true
trace_no_leak_sweep: clean
effective_max_images: 2
inserted_visual_count: 2
safe_candidate_count: 11
unsafe_candidate_count: 0
selected_count: 2
type_counts:
  diagram_or_figure: 9
  reconstructable_table: 2
  unknown: 0
  decorative_or_low_information: 0
selected_visual_type: diagrams_or_figures_present
irreplaceable_visual_selected: true
selected_figures_quality: all_useful_or_acceptable
selection_explanation: diagrams_selected_after_dense_table_fix
pdf_render_ok: true
pdf_image_visible: true
docx_render_ok: true
export_zip_ok: true
export_png_included: true
warnings:
  - multiple_figures_present_one_inserted
failure_category: none
no_leak_sweep: clean
```

The non-private sample was available, so the cap-2 harness **was** run inside the rebuilt
container (`GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1`,
`GUIDEFORGE_LOCAL_FIGURE_EXTRACTION=1`, `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`). The generated
`visual_markdown_selection_trace.json` plus the rendered PDF/HTML/DOCX were copied to a host
folder; the trace was inspected for leaks **before** any field was transcribed (it carried only
closed-vocab tokens, bounded integers/rounded floats, page numbers, and already-safe
`assets/<slug>.png` refs — clean), and the operator inspected the inserted visuals by hand using
only the closed vocabularies. The real sample path/filename and the figures' source contents are
**not** recorded here.

### What the trace + manual inspection revealed (sanitized)

- **The real-sample outcome finally flipped.** For the first time across Slices 63/65/67/69/71,
  both selected visuals are **diagrams/figures**, not reconstructable tables
  (`selected_visual_type: diagrams_or_figures_present`, `irreplaceable_visual_selected: true`).
  The trace records both selected candidates as `classified_diagram_or_figure` with
  `selection_reason: selected_by_diagram_first_ranking` — diagram-first ranking engaged on real
  material.
- **The Slice 72 dense/wrapped-table fix is what unblocked it.** The trace's `type_counts` still
  reads `diagram_or_figure: 9` and `reconstructable_table: 2`, but the two reconstructable
  definition tables that Slice 71 *selected* are now **deprioritized** behind the diagram tier
  (`rejection_reason_counts.deprioritized_reconstructable_table: 2`), so the diagram-first order
  now reaches the genuine schematic figures instead of stopping at the tables.
- **Manual ground-truth confirms quality.** Both inserted visuals are legible, content-bearing,
  non-decorative graphics from distinct source pages (`selected_figures_quality:
  all_useful_or_acceptable`); they rendered visibly in the PDF, in the DOCX, and rode along in the
  export ZIP as safe relative `assets/<slug>.png` refs.

```
selected_visual_type: diagrams_or_figures_present
irreplaceable_visual_selected: true
selection_explanation: diagrams_selected_after_dense_table_fix
decision_gate: irreplaceable_diagram_selected_on_real_sample
next_recommended_slice: visual_placement_or_citation_polish_may_now_be_considered
```

> Note on the `multiple_figures_present_one_inserted` warning: it is the existing
> closed-vocabulary token, emitted whenever the source held more than one figure candidate. Under
> cap-2 its `_one_inserted` suffix is a known legacy misnomer — two figures were inserted here —
> but the trigger condition is still literally true and the actual count is recorded unambiguously
> in `inserted_visual_count: 2`. Renaming a closed-vocab token stays out of scope for a validation
> slice.

### Interpretation

- Slice 72 improved dense/wrapped-table detection **synthetically and in Docker**; Slice 73
  validates the result on the **real** non-private sample, and the long-standing `tables_only`
  outcome has now flipped to **diagrams selected**.
- **Recorded verdict: `selected_visual_type: diagrams_or_figures_present`,
  `irreplaceable_visual_selected: true`, `selected_figures_quality: all_useful_or_acceptable`** with
  **2 figures inserted** — the higher-value goal the visual feature exists to protect (preserving
  visuals that cannot be reliably recreated from text) is now met on the real sample.
- Because an irreplaceable diagram/figure is finally selected on the real sample, **future visual
  work may now consider placement / citation polish** as a separately-designed slice
  (`next_recommended_slice: visual_placement_or_citation_polish_may_now_be_considered`). This is a
  *may*, not a mandate; classification precision can still be revisited if other samples regress.
- Had the output stayed tables-only, the recorded guidance would have been to continue
  classification precision or introduce a separately-designed, controlled understanding layer; had
  diagrams been absent from the safe candidates, the guidance would have been to inspect extraction
  / candidate generation. Neither applies here — diagrams were present, correctly extracted, and
  now correctly selected.
- **Do not expand beyond cap 2. Do not add a UI count selector. Do not add
  Chandra/Mistral/Gemini/model/provider/cloud integration.** The default remains exactly 1 and the
  cap remains hard-capped at 2. Chandra extraction integration remains blocked by its own
  live-validation gate; this record does not touch it.
- All render/export plumbing again worked end-to-end (`pdf_render_ok` / `pdf_image_visible` /
  `docx_render_ok` / `export_zip_ok` / `export_png_included: true`, `warnings:
  [multiple_figures_present_one_inserted]`, `failure_category: none`).
- Only the sanitized closed-vocabulary fields above were recorded — **no** real PDF path,
  filename, document text, OCR text, source caption/table text, image bytes, base64, data URI,
  full URL, raw argv, token, model/mmproj/executable path, provider payload, or raw exception. The
  runtime `visual_markdown_selection_trace.json` was **inspected but not committed**; no
  binary/image/PDF/DOCX/ZIP/runtime output was committed.
