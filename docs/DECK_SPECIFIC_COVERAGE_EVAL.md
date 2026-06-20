# Deck-Specific Coverage Eval

Slice 176P adds a deterministic deck-specific coverage diagnostic because 176O
found the existing 176N score was `eval_insensitive`: the scorer coverage path is
mostly `structural_contract`, with high structure weight and low deck-specific
weight.

Scope:

- no provider generation rerun
- no provider call
- no packaging-v2 generation
- no new LLM judge, Layer-2 judge, or repair
- no cloud OCR
- no frontend/API wiring
- no scorer threshold tuning
- no official scorer replacement in this slice
- no raw guide/OCR/table/caption/prompt/response/provider payload content committed

The eval compares the private baseline guide and private 176N OCR-context guide
against closed marker IDs derived from private OCR and visible-artifact categories.
Committed docs and code contain only closed marker IDs and closed statuses:
`present`, `partial`, `absent`, or `not_checked`.

Closed summary fields include:

- `baseline_deck_specific_coverage`
- `ocr_context_deck_specific_coverage`
- `deck_specific_coverage_delta`
- `visible_asset_coverage_delta`
- `recovered_content_usage_delta`
- `active_recall_from_recovered_content_delta`
- `coverage_eval_role=diagnostic`
- `should_modify_contract_scorer=no`
- `recommended_next_step`

This diagnostic is advisory evidence only. It does not modify the old contract
scorer and does not manufacture score improvement by threshold changes.

Banked Slice 176P closed result on the common StatQuest/ensemble deck:

- `private_baseline_guide_available=true`
- `private_baseline_guide_gitignored=true`
- `private_176n_guide_available=true`
- `private_176n_guide_gitignored=true`
- `private_ocr_artifact_available=true`
- `private_ocr_artifact_gitignored=true`
- `private_visible_artifact_available=true`
- `private_visible_artifact_gitignored=true`
- `provider_call_made=false`
- `generation_rerun=false`
- `marker_source=private_artifact_categories`
- `marker_count_bucket=high`
- `baseline_deck_specific_coverage=high`
- `ocr_context_deck_specific_coverage=high`
- `deck_specific_coverage_delta=unchanged`
- `visible_asset_coverage_delta=unchanged`
- `recovered_content_usage_delta=unchanged`
- `active_recall_from_recovered_content_delta=unchanged`
- `coverage_eval_role=diagnostic`
- `should_modify_contract_scorer=no`
- `recommended_next_step=test_on_uncommon_deck`

Interpretation: this deck is probably already well-covered by the baseline/model
prior knowledge. Do not run packaging-v2 for the same StatQuest/ensemble deck from
this result, and do not modify the contract scorer from this result. The next valid
question is whether OCR context helps on an uncommon, non-public, or less-model-known
deck.
