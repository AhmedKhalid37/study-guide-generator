# WRITER_GENERATED_TABLE_COMPANION.md — Slice 176W

> Closed-label record only. No raw guide/source/OCR/table/caption/explanation/
> simplified-table text, no prompts/responses, no provider payloads, no private
> paths, filenames, hashes, byte counts, or screenshots. Private rendered output
> stays under the gitignored `local_operator_baselines/` tree.

## What this slice is

The first Phase 4 slice where **generation behavior changes**. A real provider/model
**writer** is given the existing private recovered patient-dataset table as a closed
**extracted descriptor** (text content, not an image — `writer_saw_image=false`) and
must, in one generation call:

1. insert the token `{{table:patient_dataset}}` **exactly once**, where the faithful
   table belongs (the writer inserts it; this module never injects it);
2. write a **genuine, non-placeholder explanation** beneath the token; and
3. emit a **simplified, study-friendly Markdown table** generated from the descriptor.

The single token is resolved through the existing render path to the faithful recovered
Markdown table (a real table, never an image), and the whole companion is rendered to
**private gitignored HTML** for the operator to read.

Generation is model-agnostic and text-only (no vision is used or assumed).

## Modules

- `pipeline/writer_generated_table_companion.py` — producer + closed summary builder.
- `test_scripts/run_writer_generated_table_companion.py` — private runner (one real call).
- `test_scripts/test_writer_generated_table_companion.py` — public-safe synthetic tests.

## Contract / honest blocking

| Condition | Result |
| --- | --- |
| Provider config unavailable | `blocked` · `blocked_by=provider_unavailable` · `provider_call_made=false` |
| Generation call fails (network/API/empty) | `blocked` · `blocked_by=writer_generation_unavailable` · `provider_call_made=false` |
| Writer emits 0 tokens | `blocked` · `blocked_by=writer_token_missing` |
| Writer emits ≥2 tokens | `blocked` · `blocked_by=writer_token_duplicate` |
| Explanation missing/placeholder | `blocked` · `blocked_by=placeholder_content_detected` |
| Simplified table missing/placeholder/just a copy of faithful | `blocked` · `blocked_by=placeholder_content_detected` |
| Render fails or leaves the token unresolved | `degraded`/`blocked` · `render_failed`/`writer_token_invalid` |
| One token + real explanation + real distinct simplified table, rendered | `completed` · `recommended_next_step=operator_read_private_rendered_guide` |

The deterministic simplification from Slice 176V is **not** reused as the main simplified
version: completion requires `simplified_table_source=writer_generated_from_descriptor`.
Quality and table faithfulness are **not** claimed by code — the producer routes them
to a private operator read with `numeric_verification_claimed=false`.

## Real run (closed summary)

One real provider call, `deepseek` / `deepseek-v4-pro`, against the existing private
recovered `patient_dataset_table` artifact:

`artifact_name=writer_generated_table_companion` · `status=completed` ·
`source_label=ensemble` · `selected_asset_category=patient_dataset_table` ·
`selected_asset_kind=table` · `asset_descriptor_source=private_recovered_table_artifact` ·
`writer_input_descriptor_present=true` · `writer_saw_image=false` ·
`provider_call_made=true` · `provider_name_closed=deepseek` ·
`model_name_closed_or_redacted=deepseek-v4-pro` · `generation_rerun=true` ·
`generation_behavior_changed=true` · `writer_token_present=true` ·
`writer_token_count=1` · `writer_token_inserted_by_writer=true` ·
`postprocessor_token_injected=false` · `faithful_table_present=true` ·
`faithful_table_source=private_recovered_table` · `table_inserted_as_image=false` ·
`explanation_beneath_asset_present=true` ·
`explanation_source=writer_generated_from_descriptor` ·
`explanation_non_placeholder=true` · `simplified_table_present=true` ·
`simplified_table_source=writer_generated_from_descriptor` ·
`simplified_table_non_placeholder=true` · `render_format=html` ·
`render_status=rendered` · `private_rendered_guide_written=true` ·
`private_rendered_guide_gitignored=true` ·
`faithful_table_visibility_status=operator_pending` ·
`explanation_visibility_status=operator_pending` ·
`simplified_table_visibility_status=operator_pending` ·
`operator_private_read_required=true` · `operator_private_read_done=false` ·
`cloud_ocr_used=false` · `ocr_rerun=false` · `coverage_eval_rerun=false` ·
`numeric_verification_claimed=false` · `frontend_api_changed=false` ·
`judge_ready=false` · `repair_ready=false` · `blocked_by=none` ·
`recommended_next_step=operator_read_private_rendered_guide`.

Private-output structure check (counts only, no content): rendered HTML contains two
real `<table>` elements (faithful + simplified), zero `<img>`/`data:` image tags, no
leftover token, and both the explanation and simplified-table headings present.

## Operator read

The private rendered HTML lives under the gitignored
`local_operator_baselines/.private_ocr/<deck>/writer_generated_table_companion/` tree
(path given to the operator out-of-band, never committed).

Operator private read result: `operator_private_read_done=true` ·
`faithful_table_visibility_status=visible` · `explanation_visibility_status=visible` ·
`simplified_table_visibility_status=visible` · `operator_table_readability=acceptable` ·
`operator_explanation_quality=acceptable` ·
`operator_simplified_table_quality=acceptable`. Note: faithful table is readable but
very wide; do not block the 176W commit on width, but consider table-layout hardening
later.

## Validation

`python -m compileall api pipeline test_scripts` OK ·
`test_writer_generated_table_companion` OK ·
`test_reconstructed_table_companion` OK ·
`test_rendered_visible_asset_insertion_proof` OK ·
`test_visible_table_figure_pilot` OK · `git diff --check` clean · no-leak sweep clean
(only the no-image guard literal `data:image` appears, in policy code). Docker not run.

## Out of scope (do not add here)

OCR rerun, `candidate_1` work, coverage eval, a new validator/ingest/schema/bridge as
primary output, frontend/API rollout, Layer-2 judge, repair, cloud OCR, numeric
verification.
