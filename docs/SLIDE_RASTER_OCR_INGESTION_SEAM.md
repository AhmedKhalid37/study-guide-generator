# SLIDE_RASTER_OCR_INGESTION_SEAM.md — Slice 176H

> Closed-vocabulary record of the local slide-raster OCR **ingestion artifact seam**.
> Closed tokens / counts / bools / labels / structural shapes only: no guide / source
> / OCR / table / caption text, no formulas, no raw values, no private paths /
> filenames / hashes / byte counts / screenshots, no model files / caches, no provider
> payloads / prompts / responses / secrets. The repo (code) is the source of truth;
> verify `pipeline/slide_raster_ocr_ingestion.py` before relying on this.

---

## 0. What this slice is

The **first minimal, off-by-default increment** of 176G's recorded next step
`build_local_slide_ocr_ingestion_pipeline`. It is **only the artifact seam** — the
pure helpers, the private-artifact policy, the closed summary schema, and an
inert-by-default runner — so a later slice can wire real downstream consumers onto a
stable, leak-safe boundary.

**IS:** a small, local-only, off-by-default ingestion seam that can classify a PDF
text layer, detect full-page raster slides, render selected pages locally, run
configured **local** OCR engines into a **private gitignored/temp** artifact
directory, and emit a committed-safe **closed summary**.

**IS NOT:** guide-generation wiring, frontend/API integration, full ingestion
rollout, numeric-recompute wiring, a Layer-2 judge, repair, cloud OCR, provider/model
generation, or a broad new framework. `judge_ready=false`; `repair_ready=false`.

## 1. Why it exists (justified by 176F/176G)

- 176F: both real decks are **near-empty-text, full-page raster slide images**;
  **Tesseract** recovers bulk prose / loose tables but **fails** dense structured
  grids.
- 176G: **local structured OCR** (Chandra OCR 2 as GGUF via local `llama-server`,
  the Slice-41 path — local-only, no cloud/API; the pip `chandra-ocr` hf/vllm/cli
  package is **not installed**) recovers dense tables + math, but the **Gini
  masked-recompute proof remains outstanding** (the representative Gini slide was a
  per-split *answer* summary, not the raw class-count grid). Gini stays `unverified`.
- So the next real artifact is an ingestion seam, built small and off-by-default —
  not "run the harness again" (the harnesses are transient/gitignored and not
  reusable) and not a broad framework.

## 2. Module surface (closed)

`pipeline/slide_raster_ocr_ingestion.py` exposes pure/testable helpers + an
inert-by-default runner:

- `classify_pdf_text_layer(...)` → `near_empty` / `partial` / `usable` / `unknown`
  (from per-page text **lengths only**, never the text).
- `detect_full_page_image_blocks(...)` → `full_page_raster_slide_images` /
  `mixed_text_and_images` / `text_layer` / `unknown` (from numeric/bool visual
  signals only).
- `is_private_artifact_dir(...)` → whether raw OCR may be written there (temp dir or
  a known gitignored segment only; a tracked repo path is refused).
- `render_selected_pages_to_temp_images(...)` → renders selected pages to PNGs under
  a **private** dir only; degrades to `(0, [])` otherwise. Local, OCR-free.
- `run_tesseract_if_available(...)` → closed status + mean confidence **only** (no
  raw text returned).
- `run_local_structured_ocr_if_configured(...)` → closed status + closed engine
  label; never contacts a network service; GGUF/VLM **not** relabelled hf/cli.
- `write_private_ocr_artifact(...)` → writes raw payload only into a confirmed
  private dir; returns booleans only.
- `build_closed_slide_ocr_summary(...)` → coerces every field to its closed set.
- `run_slide_raster_ocr_ingestion(...)` → inert unless explicitly enabled.

## 3. Safety posture (hardwired)

- **Local only. No cloud OCR.** `cloud_ocr_used=false` is hardwired.
- **Off by default.** Disabled runner → `status=skipped`.
- **Raw OCR / rendered images are private-only.** Permitted under the system temp
  dir or a gitignored segment (`local_operator_baselines/`, `jobs/`, `.private_ocr/`,
  `.trash/`) only; a tracked path is refused and the runner returns a closed
  `blocked` status rather than writing into the repo.
