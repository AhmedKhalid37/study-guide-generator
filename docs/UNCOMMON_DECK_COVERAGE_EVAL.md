# Uncommon-Deck Coverage Eval

Slice 176S follows Slice 176R: `candidate_1` now has a private local
extraction artifact produced with `local_ocr_engine=text_layer`. This slice
compares existing private baseline/generated guides against closed marker IDs
from that artifact. It does not rerun OCR and does not run generation.

Scope:

- existing private artifacts only
- no provider generation
- no guide generation
- no packaging-v2
- no OCR rerun
- no baseline generation
- no official scorer mutation
- no new LLM judge, Layer-2 judge, or repair
- no cloud OCR
- no frontend/API wiring
- no raw source/OCR/guide/table/caption/prompt/response/provider payload content
  committed

The result is diagnostic because 176R produced only partial marker candidates
from closed static IDs. The generated guide covers more of those weak markers
than the baseline, but marker reliability is low, so this is not strong enough
to justify a provider-generation test.

Closed Slice 176S result:

- `artifact_name=uncommon_deck_coverage_eval`
- `status=degraded`
- `source_label=candidate_1`
- `candidate_type=uncommon_course_deck`
- `private_baseline_guide_available=true`
- `private_baseline_guide_gitignored=true`
- `private_generated_guide_available=true`
- `private_generated_guide_gitignored=true`
- `private_ocr_artifact_available=true`
- `private_ocr_artifact_gitignored=true`
- `provider_call_made=false`
- `generation_rerun=false`
- `ocr_rerun=false`
- `marker_source=closed_static_ids`
- `marker_candidate_status=partial`
- `marker_count_bucket=low`
- `baseline_deck_specific_coverage=low`
- `generated_deck_specific_coverage=high`
- `deck_specific_coverage_delta=improved`
- `recovered_content_usage_delta=improved`
- `active_recall_from_recovered_content_delta=unavailable`
- `coverage_eval_role=diagnostic`
- `marker_reliability=low`
- `should_run_provider_generation=not_yet`
- `should_run_better_ocr=yes`
- `recommended_next_step=improve_candidate_1_ocr_extraction`

Interpretation: the closed comparison is directionally positive for the
generated guide, but the marker source is too weak to bank as official coverage
evidence. The next route is better candidate_1 extraction, not provider
generation and not scorer-threshold changes.
