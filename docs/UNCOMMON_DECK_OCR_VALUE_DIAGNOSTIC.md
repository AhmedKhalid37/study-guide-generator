# Uncommon-Deck OCR Value Diagnostic

Slice 176Q follows Slice 176P's result: the common StatQuest/ensemble deck stayed
`high` for both baseline and OCR-context guides, with
`deck_specific_coverage_delta=unchanged`. That means the OCR-context value should
not be tested by another packaging iteration on the same common deck.

Scope:

- no provider generation
- no provider call
- no OCR rerun
- no packaging-v2 generation
- no scorer threshold tuning
- no new LLM judge, Layer-2 judge, or repair
- no cloud OCR
- no frontend/API wiring
- no raw source/OCR/guide/table/caption/prompt/response/provider payload content
  committed

The diagnostic inventories only private/gitignored local artifacts and emits closed
readiness labels. It checks whether a non-StatQuest candidate has a private source
deck, OCR artifact, baseline guide, generated guide, and closed marker candidates.
It does not print filenames, paths, source text, OCR text, guide text, hashes, byte
counts, prompts, responses, or payloads.

Closed route outcomes:

- `run_uncommon_deck_coverage_eval_existing_artifacts`
- `run_uncommon_deck_ocr_extraction`
- `run_uncommon_deck_baseline_generation`
- `collect_uncommon_deck_fixture`
- `pivot_to_rendered_visible_asset_insertion`
- `stop_ocr_coverage_campaign`
- `blocked`

The next route is chosen from candidate readiness. If an uncommon candidate already
has source, OCR artifact, baseline/generated guides, and markers, the next step is a
coverage eval using existing artifacts. If it has source but no OCR artifact, the
next step is an explicitly scoped OCR extraction slice. If only common/StatQuest-like
material exists, the route is a visible-asset pivot or fixture collection.
