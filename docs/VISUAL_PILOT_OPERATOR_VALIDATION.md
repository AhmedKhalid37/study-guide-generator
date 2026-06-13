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
