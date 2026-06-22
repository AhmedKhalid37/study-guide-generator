# COMBINED_ASSET_COMPANION_GUIDE.md — Slice 177B

> Phase 4 product path. Closed-label record only. No private artifacts, raw
> table/figure/caption/source/OCR text, descriptor JSON, prompts, responses,
> provider payloads, screenshots, image bytes, base64/data URIs, private paths,
> hashes, or byte counts appear here.

## What this slice proves

Slice 177B composes the two already-accepted Phase 4 companion outputs into **one**
student-visible private rendered HTML guide:

1. the accepted **176X writer-generated table companion** — faithful reconstructed
   table + teaching explanation beneath it + role-aware **study** simplified table
   (not a row-reduced copy); and
2. the accepted **177A writer-generated non-table figure companion** — a visible
   non-table visual asset + explanation + how-to-read steps + exam takeaway.

This demonstrates that table companions and non-table figure companions can **coexist
in one rendered guide artifact**. It proves **one combined table+figure path only** —
it does **not** claim that all tables or all figures are solved.

## Lineage

- **176X** proved role-aware table simplification (study-oriented simplified table,
  verified not a row-reduced duplicate).
- **177A** proved **one** writer-generated non-table figure companion (ensemble
  structure diagram, inserted as a safe private-relative image asset).
- **177B** combines those accepted outputs into one private rendered guide.

## Scope guards (what this slice is NOT)

No provider call, no generation rerun, no generation-behavior change, no OCR rerun, no
coverage eval, no numeric verification, no frontend/API change, no judge, no repair, no
cloud OCR, no Chandra, no new asset framework. `judge_ready=false`,
`repair_ready=false`. The preferred path reuses the accepted private 176X and 177A
guide artifacts verbatim; a provider call is never made by this module.

## Module / runner / test

- **module** — `pipeline/combined_asset_companion_guide.py`
  (`run_combined_asset_companion_guide(...)` / `main()`). Narrow private
  combined-artifact producer; not a broad framework.
- **runner** — `test_scripts/run_combined_asset_companion_guide.py`
  (`PRIVATE_TABLE_COMPANION_DIR`, `PRIVATE_FIGURE_COMPANION_DIR`,
  `PRIVATE_COMBINED_DIR`).
- **test** — `test_scripts/test_combined_asset_companion_guide.py` (public-safe
  synthetic fixtures only).

## How it works

1. Load the accepted 176X table companion output (guide Markdown + closed summary).
2. Load the accepted 177A figure companion output (guide Markdown + closed summary +
   `assets/`).
3. Verify the inputs are the **accepted** artifacts via closed-flag + structural checks:
   - table companion has a role-aware simplified table that is study-oriented and
     **not** a row-reduced copy (faithful table + explanation + simplified table all
     present);
   - figure companion uses the accepted non-table structure (non-table figure; not
     table / matrix / grid / text-only / partial sliver) with a safe relative image ref
     and the required study headings.
4. Refuse any inlined raw image data (`data:` / base64) in either source guide.
5. Copy each `assets/<name>` figure crop into the combined private dir (safe relative
   refs only; reject `..` or unsafe refs; block if the asset is missing).
6. Compose one Markdown guide: title/header → **Reconstructed table companion** block →
   `---` separator → **Non-table figure companion** block.
7. Render to private HTML; refuse the render if it would contain a `data:` URI or a raw
   private path.
8. Write the private combined guide + closed summary into a **gitignored** private
   artifact directory and emit a closed committed-safe summary.

## Closed summary (committed-safe fields)

`artifact_name=combined_asset_companion_guide` · `slice=177B` · `status` ·
`source_label=ensemble` · `combined_render_format=html` · `combined_render_status` ·
`private_combined_guide_written` · `private_combined_guide_gitignored` ·
table block (`table_companion_source=private_176x_writer_table_companion`,
`table_companion_present`, `faithful_table_present`, `table_explanation_present`,
`role_aware_simplified_table_present`, `simplified_table_is_row_reduced_copy=false`,
`simplified_table_is_study_oriented=true`, `table_visibility_status`) ·
figure block (`figure_companion_source=private_177a_writer_figure_companion`,
`figure_companion_present`, `figure_visual_present`,
`figure_visual_type_closed=flow_or_structure_diagram`,
`figure_visual_is_non_table_figure=true`, `figure_visual_is_text_only=false`,
`figure_visual_is_partial_sliver=false`, `figure_visual_is_table_like=false`,
`figure_visual_is_matrix=false`, `figure_visual_is_grid=false`,
`figure_explanation_present`, `figure_reading_steps_present`,
`figure_exam_takeaway_present`, `figure_visibility_status`) ·
negative canaries (`raw_private_paths_in_rendered_html=false`, `data_image_used=false`,
`base64_image_used=false`, `image_bytes_committed=false`, raw-text canaries all false,
`prompts_committed=false`, `responses_committed=false`,
`provider_payloads_committed=false`) · posture (`provider_call_made=false`,
`generation_rerun=false`, `generation_behavior_changed=false`, `cloud_ocr_used=false`,
`ocr_rerun=false`, `coverage_eval_rerun=false`, `numeric_verification_claimed=false`,
`frontend_api_changed=false`, `judge_ready=false`, `repair_ready=false`,
`operator_private_read_required=true`, `operator_private_read_done=false`) ·
`blocked_by` · `recommended_next_step`.

## Hard pass condition (real run)

`status=completed`, `combined_render_status=rendered`,
`private_combined_guide_written=true`, `private_combined_guide_gitignored=true`, both
companion blocks present and validated, `blocked_by=none`,
`recommended_next_step=operator_read_private_combined_asset_companion_guide`.

## Honest block conditions

`table_companion_not_found` · `figure_companion_not_found` ·
`table_companion_row_reduced` (simplified table is a row-reduced copy, not study-oriented)
· `figure_companion_table_like` (figure is table/matrix/grid/text-only/sliver) ·
`data_uri_or_base64_refused` · `raw_private_path_in_render` ·
`figure_asset_unavailable` · `unsafe_private_artifact_path` · `render_failed`.

## Status

Implemented; real private run over the accepted 176X + 177A outputs completed with the
hard-pass closed summary. **NOT committed — stopped for operator review.** The operator
must open the private combined HTML and confirm: faithful table visible/readable, table
explanation visible, role-aware simplified study table visible, non-table figure
visible/readable, figure explanation/reading steps/exam takeaway useful, and no raw
private paths or broken-image indicators. The private rendered HTML path is handed to
the operator out-of-band (never recorded in docs).