- **Committed-safe summary.** Every field is a closed token / count / bool;
  `raw_ocr_committed=false`, `raw_table_text_committed=false`,
  `rendered_images_committed=false`, `model_files_committed=false`,
  `model_cache_committed=false` are hardwired; no path/filename/size/text is accepted.
- **No numeric claim.** `numeric_recompute_readiness` can never be
  `ready_for_masked_recompute` from this seam (forced to `needs_input_cell_parser`).

## 4. Closed summary schema

`artifact_name=slide_raster_ocr_ingestion_summary`; fields:
`status` (`completed`/`degraded`/`blocked`/`skipped`), `source_label`,
`pages_considered_count`, `pages_rendered_count`,
`text_layer_status`, `effective_content_form`,
`tesseract_status` (`ran`/`available`/`not_available`/`failed`/`skipped`),
`structured_ocr_status` (`ran_local`/`available`/`not_available`/`failed_local`/`skipped`),
`structured_ocr_engine`
(`chandra_gguf_local`/`local_structured_ocr_vlm`/`chandra_hf_local`/`chandra_cli_local`/`none`/`unknown`),
`cloud_ocr_used=false`, `private_artifact_written`, `private_artifact_gitignored`,
`raw_ocr_committed=false`, `raw_table_text_committed=false`,
`rendered_images_committed=false`, `model_files_committed=false`,
`model_cache_committed=false`,
`bulk_text_quality` / `loose_table_quality` / `dense_grid_quality` /
`figure_caption_quality` (`clean`/`partial`/`failed`/`not_run`),
`downstream_readiness`
(`ready_for_visible_table_pilot`/`ready_for_bulk_content_ingestion_pilot`/`needs_engine_setup`/`blocked`),
`numeric_recompute_readiness`
(`not_attempted`/`needs_input_cell_parser`/`blocked`/`ready_for_masked_recompute`),
`warnings` (closed-vocab list).

## 5. Optional local smoke (closed labels only)

Real deck, **first 2 pages**, rendered to `/tmp` only (auto-deleted), closed labels
only: `status=completed` · `pages_rendered_count=2` · `tesseract_status=available`
(binary present, python bindings absent in host → bulk text `not_run`) ·
`structured_ocr_status=not_available` · `cloud_ocr_used=false` ·

The smoke's `structured_ocr_status=not_available` is **scoped to the seam smoke
configuration** — structured OCR was **not configured/enabled for this smoke**
(`structured_ocr_configured=false`), so the closed vocabulary maps that to
`not_available`. It is **not** a global claim that local structured OCR is
unavailable. 176G already proved the local GGUF / `llama-server` structured OCR
route **can run** and recovered dense grids; nothing here contradicts that.
Remaining closed smoke labels:
`private_artifact_written=true` · `rendered_images_committed=false` ·
`numeric_recompute_readiness=needs_input_cell_parser`. The smoke sampled the
title/intro pages (`text_layer`/`usable`), which **does not** contradict the 176F/176G
`near_empty` finding on the **category-selected dense grid slides** — a different page
class, not a re-measurement of the dense slides.

## 6. Downstream order

1. **Phase 4 visible table/figure insertion** is the first downstream consumer of the
   closed summary + private artifacts.
2. **Numeric recompute is a later consumer**, and requires a **masked recompute from
   raw input cells** (the Gini class-count grid, answer excluded) before any number is
   trusted. Until that proof passes, Gini stays `unverified` and the §0 safety
   invariant holds (no confident-but-wrong cleanup).

No cloud OCR; no provider/model generation; no guide regeneration; no Layer-2 judge;
no repair. No raw private OCR / table / source / guide text, private paths, filenames,
hashes, byte counts, screenshots, model files, or model caches committed.
`local_operator_baselines/` stays ignored. `judge_ready=false`; `repair_ready=false`.
