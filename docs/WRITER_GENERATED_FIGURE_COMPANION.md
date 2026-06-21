# Writer-Generated Figure Companion

Slice 176Y adds the descriptor-driven figure/diagram companion proof. It mirrors
the 176W/176X table companion path, but selects one existing recovered visual
asset descriptor and asks the writer to produce a student-facing explanation
beneath a single visual token.

Committed outputs stay closed-label only. Raw descriptor JSON, recovered figure
text, captions, table/grid content, screenshots, prompt text, provider responses,
private paths, hashes, and byte counts must remain in ignored private artifacts.

## Scope

- Uses an existing private visible-asset descriptor.
- Gives the writer descriptor/context only; the writer does not inspect images.
- Resolves one writer token to a safe rendered visual in private HTML.
- Supports safe relative private image references or recreated non-table diagrams.
- Does not change frontend/API behavior or normal guide generation.
- Does not add judges, repair, OCR reruns, cloud OCR, Chandra reruns, or numeric verification.

## Slice 176Y Corrected Run Status

Operator review rejected the earlier rendered companion because the selected
visual was table/grid-like. The corrected selector excludes tables, matrices,
grids, proximity matrices, dataset tables, and structured table/grid assets.

Inspection of the existing private visible-asset artifact found no acceptable
non-table figure/diagram descriptor. The corrected private runner therefore
blocked honestly and did not call a provider or render a new figure proof.

Closed real-run summary:

- `artifact_name=writer_generated_figure_companion`
- `slice=176Y`
- `status=blocked`
- `source_label=ensemble`
- `selected_asset_category=none`
- `selected_asset_kind=unknown`
- `selected_asset_role=study_visual`
- `asset_descriptor_source=private_visible_asset_inventory`
- `writer_input_descriptor_present=false`
- `provider_call_made=false`
- `generation_rerun=false`
- `generation_behavior_changed=false`
- `visual_inserted=false`
- `visual_insertion_mode=blocked`
- `visual_is_table_like=false`
- `visual_is_matrix=false`
- `visual_is_grid=false`
- `visual_inserted_as_raw_private_path=false`
- `explanation_beneath_asset_present=false`
- `study_reading_steps_present=false`
- `render_format=not_run`
- `render_status=not_run`
- `private_rendered_guide_written=false`
- `private_run_closed_summary_written=true`
- `figure_diagram_companion_status=not_produced`
- `table_like_visual_companion_status=completed_but_not_counted_for_figure_gate`
- `operator_private_read_required=false`
- `operator_private_read_done=false`
- `numeric_verification_claimed=false`
- `frontend_api_changed=false`
- `judge_ready=false`
- `repair_ready=false`
- `blocked_by=no_existing_non_table_figure_descriptor`
- `recommended_next_step=produce_private_non_table_figure_descriptor_from_existing_extraction`
