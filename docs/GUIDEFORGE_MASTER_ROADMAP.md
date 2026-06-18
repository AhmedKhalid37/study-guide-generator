# GuideForge — Master Roadmap (authoritative phase order)

> **For ChatGPT (and any future AI session). Follow this to the letter.** This is the
> single source of truth for *what order work happens in* and *when a phase is allowed
> to end*. The repo/code is the source of truth for *how* things are implemented; if a
> doc disagrees with code, trust code and verify. Do not re-derive a new plan each
> session. Do not reorder phases. Do not start a later phase before the current phase's
> **Exit criteria** are met and recorded.

---

## 0. Why this document exists

The project has drifted twice:

1. **The synthetic Quality-Safety drift (≈ Slices 118–147).** The *original* numeric
   design (`guideforge-eval-and-factsheet-spec.md`, slices 106–112) was **recompute-first**:
   derive Gini from leaf counts, forward-pass from weights+inputs, etc., and catch a
   wrong printed value on *any* dataset. That work mutated into synthetic-only adapters,
   schema validators, and an "operator types the numbers by hand" producer — the
   opposite of recompute-first. **That apparatus is frozen/archived. It is not the
   forward path.** The forward numeric path is the recompute-first verifier from the
   factsheet spec, wired into production.

2. **The measurement-treadmill drift (≈ Slices 149–157).** Reusing wired artifacts for a
   baseline was the right *escape* from the synthetic judge, but completing abstract
   metrics for their own sake is the same treadmill. Measurement is subordinate to
   product quality. Build only the measurement this roadmap names, then stop measuring
   and improve the product.

**The anti-treadmill rule:** every phase below has hard **Exit criteria**. A phase ends
when those are met — not when "more could be measured." Do not invent extra slices to
keep a phase alive. Do not pad. If a phase's exit bar is hit early, advance.

---

## 1. Target (operational definition of "done")

From `study-guide-quality-fix-spec.md` (§3, §8) and `guideforge-eval-and-factsheet-spec.md`:

- **Premium tier** (DeepSeek v4-pro / Qwen 3.7 Max): **9.5 / 10** on both golden decks.
- **Local tier** (Gemma / Qwen 26–35B): **9.0 / 10** on both golden decks.
- **Rubric bar:** ≥ 18/22 on the §8 rubric, with **zero on F1 (leaked reasoning), F5
  (fabricated math), or F6 (internal inconsistency) being disqualifying** regardless of
  total.
- **Two golden decks, on purpose:** `nn3` (clean source — proves you don't regress the
  easy case) and `ensemble` (ambiguous animation-frame source — the hard case, the
  regression test that matters).
- **Figures/tables:** every *useful* figure / diagram / chart / flowchart / graph from
  included pages is inserted into the guide **with an explanation beneath it**; every
  source table is **reconstructed faithfully** (not pasted as an image) **and** given a
  **simplified, clearer version alongside** the original.

---

## 2. Permanent guardrails (every phase, no exceptions)

- Trunk is `chrome-renderer-v1`. Branch per slice. No force-push. One slice per branch,
  verify-and-commit between.
- Do not revive consumed branches. Do not disturb the parked Slice 60 trace stash.
- Do not run or paste `docker compose config` output.
- **Recompute-first, never manual:** numeric correctness comes from recomputing
  structured facts. Never reintroduce the manual "operator types known numbers"
  apparatus. Never auto-correct an `unverified` number into false confidence (the §0
  safety invariant of the factsheet spec).
- **The §0 invariant in code:** no repair step may force a numeric value to a single
  committed form unless that value is `verified` or `canonical`. A `low-confidence` /
  `unverified` number is never "cleaned up" into confidence. Confusion → repaired into
  confident-but-wrong is strictly worse than the original.
- **Two judges, kept separate.** (a) Dev-time **reference-anchored eval judge**: run
  locally, operator's own API key, scores candidate vs the Claude reference; commit
  **closed numbers + <15-word evidence quotes only**. This is allowed and required. (b)
  Production **offline-judge-as-shippability-gate**: stays **frozen** (`judge_ready=false`,
  `repair_ready=false`). Deterministic recompute + leak/coverage checks do the blocking,
  not an LLM.
- **Privacy / closed-vocabulary:** never commit guide text, snippets, matched aliases,
  source text, OCR text, table text, captions, screenshots, private paths, filenames,
  copied formulas, evidence quotes beyond the <15-word judge quotes, provider payloads,
  model prompts/responses, raw runtime outputs, raw job-artifact JSON from private runs,
  source hashes, or source byte counts. `local_operator_baselines/` stays gitignored.
