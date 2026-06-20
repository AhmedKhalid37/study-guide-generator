# Frame-redundancy detector + `frame_dedup_mode` setting — Slice 176M

> **The cheap gate for a future, expensive, gated frame-selection branch.** A small
> minority of sources (~1–2%, especially **StatQuest-style video-export slide decks**)
> emit one PDF page per animation build-step, so the deck is dominated by runs of
> near-identical frames. 176M adds a cheap, measurement-only detector that flags this,
> plus a three-state operator setting that decides whether the (future, expensive)
> frame-selection branch should run. The expensive pipeline is **not built here** and
> must stay a gated conditional branch — the normal ~98% path is untouched.

- **module:** `pipeline/slide_redundancy_detector.py`
- **test:** `test_scripts/test_slide_redundancy_detector.py`
- **branch:** `slice176m-frame-redundancy-detector-setting`
- `judge_ready=false` · `repair_ready=false`

## What it IS / is NOT

**IS:** (1) a cheap, OCR-free, model-free, network-free detector that hashes
low-resolution page thumbnails **in memory** (difference-hash / dHash, 64-bit),
measures consecutive-page visual redundancy, and emits **closed metrics only**; (2) a
deterministic resolver for the setting `frame_dedup_mode = auto | force_on | force_off`
(default `auto`) that decides whether the expensive branch should engage.

**NOT:** the frame-selection pipeline (phash-collapse → terminal-frame →
coverage-coupled → VLM-classify-survivors) — **not built in this slice**; not OCR
generation/wiring, OCR-context full-guide generation, guide regeneration, a Layer-2
judge, repair, provider/model generation, cloud OCR, a frontend-wide redesign, or a
broad document-analysis framework.

## Why dHash (false-positive guard)

The detector uses a **difference hash** (compares horizontal brightness gradients),
not a plain average hash. dHash stays sensitive to body-content changes even when two
slides share a template header/footer, so **repetitive-template-but-content-distinct**
lecture decks are *not* flagged as redundant. A consecutive pair only counts as a
near-duplicate above a deliberately high similarity (`0.92`), and clustering breaks a
run when adjacent similarity drops below `0.88`.

## Closed detector metrics (`slide_redundancy_detection`)

`status` (`completed|degraded|blocked|skipped`) · `source_label` · `page_count_bucket`
· `pages_sampled_count` · `adjacent_pairs_sampled_count` ·
`mean_adjacent_similarity_bucket` · `high_similarity_pair_ratio_bucket` ·
`distinct_visual_cluster_count_bucket` · `cluster_to_page_ratio_bucket` ·
`slide_redundancy` (`low|medium|high|unknown`) · `detector_confidence`
(`low|medium|high`) · `raw_images_committed=false` · `thumbnails_committed=false` ·
`source_pdf_committed=false` · `warnings` (closed vocab). All buckets are
`low|medium|high|very_high|unknown`. **No image files are ever written** — frames are
hashed in memory — so raster frames never reach the repo.

### Decision (conservative — false positives are harmful)

- **high:** a clear share of consecutive pairs are near-duplicates
  (`high_similarity_pair_ratio ≥ 0.30`) **and** visual clusters collapse many pages
  (`cluster_to_page_ratio ≤ 0.60`).
- **low:** consecutive pages mostly distinct (`high_similarity_pair_ratio < 0.15`) and
  clusters ≈ pages (`cluster_to_page_ratio ≥ 0.80`).
- **medium:** in between. **unknown:** too few pages (`< 3`) to judge.

## Setting + resolver (`frame_dedup_mode`)

| `frame_dedup_mode` | detector | `resolved_frame_dedup` | `resolution_reason` |
|---|---|---|---|
| `auto` (default) | `high` | `on` | `detector_high` |
| `auto` | `low` / `medium` | `off` | `detector_low` |
| `auto` | `unknown` | `off` | `detector_unknown_default_off` |
| `force_on` | (ignored) | `on` | `user_force_on` |
| `force_off` | (ignored) | `off` | `user_force_off` |

`auto` only engages on a clear `high`; **`medium` resolves `off`** by design. `force_on`
exists for animation decks the detector misses; `force_off` exists for false positives.
The setting's natural home is the existing guide-building / generation-options surface
(the same pattern as the depth/difficulty axes); like the off-by-default
`SlideOcrIngestionConfig` seam, the resolver is self-contained and is **not** wired into
the normal generation path in this slice, so normal generation behavior is unchanged.

## Real validation (local gitignored decks; closed labels only)

Ran the detector on the available local decks (no filenames/paths/raw counts recorded):

- **Animation-export style decks (StatQuest-like):** `slide_redundancy=high`,
  `detector_confidence=medium`, `auto → resolved_frame_dedup=on`
  (`reason=detector_high`). ✅ gate flags them on.
- **Normal lecture decks:** `slide_redundancy=low`, `detector_confidence=medium|high`,
  `auto → resolved_frame_dedup=off` (`reason=detector_low`). ✅ stay on the normal path.

Closed validation result: `statquest_validation_status=passed` ·
`normal_deck_validation_status=passed` · `repetitive_template_validation_status=passed`
(synthetic guard + real normal/template lecture decks all resolve off) ·
`false_positive_risk=low` · `detector_calibration_status=ready_for_off_by_default_gate`.
The gate the build order required — animation-export decks flag high/on, normal decks
flag low/off — **passes on real decks**, so the expensive selection pipeline is the
sanctioned next slice (still gated, still off unless the resolved flag is `on`).

## Privacy / scope

No raw images, thumbnails, source PDFs, OCR text, guide text, filenames, paths, hashes,
or byte counts are committed — the committed summary is closed tokens + coarse counts
only, and all `*_committed` flags are hardwired `false`. Synthetic public-safe hash
sequences are used in tests. No Docker; no cloud OCR; no provider/model generation; no
Layer-2 judge; no repair. `local_operator_baselines/` stays ignored.
