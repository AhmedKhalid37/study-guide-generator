# WRITER_GENERATED_TABLE_COMPANION.md — Slice 176X

> Closed-label record only. No raw guide/source/OCR/table/caption/explanation/
> simplified-table text, no prompts/responses, no provider payloads, no private
> paths, filenames, hashes, byte counts, or screenshots. Private rendered output
> stays gitignored.

## What this slice is

Slice 176X keeps the Slice 176W writer/provider path but changes the simplified-table
semantics to match the operator clarification:

`operator_clarified_simplified_table_semantics=study_explanation_not_row_reduction`.

The writer still receives the existing private recovered table as a closed extracted
descriptor, inserts `{{table:patient_dataset}}` exactly once, writes a genuine
explanation beneath it, and emits a writer-generated simplified Markdown table. The
new requirement is role-aware study simplification:

- terminology/definition tables -> `Term or concept | Simple meaning | What to remember / exam clue`
- comparison tables -> `Item | Main difference | When it matters / common mistake`
- process/steps tables -> `Step | Plain-English action | Why it matters`
- formula/reference tables -> `Item | Meaning | How to use it`
- dataset/numeric tables -> `Pattern / thing to notice | Meaning | Exam takeaway`

For the existing patient dataset case, completion now requires a study-interpretation
table, not a row subset or column-trimmed copy.

## Modules

- `pipeline/writer_generated_table_companion.py` — producer + closed summary builder.
- `test_scripts/run_writer_generated_table_companion.py` — private runner.
- `test_scripts/test_writer_generated_table_companion.py` — public-safe synthetic tests.

## Contract / honest blocking

| Condition | Result |
| --- | --- |
| Provider config unavailable | `blocked` · `blocked_by=provider_unavailable` |
| Generation call fails | `blocked` · `blocked_by=writer_generation_unavailable` |
| Writer emits 0 tokens | `blocked` · `blocked_by=writer_token_missing` |
| Writer emits >=2 tokens | `blocked` · `blocked_by=writer_token_duplicate` |
| Explanation missing/placeholder | `blocked` · `blocked_by=placeholder_content_detected` |
| Simplified table missing/placeholder/copy/column-trimmed subset/wrong role shape | `blocked` · `blocked_by=placeholder_content_detected` |
| One token + real explanation + role-aware study table, rendered and operator-read | `completed` · `recommended_next_step=commit_slice_176x_only` |

The deterministic simplification from Slice 176V is not reused as the main simplified
version. Completion requires `simplified_table_source=writer_generated_from_descriptor`.
Quality and numeric faithfulness are routed to private operator review; code keeps
`numeric_verification_claimed=false`, `judge_ready=false`, and `repair_ready=false`.

## Real run

Closed summary from the required private patient-dataset rerun:

`artifact_name=writer_generated_table_companion` · `slice=176X` · `status=completed` ·
`source_label=ensemble` · `selected_asset_category=patient_dataset_table` ·
`selected_asset_kind=table` · `provider_call_made=true` · `generation_rerun=true` ·
`generation_behavior_changed=true` · `writer_token_present=true` ·
`writer_token_count=1` · `writer_token_inserted_by_writer=true` ·
`postprocessor_token_injected=false` · `faithful_table_present=true` ·
`table_inserted_as_image=false` · `explanation_beneath_asset_present=true` ·
`explanation_source=writer_generated_from_descriptor` ·
`explanation_non_placeholder=true` · `simplified_table_present=true` ·
`simplified_table_source=writer_generated_from_descriptor` ·
`simplified_table_non_placeholder=true` ·
`simplified_table_policy=role_aware_study_simplification` ·
`detected_or_requested_table_role=dataset_numeric` ·
`simplified_table_shape=dataset_patterns_takeaways` ·
`simplified_table_is_row_reduced_copy=false` ·
`simplified_table_is_study_oriented=true` ·
`simplified_table_preserves_key_meaning=true` · `render_format=html` ·
`render_status=rendered` · `private_rendered_guide_written=true` ·
`private_rendered_guide_gitignored=true` ·
`faithful_table_visibility_status=visible` ·
`explanation_visibility_status=visible` ·
`simplified_table_visibility_status=visible` ·
`operator_private_read_required=true` · `operator_private_read_done=true` ·
`operator_table_readability=acceptable` ·
`operator_explanation_quality=acceptable` ·
`operator_simplified_table_quality=acceptable` ·
`operator_simplified_table_semantics=accepted_role_aware_study_simplification` ·
`numeric_verification_claimed=false` · `frontend_api_changed=false` ·
`judge_ready=false` · `repair_ready=false` · `blocked_by=none` ·
`recommended_next_step=commit_slice_176x_only`.

Closed rendered-structure check: `table_count=2` · `leftover_token=false` ·
`has_img=false` · `has_data_image=false`.

Optional real terminology case:
`terminology_table_real_case_status=unavailable_existing_artifact_not_found`.

Operator private read:
`operator_private_read_done=true` · `faithful_table_visibility_status=visible` ·
`explanation_visibility_status=visible` · `simplified_table_visibility_status=visible` ·
`operator_table_readability=acceptable` · `operator_explanation_quality=acceptable` ·
`operator_simplified_table_quality=acceptable` ·
`operator_simplified_table_semantics=accepted_role_aware_study_simplification`.
Operator note: simplified table is not a row-reduced copy; it is study-oriented.

## Validation

`python -m compileall api pipeline test_scripts` OK ·
`test_writer_generated_table_companion` OK ·
`test_reconstructed_table_companion` OK ·
`test_rendered_visible_asset_insertion_proof` OK ·
`test_visible_table_figure_pilot` OK · `git diff --check` clean · no-leak sweep clean.
Docker was not run.

## Out of scope

OCR rerun, `candidate_1` work, coverage eval, new judge/evaluator/repair loop,
frontend/API rollout, Chandra path, cloud OCR, figure assets, and numeric
verification.