- All `clean.md` writes go through `JobManager.save_clean_md`. `/api/*` routes stay
  registered before the SPA static mount.
- Cloud OCR/extraction is **explicit opt-in**, never default; once-per-session
  disclaimer; budgeted + capped. Local/private extraction (Tesseract / Chandra) needs no
  disclaimer. Chandra stays blocked until its own live-validation gate is explicitly
  cleared.
- Do not weaken true-positive leak detection. Do not patch the aggregator/eval to hide a
  failure. Surface warnings honestly.

---

## 3. Phase order (do not reorder)

### Phase 0 — Eval harness + fact-sheet skeleton (the scoreboard)

**Why first:** you cannot "fix to 9.5" without the instrument that defines 9.5. Builds
what the factsheet spec called slices 106–112 but which drifted and was never built
correctly.

**Build:**
- Golden-pair fixtures (`guideforge-eval-and-factsheet-spec.md` §A1): seed exactly two —
  `nn3` (clean) and `ensemble` (ambiguous_animation_frames) — each with `expected_topics`,
  `ground_truth_numerics` (incl. `Gini weight_gt_176 = 0.20`), `min_mock_questions`,
  `tier_targets {premium: 9.5, local: 9.0}`.
- Layer-1 deterministic scorer (§A2): leaked-reasoning regex (§B6), numeric correctness
  vs `ground_truth_numerics`, worked-answer completeness, coverage, mock-Q count. The
  leak + numeric + two-different-values checks are **blocking**.
- Layer-2 reference-anchored judge (§A3): scores candidate vs the Claude reference (the
  9–10 anchor), with the calibration step (judge must score the reference ≥ 4 or the run
  is discarded as miscalibrated). Dev-time, local, operator's key. Closed scores + <15-word
  quotes committed only.
- Overall score + pass bar (§A4): report `overall_10` **and** `shippable` separately.
- Regression record JSONL (§A5), append-only; CI/regression rule: regress if `overall_10`
  drops > 0.3 vs the previous green run on the same lecture/model, or any previously-passing
  blocking check now fails.
- Fact-record + fact-sheet schemas (§B1, §B2) as data structures (not yet wired to
  generation).

**Exit criteria:**
- Re-running the harness on the *old* Ensemble guide auto-reports: `shippable == false`
  AND leaked_reasoning present+blocking AND `Gini weight_gt_176` a blocking mismatch with
  `expected == 0.20` and `found ∈ {any wrong printed candidate}`. Assert the **property**,
  not a hard-coded `0.42`.
- Both golden fixtures load and score end-to-end; a baseline `overall_10` is recorded for
  the current best guide on each deck.
- **Do not** advance until the harness can produce a number for both decks.

---

### Phase 1 — Text-discipline quality (no OCR dependency)

**Why here:** the highest-yield, model-agnostic, prompt-only fixes. They get clean decks
(NN3) to premium 9.5 and kill the trust-killing failure classes on *all* decks.

**Do, in the spec's priority order (`study-guide-quality-fix-spec.md` §9):**
1. **F1** — ban leaked reasoning / visible uncertainty (the single biggest tell). Prompt
   contract + the leak gate from Phase 0.
2. **F5 + F6** — no fabricated math; enforce internal consistency. Wire the **recompute-first
   verifier** (factsheet §B3) in front of the writer: recompute structured facts, mark
   `verified | failed | unverified`, and the writer sees only committed values. This is
   the return to the original numeric design.
3. **F2 + F3** — finish every worked example to its final answer; show every arithmetic
   step.
4. **F9 + coverage gate** — make "comprehensive" binding; stop silent compression; gate on
   the Material Coverage subsystem.
5. **F4** — intuition / "explain-to-a-beginner" blocks for every non-obvious mechanic.
6. **F7 + F8** — exam-required reference data in labelled tables; mandatory consolidation /
   pipeline section.
7. **F10** — confident directive voice + consistent ⚠️ EXAM ALERT flags.
- Ship the single revised generation prompt (§6) to all tiers first. Only fork a
  local-tier prompt **if** the eval loop proves the local model fails the shared prompt —
  do not pre-build per-tier prompts.

**Exit criteria:**
- `nn3` (clean deck) hits **premium ≥ 9.5** on the Phase 0 harness, with **zero** F1/F5/F6.
- The recompute-first verifier catches a synthetic wrong-number injection on a clean deck
  (blocking), and never forces an `unverified` value to false confidence.
