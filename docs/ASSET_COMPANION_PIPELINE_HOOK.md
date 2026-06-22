# Asset Companion Pipeline Hook

Slice 177E proves a default-off dry-run hook can call the 177D asset-companion
insertion seam from the guide-Markdown-before-render shape of the normal pipeline.

This is private/off-by-default only. It does not expose frontend/API behavior, does
not enable the feature for normal users, and does not change normal-generation
defaults. It does not call a provider/model, regenerate a guide, run OCR, run cloud
OCR, run Chandra, run broad OCR, add judge/repair, perform numeric verification, or
claim all assets are solved.

## Scope

- 177D proved the off-by-default insertion seam.
- 177E proves a default-off normal-pipeline dry-run hook can call that seam.
- Normal/default mode keeps the hook disabled and returns guide Markdown unchanged.
- The private runner is the only caller that explicitly enables the hook.
- This proves one private dry-run hook only, not a broad asset framework.

## Implementation

- `pipeline/asset_companion_pipeline_hook.py`
  - `default_asset_companion_pipeline_hook_config()` returns disabled config.
  - `apply_asset_companion_pipeline_hook(...)` returns unchanged Markdown unless
    both `enabled` and `private_runner_enabled` are true.
  - Enabled private mode calls `asset_companion_insertion_177d`.
  - The runner validates accepted combined companion structure before rendering.
- `test_scripts/run_asset_companion_pipeline_hook_private.py`
  - Explicit private opt-in only.
  - Prints a committed-safe closed summary.
- `test_scripts/test_asset_companion_pipeline_hook.py`
  - Public-safe synthetic fixtures only.

## Closed Private Result

`artifact_name=asset_companion_pipeline_hook` · `slice=177E` · `status=completed` ·
`source_label=ensemble` · `off_by_default=true` ·
`normal_generation_default_unchanged=true` · `default_hook_enabled=false` ·
`private_hook_enabled=true` · `private_runner_enabled=true` ·
`hook_location_closed=guide_markdown_before_render` ·
`hook_invoked_from_private_runner=true` ·
`hook_invoked_from_normal_generation=false` · `disabled_path_byte_identical=true` ·
`enabled_path_called_insertion_seam=true` ·
`insertion_seam_source=asset_companion_insertion_177d` ·
`input_full_guide_source=private_ensemble_full_guide_markdown` ·
`input_full_guide_available=true` · `input_full_guide_gitignored=true` ·
`combined_companion_source=private_177b_combined_asset_companion` ·
`combined_companion_available=true` · `combined_companion_gitignored=true` ·
`asset_companion_section_inserted=true` · `insertion_location=appended_at_end` ·
`relative_asset_refs_preserved=true` · `private_hook_render_written=true` ·
`private_hook_render_gitignored=true` · `render_format=html` ·
`render_status=rendered` · `normal_guide_content_present=true` ·
`table_companion_inserted=true` · `faithful_table_present=true` ·
`table_explanation_present=true` · `role_aware_simplified_table_present=true` ·
`simplified_table_is_row_reduced_copy=false` ·
`simplified_table_is_study_oriented=true` · `figure_companion_inserted=true` ·
`figure_visual_present=true` ·
`figure_visual_type_closed=flow_or_structure_diagram` ·
`figure_visual_is_non_table_figure=true` · `figure_visual_is_text_only=false` ·
`figure_visual_is_partial_sliver=false` · `figure_visual_is_table_like=false` ·
`figure_visual_is_matrix=false` · `figure_visual_is_grid=false` ·
`figure_explanation_present=true` · `figure_reading_steps_present=true` ·
`figure_exam_takeaway_present=true` · `raw_private_paths_in_rendered_html=false` ·
`broken_image_marker_detected=false` · `data_image_used=false` ·
`base64_image_used=false` · `provider_call_made=false` · `generation_rerun=false` ·
`generation_behavior_changed=false` · `cloud_ocr_used=false` · `ocr_rerun=false` ·
`coverage_eval_rerun=false` · `numeric_verification_claimed=false` ·
`frontend_api_changed=false` · `judge_ready=false` · `repair_ready=false` ·
`operator_private_read_required=true` · `operator_private_read_done=false` ·
`blocked_by=none` · `recommended_next_step=operator_read_private_pipeline_hook_output`.

## Operator Review

Operator private read is required. Confirm the private HTML reads as a full guide, the
companion section appears, the accepted table companion appears, the accepted non-table
figure companion appears, the relative image renders, there is no broken image marker,
there is no visible raw private path, and the guide remains readable.
