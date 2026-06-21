# Candidate_1 Structured OCR Attempt

Slice 176T follows Slice 176S: candidate_1 coverage improved over baseline on
weak closed static markers, but `marker_reliability=low`, so the result is only
diagnostic. This slice attempts to improve candidate_1 extraction through
existing local OCR routes and emits only a committed-safe closed summary.

Scope:

- local OCR/extraction attempt only
- no provider generation
- no guide generation
- no coverage evaluation
- no baseline generation
- no cloud OCR
- no broad OCR framework
- no new LLM judge, Layer-2 judge, or repair
- no frontend/API wiring
- no raw source/OCR/guide/table/caption/prompt/response/provider payload content
  committed

Closed Slice 176T result:

- `artifact_name=candidate1_structured_ocr_attempt`
- `status=degraded`
- `source_label=candidate_1`
- `candidate_type=uncommon_course_deck`
- `previous_extraction_engine=text_layer`
- `previous_marker_reliability=low`
- `private_source_available=true`
- `private_source_gitignored=true`
- `private_improved_ocr_artifact_written=false`
- `private_improved_ocr_artifact_gitignored=false`
- `raw_source_committed=false`
- `raw_ocr_committed=false`
- `raw_table_text_committed=false`
- `raw_caption_text_committed=false`
- `rendered_images_committed=false`
- `source_pdf_committed=false`
- `prompts_committed=false`
- `responses_committed=false`
- `provider_payloads_committed=false`
- `cloud_ocr_used=false`
- `provider_call_made=false`
- `generation_rerun=false`
- `coverage_eval_rerun=false`
- `ocr_rerun=true`
- `attempted_structured_ocr=true`
- `structured_ocr_engine=tesseract_cli`
- `structured_ocr_status=ran`
- `fallback_engine=none`
- `local_ocr_engine=tesseract_cli`
- `local_ocr_status=ran`
- `pages_considered_count_bucket=low`
- `pages_extracted_count_bucket=low`
- `extracted_text_block_count_bucket=low`
- `extracted_table_count_bucket=none`
- `extracted_figure_or_diagram_count_bucket=none`
- `marker_candidate_status=partial`
- `marker_source=private_artifact_categories`
- `marker_reliability=low`
- `improvement_over_176r=no`
- `next_test_readiness=needs_better_ocr`
- `blocked_by=none`
- `recommended_next_step=pivot_to_rendered_visible_asset_insertion`

Interpretation: the local tesseract attempt ran on candidate_1 but did not
recover table/figure-like structure and did not improve marker reliability over
the 176R text-layer artifact. Do not claim the OCR coverage thesis is proven on
candidate_1 and do not run provider generation from this result. The next route
is a visible-asset insertion pivot or a better uncommon fixture, not another
broad OCR setup slice without a concrete local-engine gap.