- `ensemble` text-only axes improve, but its numeric/figure axes are **expected to remain
  blocked** here — that is Phase 2/3's job. Record that gap; do not try to prompt-fix it.

---

### Phase 2 — OCR / extraction overhaul (the spine for hard decks + figures)

**Why here:** Ensemble collapses because the source is animation-frame images (≈ 792 usable
words from 50 MB). Hard-deck numerics AND figure/table insertion both depend on recovering
content the text extractor can't. This unblocks both halves of the remaining quality gap.

**Do (per `docs/VISION_ROADMAP.md` stack + factsheet ingestion):**
- **Frame-dedup ingestion:** collapse animation frames to final-state slides only (the
  2,000-frame cost+quality lever) before any expensive extraction.
- Recover the numeric content that broke Ensemble (Gini leaf counts, stump tables, weight
  tables) into structured facts the recompute verifier can consume.
- Extract figure/diagram assets (fitz local for digitally-authored PDFs; for
  scanned/video-frame decks where the whole page is one image, the local segmenter can't
  cut a figure out — that needs Chandra-local or cloud OCR).
- **Extraction-quality decision:** clear **one** privacy-clean high-quality path —
  Chandra-local (preferred; no disclaimer, no cost) via its live-validation gate, **or**
  the Mistral OCR-3 cloud path (per-page Markdown + reconstructed tables + figure images)
  via the Slice-35 conditional-go (live pricing + privacy disclaimer + budget cap). Do not
  leave both blocked.

**Exit criteria:**
- The Ensemble deck's broken numerics (`Gini weight_gt_176`, total error, amount of say,
  proximity, weighted impute) are recoverable as structured facts with enough fidelity for
  the recompute verifier to run — proven on the local gitignored sample, recorded as closed
  counts only.
- Figure assets from included pages are extracted with safe positional refs (no
  path/filename/caption leakage).
- One high-quality extraction path is **cleared and validated**, not blocked.

---

### Phase 3 — Numeric truth on hard decks (recompute-first, wired)

**Why here:** now that Phase 2 recovers the inputs, finish the truth layer so the writer
on hard decks also sees only committed values.

**Do (factsheet spec Part B):**
- Wire the **recompute-first hierarchy** (§B3) into the live pipeline: recompute → canonical
  fixture fallback (signature-matched on *content*, only when recompute is impossible) →
  `unverified` (never invent, never auto-correct).
- Add the **one** canonical AdaBoost fixture (§B4) as the narrow fallback, signature-matched,
  provenance-tagged.
- Consolidate to a single committed value per quantity; writer sees only committed values +
  provenance (§B5 decision table).
- Couple the leak/uncertainty scanner to verification status (§B6): on a blocking failure,
  repair only force-commits `verified | canonical` values; `unverified` routes to
  warning/human-review, never to forced confidence.

**Exit criteria:**
- `ensemble` reaches **premium ≥ 9.5** and **local ≥ 9.0** on the Phase 0 harness, with the
  old Gini disaster now **caught and corrected to 0.20 via recompute** (not via a hardcoded
  table).
- The §0 invariant holds: a synthetic `unverified` number is never repaired into confidence
  (assert it).
- Both golden decks now pass numeric + leak blocking checks on both tiers.

---

### Phase 4 — Figures / diagrams / tables (insertion + explanation + reconstruction)

**Why here:** depends on Phase 2 extraction. This delivers the "every useful figure +
reconstructed/simplified tables" requirement.

**Do (V1–V7 stack in `docs/VISION_ROADMAP.md`):**
- **Lift the cap.** The pilot is capped at 2 images; the requirement is *all useful*
  figures. Replace the hard cap with a usefulness threshold (the V3 text-replacement test:
  `include_as_figure | convert_to_table | summarize_as_text | omit`).
- **Finish classification precision** (table vs diagram) so reconstructable tables become
  tables and irreplaceable diagrams become inserted figures — the known residual bottleneck
  from Slices 69–73.
- **Asset-aware prompt (V4):** writer places `{{figure:asset_id}}` tokens and writes an
  explanation beneath each inserted figure. Token lint for well-formed/no-unknown-ids.
- **Tables:** reconstruct each source table faithfully as a real table (not an image) AND
  emit a simplified, clearer, comprehensive restatement alongside the original — per the
  requirement and the table-reconstruction-policy work already on trunk.
