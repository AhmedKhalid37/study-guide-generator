# Asset companion insertion seam — Slice 177D

> Private/off-by-default proof. **Not** a frontend/API rollout and **not** a change to
> normal-generation default behavior. This proves **one** gated insertion seam exists,
> not that all tables/figures are solved.

## What this slice is

Slice **177C** proved that an existing private full study guide can be **composed**
with the accepted **177B** combined table+figure companion in a standalone preview
producer (`pipeline/full_guide_asset_companion_preview.py`).

Slice **177D** takes one step closer to the normal guide pipeline: it introduces a
single, narrow, **off-by-default** insertion seam that future normal generation
*could* call, while still producing a real private rendered artifact now.

- **Module:** `pipeline/asset_companion_insertion.py`
- **Pure seam:** `insert_companion_section(guide_md, combined_md, *, enabled=False)`
- **Private runner entrypoint:** `run_asset_companion_insertion(...)` / `main()`
- **Runner script:** `test_scripts/run_asset_companion_insertion_private.py`
- **Tests:** `test_scripts/test_asset_companion_insertion.py`

## The off-by-default contract

`insert_companion_section(...)` is the reusable hook. By contract:

- With `enabled=False` (the **default**, and what normal app generation uses) the guide
  Markdown is returned **byte-for-byte unchanged**. Wiring this helper into the
  generation path therefore changes nothing until a caller explicitly opts in.
- With `enabled=True` (the **private runner only**) the accepted combined companion is
  inserted as one clearly separated section at a deterministic safe location.

The closed summary records `off_by_default=true` and
`normal_generation_default_unchanged=true`. The private runner sets `enabled=True`
(`ENABLE_INSERTION_SEAM=1`); the disabled path reports `blocked_by=seam_disabled`,
`asset_companion_section_inserted=false`, and writes no inserted guide.

## Deterministic insertion location

`pick_insertion_point(guide_md)` is content-agnostic. If the guide ends with a generic
summary-like section (Summary / References / Key takeaways / Further reading / Glossary
/ Conclusion / Wrap-up) the companion is inserted **before** it
(`insertion_location=before_trailing_summary`); otherwise it is **appended at the end**
(`insertion_location=appended_at_end`). No raw guide text is embedded in code — only
generic heading words.

## Safety posture (same invariants as 177B/177C)

- Reuses the accepted-artifact checks from 177B/177C: the companion must carry an
  accepted faithful table + explanation + role-aware **study** simplified table (never a
  row-reduced copy), and an accepted **non-table** figure (never
  table-like/matrix/grid/text-only/sliver) with explanation + how-to-read + exam
  takeaway.
- Preserves relative `assets/<name>` image refs by copying them into the private output
  dir; refuses `data:image`/base64; refuses any raw private path that would appear in
  the rendered HTML; refuses unsafe (non-gitignored) output dirs.
- Output is written **only** to a gitignored private artifact directory. The committed
  closed summary is closed labels only — no raw guide/table/figure/caption/source/OCR
  text, no descriptor JSON, no image bytes/base64/data URIs, no prompts/responses/
  provider payloads, no private paths/source filenames/hashes/byte counts.

## Hard scope (what this slice is NOT)

No provider/model generation, no generation/OCR rerun, no judge, no repair, no cloud
OCR, no Chandra, no broad OCR, no numeric verification, no frontend/API change, no broad
asset registry/framework, and no "all assets solved" claim. The seam is not yet wired
into normal generation; doing so (behind an explicit flag) is a separate future slice.

## Real private run

The private runner was executed over the existing accepted private ensemble full guide
and the accepted 177B combined companion. Result: `status=completed`,
`off_by_default=true`, `normal_generation_default_unchanged=true`,
`private_runner_enabled=true`, `asset_companion_section_inserted=true`,
`relative_asset_refs_preserved=true`, `render_status=rendered`,
`raw_private_paths_in_rendered_html=false`, `broken_image_marker_detected=false`,
`data_image_used=false`, `base64_image_used=false`, `provider_call_made=false`,
`blocked_by=none`,
`recommended_next_step=operator_read_private_asset_companion_insertion_output`.

The rendered private HTML lives in the gitignored private artifact directory and is
**not** committed. The operator must open it and confirm: it reads as a full guide; the
companion section is inserted at a sensible location; the accepted table companion and
accepted non-table figure companion both appear; the relative image renders; there is no
broken-image indicator; no raw private path is visible; and the guide remains readable.
