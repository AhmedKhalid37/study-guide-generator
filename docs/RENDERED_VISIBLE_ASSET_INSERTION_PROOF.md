# Rendered Reconstructed Table Proof

Slice 176U pivots from OCR coverage research to student-visible value. Slice
176T showed the candidate_1 local OCR attempt ran through `tesseract_cli` but did
not improve extraction reliability over 176R, so this slice uses existing
recovered structured table assets instead of running more OCR.

Scope:

- existing private recovered table artifacts only
- private reconstructed-table guide/render proof only
- no provider generation
- no guide generation
- no OCR rerun
- no coverage evaluation
- no cloud OCR
- no normal generation behavior change
- no frontend/API wiring
- no new LLM judge, Layer-2 judge, or repair
- no raw source/OCR/guide/table/caption/prompt/response/provider payload content
  committed
- table-as-image insertion cannot count as success
- markdown-only output is not a completed proof
- completed status requires rendered HTML/PDF visibility of a table

Closed Slice 176U result:

- `artifact_name=rendered_reconstructed_table_proof`
- `status=completed`
- `source_label=ensemble`
- `private_visible_artifact_available=true`
- `private_visible_artifact_gitignored=true`
- `private_guide_source_available=true`
- `private_guide_source_gitignored=true`
- `private_rendered_guide_written=true`
- `private_rendered_guide_gitignored=true`
- `selected_asset_category=patient_dataset_table`
- `selected_asset_kind=table`
- `selected_asset_role=display_only`
- `insertion_mode=private_markdown_table`
- `table_inserted_as_image=false`
- `render_format=html`
- `render_status=rendered`
- `asset_visibility_status=visible`
- `export_visibility_status=visible`
- `raw_asset_committed=false`
- `raw_guide_committed=false`
- `raw_ocr_committed=false`
- `raw_table_text_committed=false`
- `raw_caption_text_committed=false`
- `rendered_guide_committed=false`
- `prompts_committed=false`
- `responses_committed=false`
- `provider_payloads_committed=false`
- `provider_call_made=false`
- `generation_rerun=false`
- `ocr_rerun=false`
- `coverage_eval_rerun=false`
- `cloud_ocr_used=false`
- `numeric_verification_claimed=false`
- `generation_behavior_changed=false`
- `frontend_api_changed=false`
- `blocked_by=none`
- `phase4_next_requirement=add_explanation_beneath_asset`
- `recommended_next_step=inspect_private_rendered_reconstructed_table_guide`

Interpretation: one recovered display-only patient-dataset table from existing
private visible/OCR artifacts was inserted as a reconstructed Markdown table and
rendered visibly in a private HTML guide artifact. Numeric verification is not
claimed. This slice is the mechanical rendered-table proof only.

Operator inspection (closed note):

- `operator_private_rendered_html_inspection=done`
- `operator_table_readability=acceptable`
- `operator_table_readability_note=all_tables_are_readable`
- `operator_table_faithfulness=not_formally_claimed`

The operator manually opened the private rendered HTML guide and confirmed all
tables are readable. This manual inspection is the inspection producer for 176U.
No automated rendered-table inspection module was or will be built: a parser can
only re-confirm table tags and cannot judge real readability or faithfulness.
Exact table-cell faithfulness is not claimed.

Next Phase 4 requirements (the readability gate is now satisfied, so the next
built slice is table-companion work, not another inspection step):

- add an explanation beneath the inserted asset
- for tables, show the faithful reconstructed table plus a simplified clearer
  study-friendly version alongside it

The next route is the Phase 4 reconstructed-table companion slice
(`add_explanation_beneath_asset` / `add_faithful_table_plus_simplified_version`),
not another broad OCR coverage slice and not an automated inspection harness.
