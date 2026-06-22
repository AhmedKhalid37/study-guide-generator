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

## Slice 177A — Companion on the accepted 176Z non-table descriptor

The 176Y block was honest: the visible-asset inventory held no acceptable
non-table figure. Slice 176Z then produced the missing input — one private
non-table figure descriptor for a real **ensemble structure diagram** (Training
Data → learners/models → model combiner → final model), operator-accepted as a
flow/structure diagram (not text, not a sliver, source matches the `ensemble`
label, not table/matrix/grid).

Slice 177A consumes that accepted 176Z descriptor to produce the **first
writer-generated non-table figure companion**:

- New entrypoint `run_writer_figure_companion_from_descriptor(...)` (and
  `main_177a()` / `WRITER_COMPANION_MODE=descriptor_177a` in the runner).
- Reads the accepted 176Z descriptor JSON from gitignored private storage only.
- Refuses anything off-contract: missing descriptor, table/matrix/grid,
  text-only, partial sliver, or a non-`ensemble` source label.
- Inserts the recovered private crop as a **safe private-relative image asset**
  (`assets/<category>.png`, copied into the private companion dir). No inlined
  image bytes, no `data:`/base64, no raw absolute private path in the render.
- Calls the existing configured provider/model writer path **once**; the writer
  receives the descriptor/context only and never sees the image.
- The writer emits an explanation beneath the visual, how-to-read reading steps,
  an exam takeaway / study cue, and a blank-label practice seed.
- Renders private HTML for operator inspection and emits a closed summary only.

This proves **one** figure/diagram companion path end-to-end — it does not claim
all figures are solved. No frontend/API change, no judge, no repair, no cloud
OCR, no Chandra, no OCR/coverage reruns, no numeric verification.

### Slice 177A real-run closed summary (operator review pending)

- `artifact_name=writer_generated_figure_companion`
- `slice=177A`
- `status=completed`
- `source_label=ensemble`
- `selected_asset_category=ensemble_structure_diagram`
- `selected_asset_kind=conceptual_diagram`
- `selected_asset_role=study_visual`
- `visual_type_closed=flow_or_structure_diagram`
- `asset_descriptor_source=private_176z_non_table_figure_descriptor`
- `writer_input_descriptor_present=true`
- `writer_saw_image=false`
- `provider_call_made=true`
- `provider_name_closed=deepseek`
- `generation_rerun=true`
- `generation_behavior_changed=true`
- `visual_inserted=true`
- `visual_insertion_mode=image_asset`
- `visual_is_non_table_figure=true`
- `visual_is_text_only=false`
- `visual_is_partial_sliver=false`
- `visual_source_matches_label=true`
- `visual_is_table_like=false` · `visual_is_matrix=false` · `visual_is_grid=false`
- `visual_inserted_as_raw_private_path=false`
- `explanation_beneath_asset_present=true`
- `explanation_non_placeholder=true`
- `study_reading_steps_present=true`
- `exam_takeaway_present=true`
- `blank_label_practice_seed_present=true`
- `render_format=html` · `render_status=rendered`
- `private_rendered_guide_written=true` · `private_rendered_guide_gitignored=true`
- `visual_visibility_status=operator_pending` · `explanation_visibility_status=operator_pending`
- `operator_private_read_required=true` · `operator_private_read_done=false`
- `numeric_verification_claimed=false` · `frontend_api_changed=false`
- `judge_ready=false` · `repair_ready=false`
- `blocked_by=none`
- `recommended_next_step=operator_read_private_rendered_figure_companion`

Not committed: the slice stops here for operator review. The operator must open
the private rendered HTML and confirm the visual is the ensemble structure
diagram, the explanation sits beneath it, the reading/study steps are useful, no
table/matrix/text crop was used, and there is no hallucination or self-talk.
