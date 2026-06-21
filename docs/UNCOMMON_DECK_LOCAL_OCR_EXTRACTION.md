# Uncommon-Deck Local OCR Extraction

Slice 176R follows Slice 176Q: `candidate_1` has private source and guide
artifacts, but no OCR artifact or closed marker candidates. This slice produces
that missing private OCR artifact and emits only a closed extraction summary.

Scope:

- local OCR/text extraction only
- no provider generation
- no guide generation
- no baseline generation
- no coverage evaluation yet
- no cloud OCR
- no frame-selection pipeline
- no new LLM judge, Layer-2 judge, or repair
- no frontend/API wiring
- no raw source/OCR/guide/table/caption/prompt/response/provider payload content
  committed

The runner is env-driven and carries no private source or artifact paths in code.
Raw extracted content is written only under a confirmed private artifact directory.
The committed summary records closed labels only: status, engine/status labels,
coarse count buckets, redundancy labels, marker readiness, and the next route.
For `candidate_1`, the local engine was `text_layer`; this slice does not claim
that Chandra/local structured OCR ran for the uncommon deck.

Closed Slice 176R result:

- `status=degraded`
- `source_label=candidate_1`
- `candidate_type=uncommon_course_deck`
- `private_source_available=true`
- `private_source_gitignored=true`
- `private_ocr_artifact_written=true`
- `private_ocr_artifact_gitignored=true`
- `cloud_ocr_used=false`
- `provider_call_made=false`
- `generation_rerun=false`
- `ocr_rerun=true`
- `local_ocr_engine=text_layer`
- `local_ocr_status=ran`
- `slide_redundancy=unknown`
- `frame_dedup_mode=auto`
- `resolved_frame_dedup=off`
- `expensive_frame_selection_built=false`
- `pages_considered_count_bucket=low`
- `pages_extracted_count_bucket=low`
- `extracted_text_block_count_bucket=low`
- `extracted_table_count_bucket=none`
- `extracted_figure_or_diagram_count_bucket=none`
- `marker_candidate_status=partial`
- `marker_source=closed_static_ids`
- `next_test_readiness=ready_for_uncommon_deck_coverage_eval`
- `blocked_by=none`
- `recommended_next_step=run_uncommon_deck_coverage_eval_existing_artifacts`

Closed readiness rule:

- if a private OCR artifact is written and marker candidates are available or
  partial, the next step is `run_uncommon_deck_coverage_eval_existing_artifacts`
- if extraction runs but markers are too weak, the next step is
  `improve_uncommon_deck_ocr_extraction`
- if local OCR is unavailable, the slice reports the closed blocker and does not
  use cloud OCR
- if source or artifact paths are unsafe, the slice blocks without writing raw
  content

Validation passed: `compileall api pipeline test_scripts`,
`test_uncommon_deck_local_ocr_extraction`,
`test_uncommon_deck_ocr_value_diagnostic`, `test_slide_redundancy_detector`,
`test_slide_raster_ocr_ingestion`, private 176R runner, and `git diff --check`.
