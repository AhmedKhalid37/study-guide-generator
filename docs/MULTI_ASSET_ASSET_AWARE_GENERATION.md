# MULTI_ASSET_ASSET_AWARE_GENERATION.md — Slice 177G

> Private, off-by-default. The repo/code is the source of truth. Closed summaries
> only — no raw guide/table/figure/caption/source/OCR/descriptor text, image bytes,
> base64/data URIs, prompts, responses, provider payloads, private paths, source
> filenames, hashes, or byte counts in committed artifacts.

## What 177G is

Slice 177G is the first Phase 4 slice that runs **one real asset-aware guide
generation over the full available ensemble asset descriptor set** instead of a
single hand-fed descriptor. It generalises the genuinely useful 176W/176X/177A
asset-aware *writer* path (a provider/model writer receives closed descriptors —
no image — inserts a token where each asset belongs, and writes a real
explanation beneath it; tokens then resolve to faithful reconstructed tables or
safe private-relative figure images and render to private HTML) from **one**
asset to **multiple** ready assets in the **same generation pass**.

The real artifact is a **private rendered guide containing multiple distinct
inserted assets, each with an explanation beneath it** — not a preview, seam,
hook, manifest, consumer, or coverage packet.

- **Module:** `pipeline/multi_asset_asset_aware_generation.py`
  (`run_multi_asset_asset_aware_generation(...)`).
- **Private runner:** `test_scripts/run_multi_asset_asset_aware_generation_private.py`.
- **Tests:** `test_scripts/test_multi_asset_asset_aware_generation.py` (synthetic only).

## Why 177F was abandoned

Slice 177F (asset companion manifest handoff) only recorded the *same* single
accepted table + single accepted figure lineage into a manifest. It was another
wrapper around the same two assets and did not move Phase 4 toward useful
multi-asset insertion. The uncommitted 177F work was abandoned (a safety copy was
preserved outside the repo; the in-repo 177F files were removed before branching
177G from trunk). No `git stash` was used, so the parked Slice 60 stash order is
untouched.

## How it works

1. **Build the full available descriptor set** from existing private artifacts
   only (no extraction/OCR rerun):
   - **Tables** from the recovered visible-asset payload
     (`visible_table_figure_pilot.json`): each `proximity_matrix` /
     `patient_dataset_table` with insertable Markdown becomes a
     `reconstructed_table` descriptor (`render_role=insert_as_table`).
   - **Non-table figure** from the accepted 176Z non-table figure descriptor
     (validated as a real non-table flow/structure diagram with a usable crop) →
     `non_table_flow_or_structure_diagram` descriptor
     (`render_role=insert_as_figure_with_explanation`). Table-like / matrix / grid
     visuals are refused as figures by construction.
   - **Charts/graphs** are included only when an existing descriptor is sufficient
     for a text-only writer; otherwise they count toward
     `descriptor_missing_for_generation_count` and set
     `diagram_caption_descriptor_gap=true` (honest gap, not a coverage slice).
   Each descriptor carries closed fields: `asset_id`, `asset_kind_closed`,
   `source_label=ensemble`, `descriptor_ready_for_text_writer`, `render_role`.
2. **Require a true multi-asset input.** If fewer than three ready descriptors
   exist, block honestly (`blocked_by=insufficient_existing_multi_asset_descriptor_set`).
   No one-table/one-figure repeat.
3. **One asset-aware writer generation.** Every ready descriptor and its
   `{{asset:<safe_asset_id>}}` token are exposed in a single prompt. The writer must
   use every useful descriptor, place each token exactly once, write a real
   explanation beneath each (tables: faithful table + role-aware simplified study
   table; figures: what-it-shows + how-to-read + exam takeaway), omit only with a
   clear reason, never leave an orphan token, and never duplicate an asset.
4. **Resolve every token** (the writer never pastes assets): table tokens → the
   faithful reconstructed Markdown table (never an image); figure tokens → a safe
   `assets/<name>` image copied into the gitignored output dir. Data URIs / base64
   and raw private paths are refused.
5. **Render** the guide to private HTML under the gitignored
   `local_operator_baselines/.private_ocr` tree and emit a closed summary.

## Provider

This slice is **allowed and expected to call the writer/provider path once**. It
prefers the provider 176W used successfully (DeepSeek). If no provider is
configured or the call fails, it blocks honestly (`provider_unavailable` /
`writer_generation_unavailable`) — it never fakes success with a synthetic or
no-provider output. (Host note: the real run needs the `openai` package, which
lives in the project `.venv` / the Docker image, not bare host Python.)

## Hard pass condition

`status=completed`, off-by-default, normal generation default unchanged,
`generation_scope=single_private_ensemble_multi_asset_generation`,
`wrapper_slice=false`, `manifest_consumer=false`, `coverage_packet_only=false`,
`auto_discovery_enabled=false`, `all_assets_claimed=false`; descriptors built with
`descriptor_ready_count >= 3` and `multi_asset_requirement_met=true`;
`provider_call_made=true`, `writer_generation_run=true`,
`generation_behavior_changed=true`; `distinct_inserted_asset_count >= 3` with
`asset_tokens_inserted_count >= 3`, `same_single_table_figure_output=false`,
`not_byte_identical_to_prior_single_asset_output=true`, `orphan_asset_token_count=0`,
`duplicate_inserted_asset_count=0`, `all_available_useful_descriptors_considered=true`;
`tables_rendered_as_real_tables=true`, `tables_inserted_as_images=false`;
private guide + HTML written and gitignored; no raw private path, no broken image,
no data image / base64; OCR/Chandra/cloud-OCR not used, no numeric verification,
no frontend/API change, judge/repair not ready;
`recommended_next_step=operator_read_multi_asset_generated_guide`.

## Honest block conditions

Missing input artifacts; fewer than three ready descriptors; provider
unavailable; writer generation fails; output repeats only the same accepted
table + figure; fewer than three inserted assets; orphan tokens remain;
duplicate insertion; a table inserted as an image; a figure requiring
data:image/base64; a raw private path in the render; or any attempt to become a
wrapper/seam/hook/manifest/consumer/coverage packet or to rerun OCR/Chandra/cloud
OCR.

## Scope guarantees (what 177G does NOT do)

Off-by-default and private only. No frontend/API change. No normal-generation
default change. No guide regeneration outside the explicit private runner. No
judge, no repair. No cloud OCR, no Chandra, no OCR rerun, no coverage-eval rerun.
No numeric-verification claim. No all-assets-solved claim (it does not claim full
asset support; the operator must validate the rendered guide). No broad production
asset registry, scanner, or auto-discovery.

## Operator validation (required before any commit)

The operator must open the private rendered HTML and confirm: it reads as a real
generated study guide; it is **not** the same single-table/single-figure output as
before; at least 3 distinct assets are inserted; each inserted asset has a real
explanation beneath it; tables are real reconstructed/simplified tables (not
screenshots); non-table figures have useful explanation/how-to-read/exam takeaway;
no orphan `{{asset:...}}` tokens; no duplicate insertions; no broken image; no
visible raw private path; and the guide remains useful for studying. The private
guide path is shown only on the runner's stderr — it is never copied into committed
docs. **Do not commit 177G until the operator confirms.**
