# Slice 177C — Full-guide private preview with the combined asset companion inserted

> Narrow private preview producer. Off-by-default. No frontend/API behavior, no
> normal production guide-generation behavior, no provider call, no judge/repair,
> no cloud OCR / Chandra / broad OCR, no numeric verification, no all-assets claim.

## What this slice proves

177B combined the **accepted** 176X table companion and the **accepted** 177A
non-table figure companion into one standalone private rendered guide. **177C takes
that accepted 177B combined companion and inserts it into an existing real private
generated study guide (same ensemble lineage), then renders one private HTML
preview.**

This proves the accepted table+figure companion can live inside a **realistic full
study guide artifact**, not only in a standalone companion document. It proves
**one** private full-guide asset-companion preview only — it does **not** claim all
figures or all tables in the guide are solved, and it does **not** ship any
frontend/API behavior.

## Lineage

- **176X** — role-aware table simplification (faithful table + explanation +
  study-oriented simplified table that is not a row-reduced copy).
- **177A** — one writer-generated **non-table** figure companion (visible non-table
  visual + explanation + reading steps + exam takeaway).
- **177B** — composed the accepted 176X + 177A outputs into one private rendered
  combined companion guide (committed/merged/pushed on trunk `chrome-renderer-v1`).
- **177C** (this slice) — inserts the accepted 177B combined companion into an
  existing private full generated guide and renders a private full-guide preview.

## Module / files

- `pipeline/full_guide_asset_companion_preview.py` —
  `run_full_guide_asset_companion_preview(...)` / `main()`. Narrow private
  preview producer; **no new asset framework.** Reuses helpers from
  `pipeline/combined_asset_companion_guide.py` (`_markdown_table_count`,
  `_has_data_uri`, `_render_has_private_path`, image-ref regexes, data-URI markers)
  and `is_private_artifact_dir` / `render_markdown`.
- `test_scripts/run_full_guide_asset_companion_preview.py` — private runner
  (env: `PRIVATE_FULL_GUIDE_PATH`, `PRIVATE_COMBINED_DIR`,
  `PRIVATE_FULL_PREVIEW_DIR`).
- `test_scripts/test_full_guide_asset_companion_preview.py` — public-safe synthetic
  tests.

## Behavior

1. Load the existing private full generated guide (preferred: an existing private
   generated guide already used in the OCR-context/ensemble sequence). Block
   honestly if missing.
2. Load the accepted private 177B combined companion (its combined Markdown + closed
   summary). Verify it carries an accepted **table** block and an accepted
   **non-table figure** block; verify the simplified table is study-oriented and
   **not** a row-reduced copy, and that the figure is never table-like / matrix /
   grid / text-only / partial-sliver.
3. Compose a private full-guide preview: the original guide content is preserved
   verbatim, and the accepted companion is inserted under a deterministic trailing
   `# Recovered visual/table companions` section (clear placement/section
   separation, never disturbing existing guide sections).
4. Copy the companion figure asset as a safe private-relative `assets/<name>` image,
   preserving relative references; refuse `data:`/base64; refuse any raw private
   path that would land in the render.
5. Render to private HTML and write the private preview artifacts. Emit a closed
   committed-safe summary only.

## Honest blocks

`full_guide_not_found`, `combined_companion_not_found`,
`combined_companion_missing_table`, `combined_companion_missing_figure`,
`combined_companion_figure_table_like`, `combined_companion_table_row_reduced`,
`relative_assets_unavailable`, `data_uri_or_base64_refused`,
`raw_private_path_in_render`, `unsafe_private_artifact_path`, `render_failed`.

## Safety / no-leak posture

Committed output is a **closed summary only**. No raw guide / table / figure /
caption / source / OCR text, no descriptor JSON, no image bytes, no `data:`/base64,
no prompts/responses/provider payloads, no private paths, no source filenames, no
hashes or byte counts appear in committed files. The no-leak assert scans summary
**values** (keys such as `base64_image_used` are controlled closed vocabulary). The
private preview HTML + assets live under the gitignored private dir; the path is
handed to the operator out-of-band, never in docs.

## Operator review (required before any commit)

The operator opens the private preview HTML and confirms:

- it looks like a **full guide**, not only the companion section;
- the accepted table companion appears (faithful table + explanation + role-aware
  study simplified table);
- the accepted **non-table** figure companion appears (visible diagram + explanation
  + reading steps + exam takeaway);
- the relative image renders with no broken-image indicator;
- no visible raw private path;
- the guide remains readable.

177C is **not committed** by the implementer: it stops for operator visual review of
the private full-guide preview HTML before any commit.
