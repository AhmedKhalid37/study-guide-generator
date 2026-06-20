# Visible Table/Figure Pilot from the private OCR artifact — Slice 176K

> First **product-facing** downstream consumer of the private Slice 176I OCR
> extraction. Turns recovered OCR content into a small set of **student-visible
> display assets** — not numeric verification. Closed/committed-safe summary only;
> all raw content stays in a private, gitignored artifact.

- **module:** `pipeline/visible_table_figure_pilot.py`
- **test:** `test_scripts/test_visible_table_figure_pilot.py`
- **branch:** `slice176k-visible-table-figure-pilot-private-ocr`
- `judge_ready=false` · `repair_ready=false`

## Why this slice

Slice 176J (Gini OCR input-cell parser) settled the numeric path for this artifact:
the representative Gini slide is a per-split **answer summary**
(`candidate_kind=computed_gini_answer`, `blocked_by=answer_output_only`,
`machine_consumable_for_recompute=false`), and its recorded
`recommended_next_step` was `pivot_to_visible_table_pilot`. 176K is that pivot — the
**product path**: the first consumer that turns the already-recovered OCR content
into student-visible display assets for a later (off-by-default) private guide
preview. It exists because 176I produced real extracted content with dense grids and
a patient-dataset table cleanly recovered.

## What it IS / is NOT

**IS:** a minimal selector that picks a very small set (**max 3**) of high-value
student-visible assets (proximity matrix, patient-dataset table, optional
decision-tree/split diagram) out of the private 176I OCR extraction, packages
reconstructed table markdown / structured table JSON / caption-context / a closed
placement hint into a **private, gitignored** pilot artifact, and emits a
committed-safe closed summary.

**NOT:** a numeric parser, numeric-recompute wiring, a broad table engine,
guide-generation wiring, frontend/API integration, full ingestion rollout, a Layer-2
judge, repair, cloud OCR, or provider/model generation.

## Anti-laundering / privacy invariants

- Visible table/figure assets are **display / study assets only** — they do **not**
  prove numeric correctness. No asset is ever `numeric_verification`; numeric-bearing
  display tables are at most `numeric_verification_role=display_only`; nothing is fed
  into recompute and `numeric_recompute_claimed` is a hardwired `False`.
- Raw reconstructed tables, OCR captions, rendered crops, source PDFs, model
  files/caches, and private paths live **only** in the private artifact directory.
  The committed summary carries closed tokens / counts / bools only — every
  `*_committed` flag is hardwired `False` and the summary builder accepts no
  raw-text / path / size argument.
- If the private artifact directory is missing or not confirmed private
  (gitignored / temp), the pilot **blocks** instead of writing anything.

## Real result (ran on the private 176I artifact)

| field | value |
|---|---|
| `status` | `completed` |
| `selected_assets_count` / `max_assets_allowed` | `3` / `3` |
| `selected_asset_categories` | `proximity_matrix`, `patient_dataset_table`, `decision_tree_or_split_diagram` |
| `selected_asset_kinds` | `mixed` |
| `private_visible_artifact_written` / `_gitignored` | `true` / `true` |
| `table_asset_status` | `ready` |
| `figure_asset_status` | `partial` (decision-tree slide recovered as a table grid, not a figure image) |
| `caption_or_context_status` | `ready` |
| `guide_insertion_readiness` | `ready_for_off_by_default_private_pilot` |
| `numeric_verification_role` | `display_only` |
| `numeric_recompute_claimed` | `false` |
| `blocked_by` | `none` |
| `recommended_next_step` | `wire_visible_assets_into_private_guide_preview` |

## Next step

Wire the selected display assets into a private, off-by-default guide preview, or add
a caption / placement policy. Numeric verification for this deck stays out of scope
(Gini remains `unverified` from 176J). No cloud OCR; no provider/model generation; no
guide-generation / frontend/API wiring in this slice.
