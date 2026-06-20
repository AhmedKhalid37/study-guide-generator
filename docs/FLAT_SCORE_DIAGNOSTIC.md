# Flat-Score Diagnostic

Slice 176O diagnoses Slice 176N's unchanged real OCR-context generation score
before any packaging iteration. It compares the existing private 176N guide with
the private baseline guide and inspects the existing scorer's coverage semantics.

Scope:

- no provider generation rerun
- no provider call
- no packaging-v2 generation
- no new evaluator, judge, Layer-2 judge, or repair
- no cloud OCR
- no frontend/API wiring
- no scorer threshold tuning
- no raw guide/OCR/table/caption/prompt/response/provider payload content committed

The diagnostic emits only closed fields:

- `guide_content_difference`
- `ocr_specific_content_added`
- `visible_asset_difference`
- `scorer_coverage_semantics`
- `scorer_structure_weight`
- `scorer_deck_specific_weight`
- `eval_insensitive_likelihood`
- `model_prior_likelihood`
- `packaging_weak_likelihood`
- `flat_score_explanation`
- `recommended_next_step`

176N's unchanged score remains load-bearing negative evidence. Packaging-v2 is
only the next route if the diagnostic supports `packaging_weak`. If the scorer is
mostly structural and deck-specific weight is low, the next route is
`add_deck_specific_coverage_eval` rather than another generation run.

Banked 176O result:

- `status=completed`
- `private_baseline_guide_available=true`
- `private_baseline_guide_gitignored=true`
- `private_176n_guide_available=true`
- `private_176n_guide_gitignored=true`
- `private_score_artifacts_available=true`
- `private_score_artifacts_gitignored=true`
- `generation_rerun=false`
- `provider_call_made=false`
- `guide_content_difference=high`
- `ocr_specific_content_added=partial`
- `visible_asset_difference=medium`
- `scorer_coverage_semantics=structural_contract`
- `scorer_structure_weight=high`
- `scorer_deck_specific_weight=low`
- `eval_insensitive_likelihood=high`
- `model_prior_likelihood=low`
- `packaging_weak_likelihood=low`
- `flat_score_explanation=eval_insensitive`
- `recommended_next_step=add_deck_specific_coverage_eval`
