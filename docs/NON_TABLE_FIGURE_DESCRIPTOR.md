# Non-Table Figure Descriptor

## Slice 176Z

Slice 176Z produces the missing private descriptor for one actual non-table
visual asset so a later writer-generated figure companion can run on a valid
figure/diagram input.

Operator review rejected the previous selected crop because it was text-only or
from the wrong source. The target visual type for this correction is the
ensemble structure diagram.

176Y is the required guardrail: table, matrix, grid, proximity-matrix,
dataset-table, dataframe, structured-grid, scanned-table, and other row/column
cell assets cannot satisfy the figure companion gate. A table-like asset may be
useful elsewhere, but it is not a figure descriptor.

## Scope

- Private artifact only: `non_table_figure_descriptor.json` is written under a
  gitignored/private output directory.
- Closed summary only: committed docs and printed summaries include only closed
  labels and booleans.
- No provider/model generation, no writer companion run, no OCR rerun, no cloud
  OCR, no Chandra, no frontend/API behavior, no judge, and no repair path.

## Real Run

Closed result:

- `artifact_name=non_table_figure_descriptor`
- `slice=176Z`
- `status=completed`
- `source_label=ensemble`
- `candidate_source=private_source_deck`
- `candidate_scan_mode=pdf_local_geometry_crop`
- `selected_asset_category=ensemble_structure_diagram`
- `selected_asset_kind=conceptual_diagram`
- `selected_asset_role=study_visual`
- `operator_rejected_previous_crop_reason=text_only_or_wrong_source`
- `operator_target_visual_type=ensemble_structure_diagram`
- `descriptor_written=true`
- `descriptor_gitignored=true`
- `private_visual_asset_available=true`
- `private_visual_asset_gitignored=true`
- `visual_is_table_like=false`
- `visual_is_matrix=false`
- `visual_is_grid=false`
- `visual_is_text_only=false`
- `visual_is_partial_sliver=false`
- `visual_source_matches_label=true`
- `visual_is_non_table_figure=true`
- `visual_type_closed=flow_or_structure_diagram`
- `visual_descriptor_readiness=ready_for_writer_companion`
- `figure_companion_input_ready=true`
- `provider_call_made=false`
- `generation_rerun=false`
- `generation_behavior_changed=false`
- `ocr_rerun=false`
- `cloud_ocr_used=false`
- `chandra_used=false`
- `frontend_api_changed=false`
- `numeric_verification_claimed=false`
- `judge_ready=false`
- `repair_ready=false`
- `blocked_by=none`
- `recommended_next_step=run_writer_generated_figure_companion_on_non_table_descriptor`

This slice does not complete the writer-generated figure companion. The next
slice should run the writer figure companion on the private non-table descriptor,
without counting table/matrix/grid assets as success.
