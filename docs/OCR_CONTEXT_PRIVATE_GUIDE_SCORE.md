# OCR-context private guide preview + score — Slice 176L

> **First student-visible artifact after the local-OCR breakthrough.** Turns the
> private Slice 176I OCR extraction (+ the Slice 176K visible assets) into a private,
> off-by-default **student guide preview**, and scores it against the existing
> baseline guide with the committed deterministic contract lint. Closed/committed-safe
> summary only; all raw guide / OCR / table / caption content stays in a private,
> gitignored artifact.

- **module:** `pipeline/ocr_context_private_guide.py`
- **runner:** `test_scripts/run_ocr_context_private_guide_score.py`
- **test:** `test_scripts/test_ocr_context_private_guide_score.py`
- **branch:** `slice176l-ocr-context-private-guide-score`
- `judge_ready=false` · `repair_ready=false`

## Why this slice

176K was the **last preparation slice**. Per the byte-identical invariant, the next
commit had to change what a student can actually read. 176L does: it assembles a
private student guide **preview** from the OCR-extracted slide content that the
deck's near-empty text layer otherwise dropped (176G–176I), embedding the three 176K
visible assets, and scores it with **existing** tooling — no new judge, no Layer-2
judge, no repair, no provider/model generation, no cloud OCR, no frontend/API wiring.

## What it IS / is NOT

**IS:** a pure offline preview builder (176I manifest entries + optional 176K visible
payload → a comprehensive-style guide-preview **markdown**, written only to the
private gitignored dir) + a thin wrapper over the committed deterministic
`guide_quality_contract_lint` scorer + a deterministic **closed** baseline comparison.

**NOT:** a new evaluator / judge, a Layer-2 judge, repair, numeric-recompute wiring,
provider/model generation, guide-generation wiring into normal app behavior,
frontend/API integration, full ingestion rollout, or cloud OCR.

## Generation & scoring path (existing tooling only)

- **Generation mode:** `deterministic_stub_preview` — fully offline, no LLM, no
  provider. The preview embeds the reconstructed OCR tables (and the 176K visible
  asset markdown) under a comprehensive-style scaffold.
- **Scoring:** the already-committed `pipeline/guide_quality_contract_lint.py`
  (counts only, deterministic, no LLM) is run on both the preview and the private
  baseline guide markdown. The closed comparison is derived from reference-table
  count, present required-section count, and lint warning count.

## Real result (ran on the private 176I artifact, vs the private baseline guide)

| field | value |
|---|---|
| `status` | `completed` |
| `generation_mode` | `deterministic_stub_preview` |
| `guide_artifact_status` | `preview_generated` |
| `private_ocr_artifact_available` / `_gitignored` | `true` / `true` |
| `private_visible_artifact_available` / `_gitignored` | `true` / `true` |
| `private_guide_artifact_written` / `_gitignored` | `true` / `true` |
| `visible_assets_used` | `yes` |
| `selected_visible_asset_categories` | `patient_dataset_table`, `decision_tree_or_split_diagram`, `proximity_matrix` |
| `score_status` | `scored` |
| `baseline_comparison_status` | `regressed` |
| `coverage_signal` | `regressed` |
| `figure_table_signal` | `unchanged` |
| `numeric_verification_claimed` | `false` |
| `blocked_by` | `none` |
| `recommended_next_step` | `build_off_by_default_ocr_context_generation_path` |

## GATE-2 interpretation (do not bank "regressed" as a finding)

The comparison is **regressed / unchanged**, but this is a **stub-vs-full-guide
confound, not evidence that OCR content hurts**. The candidate is a *deterministic
stub* (recovered tables + generic scaffold prose); the baseline is the *full,
LLM-generated* app guide. A thin stub is expected to carry fewer present required
sections and exam alerts than a complete guide, so it scores lower on the contract
lint regardless of content quality. What the slice **did** establish:

- the recovered OCR tables (which the near-empty text layer dropped) are now present
  in a student-readable preview — the real student-visible change;
- the existing deterministic scorer runs cleanly on both guides;
- a fair measurement of "does OCR content improve the guide" requires feeding the OCR
  content through the **real** (off-by-default) generation path and re-scoring — not a
  deterministic stub. Hence `recommended_next_step=build_off_by_default_ocr_context_generation_path`.

The scorer/thresholds were **not** touched to manufacture an "improved" result.

## Privacy / anti-laundering

- The preview markdown (reconstructed OCR tables + context) is written **only** to the
  private gitignored dir; it is never committed or printed. The committed summary is
  closed tokens / bools only — every `*_committed` flag is hardwired `false` and the
  summary builder accepts no raw text / path / size argument.
- Visible assets are **display / study** material; nothing is fed into recompute and
  `numeric_verification_claimed` is a hardwired `false`. Gini stays `unverified`.
- Baseline markdown is read **only** from a confirmed-private (gitignored) location.

No cloud OCR; no provider/model generation; no guide-generation / frontend/API wiring;
no Layer-2 judge; no repair. `local_operator_baselines/` (incl. the private OCR artifact
and the private preview) stays ignored. `judge_ready=false`; `repair_ready=false`.