- **Visual render path (V5, HIGH RISK, late, flag-gated):** resolve tokens → embedded images
  in `clean.md`/PDF/HTML/DOCX. Touches the tuned Chromium PDF path — golden-render
  regression-tested, byte-identical when no assets present.
- **Visual + coverage eval (V7):** high-value figures included? orphaned tokens? duplicate
  figures? all selected source pages represented? Makes "self-contained" measurable.

**Exit criteria:**
- On both golden decks: every figure the V3 test rates `include_as_figure` is inserted with
  an explanation beneath it; no orphaned tokens; no duplicate figures; tables reconstructed +
  simplified.
- Golden-render regression passes; output byte-identical when a deck has no assets.
- The figure/table axes of the rubric (F7) score 2 on both decks.

---

### Phase 5 — Finalize quality (close the rubric on both tiers)

**Do:** run the full harness on both decks × both tiers; close any remaining rubric gap to
**≥ 18/22, zero F1/F5/F6**; record the green regression line.

**Exit criteria:**
- `nn3` and `ensemble` both: **premium ≥ 9.5, local ≥ 9.0**, `shippable == true`, zero
  blocking failures. Recorded in the regression JSONL as the new green baseline.
- This is the milestone where guide quality is **declared done** and frozen as the baseline
  all later work must not regress.

---

### Phase 6 — Presets / styles / Style-tab options

**Why here:** only tune per-style variants once the base quality is locked, so you're tuning
*around* a known-good 9.5 baseline, not on sand.

**Do:** audit and edit the generator presets, outline quick-templates, custom styles, and the
Style-tab options against the green baseline. Compare real generated guides (not just metrics)
across styles. Change a prompt/style only when the harness shows it helps.

**Exit criteria:** every shipped preset/style produces a guide that stays within regression
tolerance of the Phase 5 baseline on its intended deck; no style regresses F1/F5/F6.

---

### Phase 7 — Local LLM Manager finish

**Do:** resume LMM from its paused Phase 2 state; design + build the deferred **approve-root
flow** as a host-companion flow (not a browser folder picker), within the existing LMM
security boundary (no Docker socket, no host PID namespace, no browser-provided host paths,
token-authed Unix socket, key-less DTOs).

**Exit criteria:** approve-root flow works end-to-end via the companion; LMM boundary
invariants hold; local-tier generation runs against a companion-managed model.

---

### Phase 8 — Final features list

**Do:** implement the remaining items in `guideforge_final_picked_features.md` (active recall
after each section, etc.), each as its own slice, each measured against the Phase 5 baseline so
no feature regresses quality.

**Exit criteria:** picked features shipped; baseline not regressed; project is feature-complete
against the picked list.

---

## 4. What NOT to do (encoded so it can't drift again)

- Do **not** build more synthetic Quality-Safety adapters/schemas/validators. That layer is
  frozen/archived.
- Do **not** reintroduce manual "operator types known numbers." Numeric truth is
  recompute-first.
- Do **not** set `judge_ready=true` or `repair_ready=true` on the production offline judge.
- Do **not** make Quality Safety blocking in production beyond the deterministic recompute +
  leak + coverage gates.
- Do **not** schedule a docs-consolidation slice until doc drift actively costs onboarding time
  on a real task.
- Do **not** start a phase before the prior phase's Exit criteria are met and recorded.
- Do **not** pad a phase with extra slices once its Exit criteria are hit. End it and advance.
- Do **not** add Chandra/Mistral/Gemini/cloud/provider calls outside the explicit, gated,
  opt-in extraction path in Phase 2.

---

## 5. One-line phase ledger (fill in as you go, closed vocabulary only)

```
phase_0_eval_harness:        not_started | in_progress | done   (nn3_baseline_10=_, ensemble_baseline_10=_)
phase_1_text_quality:        not_started | in_progress | done   (nn3_premium_10=_, zero_F1_F5_F6=_)
phase_2_ocr_extraction:      not_started | in_progress | done   (ensemble_numerics_recoverable=_, extraction_path_cleared=_)
phase_3_numeric_truth:       not_started | in_progress | done   (ensemble_premium_10=_, gini_caught_via_recompute=_)
phase_4_figures_tables:      not_started | in_progress | done   (all_useful_figures_inserted=_, tables_reconstructed_simplified=_)
phase_5_finalize_quality:    not_started | in_progress | done   (nn3_premium_10=_, ensemble_premium_10=_, local_10=_, shippable=_)
phase_6_styles_presets:      not_started | in_progress | done
phase_7_local_llm_manager:   not_started | in_progress | done
phase_8_final_features:      not_started | in_progress | done
```
