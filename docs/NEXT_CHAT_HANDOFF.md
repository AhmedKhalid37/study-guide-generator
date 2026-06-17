# NEXT_CHAT_HANDOFF.md — Start here

> One-page handoff so a fresh chat (Claude / ChatGPT / Codex) can continue safely
> from the repo alone. The repo is the source of truth. For the full per-slice log
> see `CURRENT_TASK.md`; for the "why" behind choices see `DECISIONS.md`; for the
> stable overview see `PROJECT_CONTEXT.md`; canonical brief is `../CLAUDE.md`.

## Current position
- **Working tree:** **Slice 130 (Wire Safe Numeric Extractor into Advisory Artifact Path) — UNCOMMITTED (per instruction)** on
  branch `slice130-wire-safe-numeric-extractor-advisory-artifact`, branched from fresh `chrome-renderer-v1` after Slice 129 was
  committed, fast-forward merged, and pushed. **Slice 129 is trunk commit `0bff68c`**.
  - **Part 0 completed:** Slice 129 was committed as `0bff68c`, fast-forward merged to `chrome-renderer-v1`, and pushed with a
    normal `git push` (no force-push). It added the pure/unwired safe numeric extractor. No docker compose config was run; the
    Slice 60 trace stash remains parked and untouched.
  - **Slice 130 scope:** wire the Slice 129 safe numeric extractor into the advisory `quality_safety_unified_qa.json` artifact
    path. **Advisory / non-blocking.** An optional, job-local, read-only candidate sidecar feeds the safe extractor, whose records
    run through the existing Slice 126 numeric mapper/recompute path. No production OCR/table/source parsing, no `clean.md`
    numeric read, no job-folder scan, no sidecar writes in production, no provider/model/cloud, no judge, no repair, no blocking.
  - **Candidate input artifact (read-only, optional, internal, non-user-facing):** `quality_safety_safe_numeric_candidates.json`
    — a list of sanitized candidate dicts, or a dict wrapper under a closed `candidates` key. Never created/written in production;
    never added to generic artifact/export/UI lists. Slice 125 mapper remains the final sanitizer.
  - **Precedence (deterministic):** explicit `quality_safety_numeric_extraction_records.json` records **win**; safe candidates
    feed the numeric leg only when no explicit records exist; when both exist the safe leg is summarized only
    (`safe_numeric_extractor_status=skipped`, `superseded_by_explicit_records`) and never merged.
  - **`pipeline/quality_safety_job_artifact.py`:** new `safe_numeric_candidates` param + read-only reader
    `read_quality_safety_safe_numeric_candidates`; three new top-level fields `safe_numeric_extractor_status`,
    `safe_numeric_extractor_summary` (counts only), `safe_numeric_extractor_warnings` (closed tokens). `numeric_extraction_*`
    stays canonical recompute evidence; only summary/status/warnings are surfaced (sanitized records flow internally into
    `numeric_extraction_bundle`). Artifact name/kind/`advisory=true` unchanged.
  - **`pipeline/run_markdown_job.py`:** `_write_quality_safety_unified_qa` reads the optional candidate sidecar (read-only) and
    passes it through; degraded fallback carries the three new fields.
  - **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
    `M docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
    `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
    `M pipeline/quality_safety_job_artifact.py`, `M pipeline/run_markdown_job.py`,
    `M test_scripts/test_quality_safety_job_artifact.py`, `M test_scripts/validate_quality_safety_real_disaster_e2e.py`.
  - **Validation (synthetic):** safe candidate payload flows through the real artifact path + production hook: clean → recompute
    passed (`shippable=true`); wrong → recompute blocking (`shippable=false`, `safety_floor_green=false`); unsupported-method →
    counted unsupported, not blocked; structural coverage not converted into candidates; forbidden fields stripped, no canary;
    precedence proven.
  - **Closed-vocabulary outcome:** `safe_numeric_extractor_artifact_path_status=ok`;
    `numeric_fact_sheet_extraction_leg_status=partial`; `artifact_path_ready=true_for_synthetic_candidates`;
    `production_numeric_extractor_present=sidecar_candidate_only`; `judge_ready=false`; `repair_ready=false`; production numeric
    extraction coverage **not** claimed complete.
  - **Validation runs:** safe extractor 207; numeric mapper 232; job artifact **595**; recompute verifier 99; unified qa 73;
    real-disaster e2e **80**; `compileall api pipeline test_scripts` OK; `git diff --check` clean; no-leak sweep clean. No docker
    compose config was run; Docker not required (no container surface changed).
  - **Out of scope/unchanged:** no `api/server.py` change, no routes, no frontend change, no generic artifact selector row, no
    generation/prompt/provider/request-schema/render/export/OCR/table/visual/Ask Guide change, no judge/`overall_10`/repair/
    blocking gate, no `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`. **Slice 130 remains NOT
    committed.**
  - **Next expected slice:** a production safe-candidate *source* (a separately-designed bounded slice deriving sanitized
    candidates from already-sanitized structured artifacts) **or** an explicit operator waiver accepting sidecar-only coverage.
    Only after a proven production candidate source (or waiver) revisit `judge_ready`.

### Previously (Slice 129, now trunk `0bff68c`)
- **Slice 129 (Pure Safe Numeric Extractor v1)** added the pure/unwired `pipeline/quality_safety_safe_numeric_extractor.py`
  (stdlib + Slice 125 mapper only): converts caller-supplied sanitized numeric candidates into
  `quality_safety_numeric_extraction_records`-compatible records; Slice 125 mapper is the final sanitizer; v1 methods unchanged;
  `single_confident_wrong_numeric_case` recompute-blocked, `clean_real_case` passed, `legacy_confused_wrong_case` partial;
  `judge_ready=false`, `repair_ready=false`. Not wired in Slice 129; Slice 130 wires it.

### Previously (Slice 128, now trunk `8534784`)
- **Slice 128 (Safe Numeric Extractor Design)** designed the safe production numeric extractor (design only): allowed input
  `caller_supplied_sanitized_numeric_candidates`; forbidden source/OCR/table/text inputs; Slice 124/125 output record shape;
  v1 methods unchanged; `production_numeric_extractor_present=false`, `judge_ready=false`, `repair_ready=false`,
  `next_step=pure_safe_numeric_extractor_v1`. Docs-only.

### Previously (Slice 127, now trunk `35bdf8b`)
- **Slice 127 (Numeric Sidecar Real-Path Operator Validation)** validated the Slice 126 numeric sidecar advisory artifact path:
  synthetic sidecar path `ok` through the actual builder + production hook (missing → `skipped`, malformed → `failed`/degraded,
  clean → `recompute=passed`, wrong → recompute blocker, advisory/non-blocking); the real/private operator pass was `not_run`
  (deferred). `numeric_fact_sheet_extraction_leg_status=partial`, `production_numeric_extractor_present=false`,
  `judge_ready=false`, `repair_ready=false`, `next_step=safe_numeric_extractor_design`. Docs-only.

### Previously (Slice 126, now trunk `7ff1887`)
- **Slice 126 (Wire Numeric Extraction Mapper into Advisory Artifact)** wired the Slice 125 mapper into the advisory
  `quality_safety_unified_qa.json` artifact path: an optional read-only sidecar
  (`quality_safety_numeric_extraction_records.json`, never created in production) feeds the producer + recompute verifier when
  present, adding `numeric_extraction_*` fields kept SEPARATE from `extraction_coverage_*`. Wrong numeric claim → recompute
  blocker; clean → passes; missing → `skipped`; malformed → `failed`/degraded. `numeric_fact_sheet_extraction_leg_status=partial`,
  `judge_ready=false`, `repair_ready=false`. No production numeric extractor.

### Previously (Slice 125, now trunk `13a7ef6`)
- **Slice 125 (Pure Numeric Extraction Record Mapper v1)** added `pipeline/quality_safety_numeric_extraction_mapper.py`
  (pure/unwired) translating sanitized numeric extraction records into the producer `quality_safety_extraction_bundle` shape,
  with a synthetic harness (232 checks). Recorded `judge_ready=false`, `repair_ready=false`. No production wiring.

### Previously (Slice 124, now trunk `242d580`)
- **Slice 124 (Quality Safety Numeric Extraction Contract Design)** defined the safe structured numeric extraction contract
  (`docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`) feeding the existing fact-sheet producer + recompute verifier, plus a
  pure synthetic contract harness (27 passed). Recorded `judge_ready=false`, `repair_ready=false`,
  `next_step=pure_numeric_extraction_record_mapper_v1`. No production code change.

### Previously (Slice 123, now trunk `624a70e`)
- **Slice 123 (Real-Disaster E2E with Advisory Coverage Leg)** validated the *actual* advisory `quality_safety_unified_qa.json`
  artifact path with a synthetic-safe harness (`validate_quality_safety_real_disaster_e2e.py`, 41 checks) across
  `clean_real_case`, `single_confident_wrong_numeric_case`, and the production-shaped `legacy_confused_wrong_case`. Recorded
  closed-vocabulary outcome: `structural_coverage_leg_status=covered`, `numeric_fact_sheet_extraction_leg_status=not_covered`,
  `judge_ready=false`, `repair_ready=false`, `next_step=numeric_extraction_design`. No production code change.

### Previously (Slice 122, now trunk `979bb4e`)
- **Slice 122 (Wire Coverage Adapter into Advisory Artifact)** wired the Slice 121 structural-coverage adapter into the
  advisory `quality_safety_unified_qa.json` artifact. `build_quality_safety_job_artifact_payload` /
  `write_quality_safety_job_artifact` gained optional `source_coverage_report`, `extraction_metadata`,
  `visual_inclusion_plan`, `table_candidates_manifest`, `table_reconstruction_policy` (default `None`), feeding **only** the
  Slice 121 adapter; `_write_quality_safety_unified_qa` reads the already-produced safe sibling JSON artifacts read-only.
  Added `extraction_coverage_status` / `extraction_coverage_summary` / `extraction_coverage_bundle` (closed tokens/counts;
  `numeric_observation_count=0`); `kind`/`artifact_name`/`advisory` and all prior fields unchanged. Advisory/non-blocking;
  never feeds the concept/fact producer or recompute; never upgrades `shippable`/`safety_floor_green`. Job artifact tests 276,
  E2E artifact harness 36.

### Previously (Slice 121, now trunk `b382eed`)
- **Slice 121 (Pure Extraction-Bundle Adapter v1)** added the pure/unwired `pipeline/quality_safety_extraction_bundle_adapter.py`
  mapping already-sanitized structural extraction/coverage artifacts into a normalized **structural coverage bundle**
  (`kind=quality_safety_extraction_coverage_bundle`, distinct from the producer's concept/fact bundle). Closed tokens / counts
  only; `numeric_observations=[]` and `numeric_observation_count=0` always (numeric leg `numeric_observation_recoverable=no`);
  reads only caller dicts, never raises, never mutates. Adapter tests 705/705.

### Previously (Slice 120, now trunk `06deb50`)
- **Slice 120 (Quality Safety Advisory Artifact E2E + Extraction Metadata Inspection)** validated the advisory visible path
  (production build → exact-name fetch → read-only UI display) on a synthetic-safe sample and inspected existing extraction/
  page metadata. Closed-token outcome: `page_ref_shape=mixed`, `leaf_count_recoverable=yes`,
  `numeric_observation_recoverable=no`, `extraction_leg_design_status=partial`; the raw extraction metadata artifact carries a
  source basename, so the sanitized source coverage report (keyed by a source ref) is the preferred adapter input. Added
  `test_scripts/validate_quality_safety_e2e_artifact.py` (22/22) and `docs/QUALITY_SAFETY_E2E_VALIDATION.md`.

### Previously (Slice 119, now trunk `91a1134`)
- **Slice 119 (Quality Safety Advisory UI Display v1)** surfaced `quality_safety_unified_qa.json` in the existing Guide
  Quality advisory UI as a read-only, non-blocking section behind a strict display allowlist (closed statuses/components/check
  ids/severities/verification statuses/warning tokens, booleans/unknowns, non-negative counts, deterministic 0-5 axes, capped
  blocking rows). Missing artifacts degrade calmly to "not available".

### Previously (Slice 118, now trunk `c9644aa`)
- **Slice 118 (Quality Safety Advisory Job Artifact v1)** added `pipeline/quality_safety_job_artifact.py`, a synthetic test
  suite, an exact-name job path/API download case, and one guarded production writer call after `clean.md` exists and before
  rendering. The exact artifact name is `quality_safety_unified_qa.json`; it is advisory-only and stores closed signals only.

### Previously (Slice 117, now trunk `e389697`)
- **Slice 117 (Quality Safety Fact-Sheet Producer v1)** added the pure/unwired producer that maps sanitized structured
  extraction bundles into the fact-sheet schema. It remained offline and unwired: no production job artifact, no API/UI/export
  change, no provider/model/cloud call, no judge, and no repair.

### Previously (Slice 116, now trunk `0bef077`)
- **Slice 116 (Quality Safety Leak Scanner Clean-Case False-Positive Hardening)** changed only the unwired offline leak
  scanner, synthetic tests, and closed-vocabulary docs. It fixed boundary false positives around clean technical terms such
  as `weight`, `weighted`, `weighted_gini`, `await`, `actual`, and `factual` while preserving actual leak signatures and
  structural uncertainty markers.

### Previously (Slice 115, now trunk `92a4fb2`)
- **Slice 115 (Quality Safety Real-Disaster Operator Validation)** added `docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md` and
  updated the handoff docs only. It validated recompute/leak/unified-QA behavior with private local operator material and a
  hand-built local fact sheet, recorded only closed-vocabulary outcomes, and found the blocker fixed by Slice 116:
  `failure_category=clean_case_false_positive`, `component_miss_tokens=[false_positive_leak]`,
  `extraction_leg_covered=false`.

### Previously (Slice 114, now trunk `f3693dc`)
- **Slice 114 (Quality Safety Unified QA Artifact v1)** added `pipeline/quality_safety_unified_qa.py` and
  `test_scripts/test_quality_safety_unified_qa.py` — the pure unified deterministic Quality Safety QA report layer. It
  aggregates Layer-1 eval, recompute verifier, canonical fallback, and verifier-coupled leak scanner outputs into one report
  that determines `shippable` / `safety_floor_green` and emits deterministic axes only. It changed no API, frontend,
  generation, prompt, request schema, render/export/OCR/table/visual, Ask Guide, provider/model/cloud behavior, and did not
  add repair, judge logic, or production runtime wiring.

### Previously (Slice 113, now trunk `4b002c6`)
- **Slice 113 (Quality Safety Verifier-Coupled Leak Scanner v1)** added
  `pipeline/quality_safety_leak_scanner.py` and `test_scripts/test_quality_safety_leak_scanner.py` — the unwired scanner
  that records safe verification context beside leak hits. Recompute verified/failed statuses take priority over canonical;
  it changed no API, frontend, generation, prompt, request schema, render/export/OCR/table/visual, Ask Guide,
  provider/model/cloud behavior, and did not add repair or judge logic.

### Previously (Slice 112, now trunk `1606896`)
- **Slice 112 (Quality Safety Canonical Fixture Matcher v1)** added `pipeline/quality_safety_canonical_matcher.py` and
  `test_scripts/test_quality_safety_canonical_matcher.py` — the unwired fallback-only canonical matcher. Recompute remains
  primary; canonical matching never overrides recompute-verified facts and never hides recompute-failed facts. It changed no
  API, frontend, generation, prompt, request schema, render/export/OCR/table/visual, Ask Guide, provider/model/cloud
  behavior, or `math_verifier.py`.

### Previously (Slice 111, now trunk `9d2050b`)
- **Slice 111 (Quality Safety Recompute Verifier v1)** added `pipeline/quality_safety_recompute_verifier.py` and
  `test_scripts/test_quality_safety_recompute_verifier.py` — the unwired primary numeric truth path that consumes the
  Slice 110 fact-sheet contract and recomputes structured `{method, inputs}` facts. It changed no API, frontend, generation,
  prompt, request schema, render/export/OCR/table/visual, Ask Guide, provider/model/cloud behavior, or `math_verifier.py`.

### Previously (Slice 110, now trunk `ff7c971`)
- **Slice 110 (Quality Safety Fact-Sheet Schema v1)** added `pipeline/quality_safety_fact_sheet.py` and
  `test_scripts/test_quality_safety_fact_sheet.py` — the unwired fact-record/fact-sheet schema (closed
  type/provenance/status/confidence/method vocabularies, safe ids/source refs, bounded values, `max_items` partial
  semantics) that Slice 111+ verification reads. It changed no API, frontend, generation, prompt, request schema,
  render/export/OCR/table/visual, Ask Guide, or provider/model/cloud behavior.

### Previously (Slice 109, now trunk `2bbd644`)
- **Slice 109 (Quality Safety Seed Fixtures v1)** added
  `test_scripts/fixtures/quality_safety/clean_neural_networks_synthetic.json`,
  `test_scripts/fixtures/quality_safety/ambiguous_ensemble_synthetic.json`, and
  `test_scripts/test_quality_safety_seed_fixtures.py`. It also hardened numeric correctness so distinct contradictory values
  for the same synthetic label fail blocking even when one value is correct. Fixtures are sanitized synthetic JSON specs only,
  not a real golden corpus. It changed no API, frontend, generation, prompt, request schema, render/export/OCR/table/visual,
  Ask Guide, or provider/model/cloud behavior.

### Previously (Slice 108, now trunk `133e8e0`)
- **Slice 108 (Quality Safety Eval Harness Skeleton)** added `pipeline/quality_safety_eval_harness.py` and
  `test_scripts/test_quality_safety_eval_harness.py`. The harness is stdlib-only, deterministic, offline, synthetic-fixture
  based, persists no eval JSONL/output by default, and measures leaked reasoning, numeric correctness, worked-answer
  completeness, expected-topic coverage, and mock/practice question count. It changed no API, frontend, generation, prompt,
  request schema, render/export/OCR/table/visual, Ask Guide, or provider/model/cloud behavior.

### Previously (Slice 107, now trunk `03cacc7`)
- **Slice 107 (Guide Quality closeout panel rubric + operator checklist)** surfaced the existing
  `guide_quality_rubric_score.json` artifact in the JobDetails Guide Quality panel and added
  `docs/GUIDE_QUALITY_OPERATOR_VALIDATION.md`, a docs-only closed-vocabulary manual-review record. It changed frontend
  display/panel/verifier files and docs only. No backend production-code files changed; no generation/prompt/provider/
  render/export/OCR/table/visual/Ask Guide behavior changed. Committed `03cacc7`, fast-forward merged, and pushed to
  `chrome-renderer-v1`.

### Previously (Slice 106, now trunk `d34b39e`)
- **Slice 106 (Guide Quality release validation)** added `test_scripts/test_guide_quality_release_validation.py`, a
  deterministic synthetic release checkpoint for Slices 102-105. It calls the real prompt contract, contract lint, source
  coverage, guide quality report v2, QA gate, rubric score, and frontend Guide Quality panel verifier. It is
  validation-only, uses synthetic canaries, persists no private/source/runtime artifacts, and made no production-code changes.
  Committed `d34b39e`, fast-forward merged, and pushed to `chrome-renderer-v1`.

### Previously (Slice 105, now trunk `10041b7`)
- **Slice 105 (Guide Quality Rubric Score v1)** added `pipeline/guide_quality_rubric_score.py`, `Job.guide_quality_rubric_score_json`,
  `_write_guide_quality_rubric_score(job)` after the QA gate writer, and exact-name `_artifact_path` support for
  `guide_quality_rubric_score.json`. It is advisory-only (`blocking:false`), not in generic artifact rows/UI/export selectors,
  and unsupported semantic axes stay `unknown`/`score:null`. No generation/prompt/render/export/Ask Guide behavior changed.
  Committed `10041b7`, fast-forward merged, and pushed to `chrome-renderer-v1`.

### Previously (Slice 104, now trunk `d5acd12`)
- **Slice 104 (JobDetails Guide Quality panel v1)** added `frontend/src/guideQualityDisplay.js` plus
  `frontend/src/components/GuideQualityPanel.jsx`, wired into the JobDetails drawer as a new read-only **Guide Quality** tab
  after Material Coverage. It fetches exact-name artifacts independently, summarizes counts/statuses only, avoids raw JSON
  rendering, and keeps older jobs calm when artifacts are absent. Frontend visibility only; no generation/prompt/provider/
  OCR/table/render/export/Ask Guide changes. Committed `d5acd12`, fast-forward merged, and pushed to `chrome-renderer-v1`.

### Previously (Slice 103, now trunk `71f5f8c`)
- **Slice 103 (Guide Quality QA Gate v1)** added `pipeline/guide_quality_qa_gate.py` (pure, stdlib-only) combining the
  already-sanitized contract lint (Slice 102), guide quality report v2 (Slice 96), source coverage report (Slice 77), and
  numeric math verification (Slice 21) into one advisory `passed`/`warning`/`skipped`/`partial` gate. Counts + closed tokens
  only; `blocking` always `False`; math summarized not rerun. Persisted as exact-name `guide_quality_qa_gate.json` via
  `Job.guide_quality_qa_gate_json` + `_write_guide_quality_qa_gate(job)` + `_artifact_path` route — not in ARTIFACTS / UI /
  exports. Flag-only; never rejects/regenerates/blocks/fails. No FE was added in Slice 103 (Slice 104 adds the UI).

### Previously (Slice 102, now trunk `815a0dc`)
- **Slice 102 (Claude-quality guide prompt contract v1)** added `pipeline/guide_quality_prompt_contract.py` (core rules always
  + 13-section structural contract for comprehensive/long guides) appended once as a `## Guide Quality Contract` block in
  `run_llm_job.py`, plus the flag-only `pipeline/guide_quality_contract_lint.py` writing exact-name
  `guide_quality_contract_lint.json`. Centralized (no preset/style body edits); leak-free; Ask Guide untouched.

### Previously (Slice 101, now trunk `89f8532`)
- **Slice 101 (~100 MB attachment support)** raised the per-attachment ceiling to an env-tunable default (`GUIDEFORGE_MAX_ATTACHMENT_MB`,
  default **150 MB**; 15 MB → 150 MB), shared across the preflight + multipart paths, with a generic filename-free **413** on
  oversize and a matching client-side guard (`frontend/src/uploadLimits.js`). It also folded in two unrelated provider-icon
  SVG refreshes (operator instruction). Live ~100 MB upload returned HTTP 200.

### Previously (Slice 100, now trunk `fbff55d`)
- **Slice 100 (Full Material Coverage E2E release validation)** added a deterministic, synthetic, validation-only release
  checkpoint (`test_scripts/test_full_material_coverage_release_validation.py`, 86 checks) proving the Full Material Coverage
  phase coheres end to end. No product behaviour, no LLM/provider/model/cloud call, no UI change.

### Previously (Slice 99, now trunk `e8d6f86`)
- **Slice 99 (Explain like I'm 10 / Exam answer mode v1)** added an optional study-quality generation mode. When on, the
  guide generator is asked to explain difficult /
    exam-important concepts **two ways** — a beginner-friendly "Explain it simply" block + a formal "Exam answer" block —
    so a student understands the concept and learns the version to write in the exam. **Default off** ⇒ generation prompt
    byte-identical to before.
  - **New pure module `pipeline/dual_explanation_prompt_context.py`** (stdlib-only; no provider/model/OCR/renderer/FastAPI/
    frontend import): `build_dual_explanation_prompt_context(enabled, *, max_items=None)` → `{version,
    kind:"dual_explanation_prompt_context", status (completed/skipped), summary{enabled, prompt_item_count}, prompt_block,
    warnings}`. Only real `True` enables; `None`/`False` ⇒ off; other types ⇒ off + closed `enabled_not_bool` warning.
    Fixed deterministic source-grounded `prompt_block` (two companion blocks; no invented facts/labels/values/citations;
    say what's missing instead of guessing). Reads no source text; never raises.
  - **Prompt integration = `run_llm_job.py`** (`_build_dual_explanation_prompt_block_safely`), appended under the
    `## Dual Explanation Mode` heading after the Slice 93/94/95 attachment guidance, for every generation (paste or
    attachment). Disabled ⇒ empty ⇒ byte-equivalent. Composes with Slice 95 coverage-aware guidance.
  - **Request field `dual_explanation_mode: bool` (default False)** wired into BOTH `/api/jobs/llm` paths (JSON
    `LLMJobRequest` + multipart `_form_bool`) and the `run_llm_job(...)` call; persisted in the job manifest (mirrors the
    `visual_markdown_image_pilot` precedent — persisted, not in the public job-details DTO).
  - **Frontend:** pure helper `frontend/src/dualExplanationOptIn.js` + a Builder toggle ("Explain difficult concepts two
    ways") in the LLM options area; field sent only when true (omitted otherwise); does not touch `page_selections` /
    `material_page_selections`.
  - **It does NOT** add an extra LLM/provider/model/cloud call, change provider/model selection, inspect PDFs/images/OCR,
    reconstruct tables, change render/export, change figure-insertion / material-selection / visual-filter logic, or change
    Ask Guide behaviour. No direct `clean.md` write. Chandra remains blocked by its own live-validation gate.
  - **Tests:** `test_dual_explanation_prompt_context.py` (91 pure), `test_dual_explanation_request.py` (JSON+multipart parse
    / manifest persistence / prompt-block presence-absence / no-leak; skips without FastAPI),
    `frontend/scripts/verify-dual-explanation-mode-ui.mjs`. **Committed `e8d6f86`, merged + pushed to `chrome-renderer-v1`.**

### Previously (Slice 98, now trunk `9f9d838`)
- **Slice 98 (Ask Guide coverage grounding upgrade)** made **Ask Your Guide** aware of the same safe coverage signals the
  guide + JobDetails already use, so a
    user can ask coverage/meta questions ("were any pages excluded?", "did the guide include all figures?", "were tables
    reconstructed?", "why is a diagram missing?", "can I trust the coverage?") and get honest, closed answers. **Ask Guide
    grounding/context slice — counts/statuses only**; course content still comes from the guide/source chunks + citations.
  - **New pure module `pipeline/ask_coverage_grounding.py`** (stdlib-only; imports nothing from `pipeline`, no
    provider/model/OCR/renderer/FastAPI/frontend): `build_ask_coverage_grounding(*, job, source_coverage_report,
    visual_inclusion_plan, table_candidates_manifest, table_reconstruction_policy, guide_quality_report_v2, max_items)` →
    `{version, kind:"ask_coverage_grounding", status, summary, grounding_text, items, warnings}`. Reads inputs for
    decisions only (never echoes a raw field), emits only closed tokens / ints / `None` / bools / fixed strings +
    `ask_grounding_NNNN` ids, degrades to `skipped` on malformed/missing input, never raises. Item kinds:
    `material_selection`, `source_coverage`, `visual_coverage`, `table_policy`, `missing_material`, `guide_quality`.
  - **It reads safe exact-name artifacts + safe job page-selection fields only:** `source_coverage_report.json`,
    `visual_inclusion_plan.json`, `table_candidates_manifest.json`, `table_reconstruction_policy.json`,
    `guide_quality_report_v2.json`, plus the job manifest's `material_page_selection` / `material_page_selections`. It does
    **not** expose source text, table text, captions, OCR, filenames, paths, image refs, asset refs, raw artifact
    warnings, raw URLs, or raw errors.
  - **Integration = Ask Guide model-facing context preamble (not an indexed/citable chunk).** In
    `pipeline/ask_sessions.py`: `build_coverage_grounding_for_job(job)` (reads manifest selection fields + the five
    artifacts via a total/degrade-safe `_read_artifact_json`) → pure builder; `answer_message` threads
    `coverage_grounding_text` into `assemble_prompt`, which injects it into the **system** message after `ANSWER_RULES` +
    the citation-label list, framed by a new `COVERAGE_GROUNDING_RULES` ("internal meta-context, not citable, not course
    content"). No chunk text / citation label added → citation contract unchanged; absent/skipped grounding → empty string
    → prompt byte-identical.
  - **It does NOT** change backend extraction/OCR, inspect PDFs/images/OCR, reconstruct tables, add table text extraction,
    change render/export, change figure insertion semantics, change material page-selection logic, change visual-manifest
    filtering, change providers/models, add UI (no copy/status tweak was needed), or add/call any provider/model/cloud (no
    Chandra/Mistral/Gemini). **Preserved:** direct-answer guard, empty-response guard, `/no_think` (model-facing only),
    citation rules/validation. No direct `clean.md` write. Chandra remains blocked by its own live-validation gate.
  - **Tests:** new `test_scripts/test_ask_coverage_grounding.py` (synthetic dicts; missing/empty → skipped, malformed →
    safe degrade, per-signal summaries, count coercion, `max_items`→partial, deterministic ids, deep-walk no-leak sweep,
    hostile status not echoed, stdlib-only purity guard, + a guarded `ask_sessions` integration section). Reran the
    existing ask suite (`test_ask_context_inventory`, `test_ask_context_prepare`, `test_ask_lexical_hygiene`,
    `test_ask_local_chat`, `test_ask_retrieval_relevance`) + the coverage-artifact regressions. **Committed `9f9d838`,
    fast-forward merged + pushed to `chrome-renderer-v1`.**

### Previously (Slice 97, now trunk `e6e91df`)
- **Slice 97 (JobDetails Material Coverage final panel)** upgraded the JobDetails "Material Coverage" tab into the final
  read-only coverage dashboard: new helpers in `frontend/src/materialCoverageDisplay.js`
  (`summarizeTableCandidatesManifest`, `summarizeTableReconstructionPolicy`, `summarizeGuideQualityReportV2`, composite
  `buildMaterialCoverageFinalModel`), `MaterialCoveragePanel.jsx` rendering 7 safe sections (selections / source coverage /
  figures & diagrams / tables / missing material / guide quality v2 / fixed exact-name artifact links), new verify script
  `verify-material-coverage-final-panel.mjs`. Frontend display only, counts/statuses/checks, no backend generation change.

### Previously (Slice 96, now trunk `2fc6d95`)
- **Slice 96 (Guide quality report v2)** added a deterministic, sanitized `guide_quality_report_v2.json` (new
  `pipeline/guide_quality_report_v2.py`) measuring whether the generated `clean.md` reflects the Slices 82–95 coverage
  signals — scans `clean.md` for **safe counts only** (page-grounded signals; safe `assets/<slug>.png` refs; a closed set
  of static app-authored guidance phrases), compares against the sanitized coverage artifacts, emits one closed check per
  dimension (`source_pages`/`visuals`/`tables`/`missing_material`/`coverage`). **No `clean.md` excerpt persisted.** Written
  after `_write_guide_lint` (post `save_clean_md`) via `job.save_text(...)`; advisory (never changes status / blocks render
  / fails the job). Artifact reached by exact filename only (new `Job.guide_quality_report_v2_json` + `_artifact_path`),
  NOT in generic ARTIFACTS / UI rows / export selectors. Committed `2fc6d95`, merged + pushed.

### Previously (Slice 95, now trunk `c8d3c02`)
- **Slice 95 (Coverage-aware generation prompt v1)** added a single sanitized coverage-aware generation guidance block
  (`pipeline/coverage_aware_prompt_context.py`) appended in `run_llm_job.py::_attach_sources`. Committed `c8d3c02`,
  fast-forward merged, pushed. **Slice 94 is trunk commit `3264b92`** (missing visual/table explainer core).
  - **Purpose:** a single sanitized coverage-aware generation guidance block telling the generator to use the selected
    material completely and honestly — focus only on included pages, never rely on excluded pages/slides, treat source
    coverage gaps as constraints, connect explanations to inserted figures, reconstruct/simplify tables only from source
    text, and add honest missing-material notes (no hallucinated labels/rows/cells/values/captions). It SUMMARISES which
    closed coverage signals are active; it never repeats the per-item Slice 93/94 detail.
  - **It does NOT** change extraction/OCR, inspect PDFs/images, read image bytes, reconstruct tables, extract table text,
    add UI, change render/export, change figure insertion semantics, change material page-selection logic, change
    visual-manifest filtering, or add/call any provider/model/cloud (no Chandra/Mistral/Gemini).
  - **New pure module:** `pipeline/coverage_aware_prompt_context.py` —
    `build_coverage_aware_prompt_context(*, job_request=None, source_coverage_report=None, visual_inclusion_plan=None,
    table_candidates_manifest=None, table_reconstruction_policy=None, table_prompt_context=None,
    missing_material_context=None, full_visual_insertion_enabled=False, max_items=None)` → sanitized context dict
    (`version`/`kind`/`status`/`summary`/`prompt_block`/`items`/`warnings`). Emits one closed signal item per active
    signal in fixed order — `included_page`, `source_gap`, `visual_plan`, `table_policy`, `missing_material` — each with a
    safe `item_id` (`coverage_context_NNNN`), `source_page` `None` (aggregate, not page-anchored), closed `kind`,
    fixed-shape `instruction`. All-inactive/empty/missing/malformed → safe `skipped` + empty block; `max_items`/ceiling →
    `partial`. stdlib-only.
  - **Integration:** `pipeline/run_llm_job.py::_attach_sources` — after the Slice 93 table block + Slice 94 missing block,
    `_build_coverage_aware_prompt_block_safely(...)` builds the context from `{material_page_selection,
    material_page_selections}` + the captured source coverage report + visual inclusion plan + the two table artifacts +
    the Slice 94 missing-material context, and appends the block under `## Coverage-Aware Generation Guidance` only when
    `status` is completed/partial AND `prompt_item_count > 0`; else prompt byte-identical. The source-coverage writer
    helper now returns its report dict (counts reused, no re-read). **No new artifact persisted** (in-memory only).
    Degrade-never-fail.
  - **No change to:** extraction/OCR, table reconstruction (none), PDF/image inspection, providers/models/cloud,
    render/export, figure insertion semantics, material page-selection, visual-manifest filtering, UI, or direct
    `clean.md` writes.
  - **Files:** `pipeline/coverage_aware_prompt_context.py` (new), `pipeline/run_llm_job.py` (imports + two locals + two
    builder helpers + source-coverage writer returns report + safe append), `test_scripts/test_coverage_aware_prompt_context.py`
    (new), three docs.
  - **Validation:** coverage test 106/0; explainer 121/0, prompt-context 108/0, candidate manifest 105/0, policy artifact
    39/0, policy core 145/0, full insertion v2 81/0, render/export 22/0, coverage E2E 79/0, source coverage 59/0 host;
    `compileall` clean; `git diff --check` clean; Docker build + health + `smoke_release.py`. **NOT committed.**
  - **Next:** optionally surface coverage/missing-material notes in UI / persist an artifact (deferred); image-only
    understanding stays deferred. Chandra still blocked by its own live-validation gate.

### Prior position (Slice 94 — committed & merged)
- **Slice 94 (Missing diagram/table explainer core)** is trunk commit `3264b92` (ff-merged + pushed). It added
  `pipeline/missing_material_explainer.py` and wired `_build_missing_material_prompt_block_safely(...)` into
  `run_llm_job::_attach_sources` to append honest "what was missing" guidance (kind + page only; `defer`/`skip_unreadable`
  → unreadable note; `skip_unsafe` counted only; planned visuals flagged only when full insertion is off) under
  `## Missing Visual and Table Guidance` — no reconstruction, OCR/PDF/image inspection, provider/model, render/export,
  figure insertion, material selection, UI, or `clean.md` change.

### Prior position (Slice 93 — committed & merged)
- **Slice 93 (Table reconstruction prompt-context integration v1)** is trunk commit `774a2e4` (ff-merged + pushed). It
  added `pipeline/table_reconstruction_prompt_context.py` and wired `_build_table_prompt_block_safely(...)` into
  `run_llm_job::_attach_sources` to append safe, no-hallucination table guidance (reconstruct/simplify only from source
  text; honest unreadable notes; `skip_unsafe` excluded) — no reconstruction, OCR, provider/model, render/export, figure
  insertion, material selection, UI, or `clean.md` change.

### Prior position (Slice 92 — committed & merged)
- **Slice 92 (Table candidate manifest + reconstruction-policy artifacts)** is trunk commit `ea3f321` (ff-merged +
  pushed). It added `pipeline/table_candidate_manifest.py` + `pipeline/table_reconstruction_policy_artifact.py`, two
  `Job` path props, two exact-name `_artifact_path` branches (NOT in `ARTIFACTS`/UI/export), and persists
  `table_candidates_manifest.json` + `table_reconstruction_policy.json` derived only from the sanitized visual manifest —
  no table reconstruction, prompt/provider/model, render/export, figure insertion, material selection, UI, or `clean.md`
  change. `screenshot_insert_count` always `0`.

### Prior position (Slice 91 — committed & merged)
- **Slice 91 (Full figure insertion export/render validation)** is trunk commit `ff7bc70` (ff-merged + pushed). It added
  `find_all_exportable_visual_assets` (uncapped, ceiling-bounded), removed the export bundle cap-2 ride-along, and proved
  the HTML/PDF/DOCX renderers were already uncapped — no figure selection/planning, material selection, prompt/provider/
  model, UI, or `clean.md` change.

### Prior position (Slice 90 — committed & merged)
- **Slice 90 (Full non-table figure insertion v2)** is trunk commit `096148f` (ff-merged + pushed). Branched from fresh
  trunk after Slice 89 (`b879590`).
  - **Purpose:** turn *planned* non-table visuals into *inserted* guide content. When visuals are enabled it inserts **all
    useful planned non-table figures from included pages** (deterministic Slice 83 safety filtering), not the legacy
    top-1/top-2 cap. **Not** "insert every crop": table-like, decorative/logo/header/background, tiny, blank, unsafe, and
    unmappable records are still skipped. No table reconstruction; no prompt/provider/model/cloud; no UI; no render/export
    code change.
  - **Gate (unchanged two-key AND + mode switch).** Insertion still needs the env master switch
    (`GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT`) AND the per-job opt-in (`visual_markdown_image_pilot`). New
    server-side **mode switch** `GUIDEFORGE_ENABLE_FULL_VISUAL_INSERTION` (off by default) selects the plan-driven full path;
    off ⇒ legacy capped pilot byte-identical. The mode switch never enables insertion alone. Default output unchanged.
  - **Safe candidate mapping (Slice 84 deferral resolved).** Planner emits a safe generated `candidate_id`
    (`candidate_id_for_manifest_position` → `visual_candidate_NNNN`, a positional ordinal, never slug/path/filename/ref);
    insertion re-derives `{candidate_id: record}` by the same formula. Public plan gains exactly this one closed-shape field.
  - **Insertion** (`pipeline/visual_markdown_insertion.py`): `is_full_visual_insertion_enabled()`,
    `select_full_visual_markdown_candidates(job, *, manifest, plan)` (ordered; de-duped by candidate_id + asset slug; each
    record re-validated by the **unchanged** hard gates — `fitz_local` `extracted_figure` only, safe `assets/<slug>.png`,
    real file in job dir, never Chandra/Mistral/page-signal), `_apply_full_visual_insertion`. Reuses
    `insert_visual_markdown_references` (source-page anchor else one `## Visual References` section). Captions forced to the
    generic page-derived convention (no raw caption/OCR can ride through). Degrade-never-fail.
  - **Files:** `pipeline/visual_inclusion_planner.py` (+`candidate_id`), `pipeline/visual_markdown_insertion.py`,
    `test_scripts/test_full_visual_insertion_v2.py` (new), `test_scripts/test_visual_inclusion_planner.py` +
    `test_scripts/test_visual_inclusion_plan_artifact.py` (schema allows the safe `candidate_id`), three docs.
    `visual_inclusion_plan_artifact.py` / `run_llm_job.py` / `run_markdown_job.py` unchanged.
  - **Validation:** `test_full_visual_insertion_v2.py` 81/0; reran inclusion planner 179/0, plan artifact 64/0, manifest
    65/0, manifest-planning 47/0, coverage E2E 79/0, pilot trace 56/0, caption polish 132/0, multifigure 63/0, quality gate
    50/0, export asset 9/0, table policy 145/0, legacy insertion 53/0; `compileall api pipeline test_scripts` clean; Docker
    build + health + `smoke_release.py` 29/0 (default output unchanged). **Committed `096148f` + ff-merged + pushed.**
  - **Followed by:** Slice 91 (above) — validated PDF/DOCX/HTML/export with many figures and removed the export ride-along
    cap-2.

### Prior position (Slice 89 — committed & merged)
- **Working tree:** **Slice 89 (Full Material Coverage controls and warnings) — COMMITTED `b879590` + MERGED (ff) + PUSHED**
  to `chrome-renderer-v1` (branched from fresh trunk after Slice 88 was committed/merged/pushed). Slice 88 is trunk commit
  `769d1f5`. Added Builder `MaterialCoverageControls` (active/inactive state, summary, generic invalid-token hint, scope +
  honest "not enabled yet" copy, "Clear exclusions"), JobDetails "What this means" notes, pure helper
  `frontend/src/materialCoverageWarnings.js`, and `verify-material-coverage-warnings.mjs`. Frontend UX/control only; no
  backend field; Slice 87 payload shape unchanged.

### Prior position (Slice 88 — committed & merged)
- **Working tree:** **Slice 88 (JobDetails material coverage display) — COMMITTED `769d1f5` + MERGED (ff) + PUSHED** to
  `chrome-renderer-v1` (branched from fresh trunk after Slice 87 was committed/merged/pushed). Slice 87 is trunk commit
  `844e394`.
  - **Purpose:** add the **first read-only surface** for the Full Material Coverage signals — a "Material Coverage" tab in
    Job Details that shows safe counts/status after a job finishes. **Display only.**
  - **Data sources (already-safe only):** the `material_page_selection(s)` envelopes echoed by the job response, plus the
    **exact-name** artifacts `source_coverage_report.json` (Slice 77) and `visual_inclusion_plan.json` (Slice 84), fetched
    through the existing `getJobArtifact` / `artifactUrl` helpers. **No new backend route, no client.js change** — 404 ⇒
    neutral "not available".
  - **Helper** `frontend/src/materialCoverageDisplay.js` (`summarizeMaterialSelections`, `summarizeSourceCoverage`,
    `summarizeVisualInclusionPlan`, `buildMaterialCoverageDisplayModel`); **panel**
    `frontend/src/components/MaterialCoveragePanel.jsx` wired into `RecentJobsPanel.jsx` as a `Gauge`-icon drawer tab; new
    neutral `.sg-tag-slate` class. All degrade-never-throw, counts/booleans/closed tokens only.

### Prior position (Slice 87 — committed & merged)
- **Working tree:** **Slice 87 (Builder UI for per-attachment page/slide exclusions) — COMMITTED `844e394` + MERGED (ff) +
  PUSHED** to `chrome-renderer-v1` (branched from fresh trunk after Slice 86 was committed/merged/pushed). Slice 86 is
  trunk commit `3db8572`.
  - **Purpose:** add the **first Builder UI control** on top of the Slices 78–86 Full Material Coverage backend, so a user
    can set per-attachment page/slide **exclusions** and submit them through the already-merged `material_page_selections`
    field. UI-wiring only — no backend/extraction/visual/table/render/export/prompt/provider/visual-pilot change.
  - **New pure helper** `frontend/src/materialPageSelections.js`: `parsePageListInput` (positive 1-based ints + simple
    ranges `2,4-6,10`; dedupe/sort; closed-vocabulary warnings, never the raw token), `buildMaterialPageSelections`
    (per-attachment raw inputs **by upload order** → safe envelope with `attachment_<index>` keys, exclude-mode models;
    omits empty attachments; never filenames/paths), `hasActiveMaterialSelections` (send-gate).
  - **Builder** (`BuilderWorkspace.jsx`): `materialExclusions` state keyed by stable `attachmentKey(file)`; a
    `MaterialExclusionField` under each paginated (`.pdf`/`.pptx`) attachment; at submit, mapped by upload order to the
    envelope and threaded `buildBuilderPayload → buildLlmPayload`, which adds `material_page_selections` only when active.
  - **Request** (`api/client.js`): `material_page_selections` added to the multipart object-stringify whitelist; absent
    when no exclusion is active. **`page_selections` (filename-keyed extraction ranges) preserved exactly — separate.**

### Prior position (Slice 86 — committed & merged)
- **Working tree:** **Slice 86 (Material Coverage E2E validation harness) — COMMITTED `3db8572` + MERGED (ff) + PUSHED** to
  `chrome-renderer-v1` (branched from fresh trunk after Slice 85 was committed/merged/pushed). Slice 85 is trunk commit
  `8a1b780`.
  - **Purpose:** add a deterministic, synthetic **E2E validation harness** that proves the Slices 76–85 Full Material
    Coverage backend chain works together — *before* any Builder UI is built on top of it.
  - **Validated chain:** `material page selection → text extraction page filtering → visual manifest page filtering →
    visual inclusion plan → table reconstruction policy → source/visual/material coverage summary`, composing the
    already-merged pure helpers (`apply_material_selection_to_page_universe`, `page_is_in_material_selection`,
    `build_visual_assets_manifest(..., page_filters=...)`, `build_visual_inclusion_plan`,
    `build_table_reconstruction_policy`, `build_source_coverage_report`).
  - **New test:** `test_scripts/test_material_coverage_e2e_validation.py` (**79/0** on host). Synthetic two-attachment
    scenario: universes `{1,2,3,4}` / `{5,6,7,8}`, global `exclude 2,4,6,8`, per-attachment override `include 1,9` on
    `attachment_0`. Effective sets resolve to `{1}` (override beats global; page 9 dropped as out-of-universe) and `{5,7}`
    (global fallback).
  - **Proven:** per-attachment overrides global; `page_selections` caps the universe (material can't expand it); excluded
    pages absent from extraction; visual records from excluded pages filtered (only `{1,5,7}` survive); full plan includes
    all useful non-table visuals (4, not top 1–2); decorative/tiny/table-like not planned as normal visuals; table-like
    routed to the table policy (all 4 handled, reconstruct/simplify), `screenshot_insert_count` stays `0`; coverage counts
    deterministic + sanitized; hostile-canary no-leak sweep across every stage; identical serialization on repeat.
  - **What changed:** new `test_scripts/test_material_coverage_e2e_validation.py` + docs only. **No production wiring** —
    no `pipeline/material_coverage_validation.py` was needed (test-only harness). `api/server.py`, `run_llm_job.py`,
    `job_manager.py`, the planner/artifact, `visual_markdown_insertion.py`, renderers, exporters, prompts, providers,
    frontend, visual-pilot files all unchanged.
  - **Scope:** validation-only — no API route, no job execution wiring, no extraction/OCR routing, no render/export/prompt/
    provider change, no visual-pilot ranking/classification/cap/default/two-key-gate/caption change, no table
    reconstruction, **no new job artifact persisted**, no Chandra/Mistral/Gemini/model/provider/cloud call, no direct
    `clean.md` write, no table manifest invented. Closed warning tokens only; no leaks (hostile-canary tested). Chandra
    remains blocked by its own live-validation gate. Docker rebuild **not required** (pure/unwired). **Slice 86 is NOT
    committed.**

### Prior position (Slice 85 — committed & merged)
- **Working tree:** **Slice 85 (table reconstruction/simplification policy core) — COMMITTED `8a1b780` + MERGED (ff) +
  PUSHED to `chrome-renderer-v1`** on branch `slice85-table-reconstruction-policy-core` (branched from fresh trunk after
  Slice 84 was committed/merged/pushed). Slice 84 is now trunk commit `7cc9d6f`.
  - **Purpose:** add a pure, deterministic **policy core** that decides what should later happen to a table-like candidate.
    The Slice 83/84 non-table planner+artifact deliberately **skip table-like material**; tables must not be treated as
    ordinary screenshot visuals. This slice defines that decision layer only — **no actual table reconstruction yet.**
  - **New pure module:** `pipeline/table_reconstruction_policy.py` (stdlib-only, unwired) →
    `classify_table_candidate(candidate)` and `build_table_reconstruction_policy(candidates, *, max_items=None)`.
    Consumes synthetic / sanitized *table-candidate-shaped* dicts; returns a sanitized policy dict
    (`version, kind, status, summary, items, warnings`). **No table manifest exists today and this slice invents none.**
  - **Product rule:** a table should generally **not** be inserted as a screenshot. Future modes (not implemented here)
    are `reconstruct_with_original` (original table text + simpler/clearer version) and `simplify_only` (simpler version
    only), plus `defer`, `skip_unreadable`, `skip_unsafe`. `screenshot_insert_count` is **always 0**.
  - **Rules:** table-likeness from closed tokens; non-table → `not_table_like` (no item, never a screenshot); unsafe →
    `skip_unsafe`; missing/invalid `source_page` → `defer`; insufficient structure → `skip_unreadable`; low confidence →
    `defer`; text-layer present → `reconstruct_with_original`; text-layer absent/unknown (with structure) → `simplify_only`.
    Closed/deterministic `preserve` list (`headers, column_labels, row_labels, exam_terms, numeric_values, units`).
    Default handles **ALL** candidates; `max_items` is a defensive ceiling only.
  - **What changed:** new `pipeline/table_reconstruction_policy.py`, new
    `test_scripts/test_table_reconstruction_policy.py` (**145/0** on host), docs. **No production wiring** —
    `api/server.py`, `run_llm_job.py`, the visual-inclusion planner/artifact, `visual_markdown_insertion.py`, renderers,
    exporters, prompts, providers, frontend all unchanged.
  - **Scope:** pure policy core only — no API route, no job execution wiring, no extraction/OCR routing, no render/export/
    prompt/provider behavior change, no visual-pilot ranking/classification/cap/default/two-key-gate/caption change, no
    Chandra/Mistral/Gemini/model/provider/cloud call, no direct `clean.md` write, no table manifest invented. Closed
    warning tokens only; no leaks (hostile-canary tested). Chandra remains blocked by its own live-validation gate. Docker
    rebuild **not required** (pure/unwired). **Slice 85 was committed `8a1b780`, merged (ff), and pushed to
    `chrome-renderer-v1`.**

### Prior position (Slice 84 — committed & merged)
- **Working tree:** **Slice 84 (persist visual inclusion plan artifact) — COMMITTED `7cc9d6f` + MERGED (ff) + PUSHED to
  `chrome-renderer-v1`** on branch `slice84-visual-inclusion-plan-artifact` (branched from fresh trunk after Slice 83 was
  committed/merged/pushed). Slice 83 is now trunk commit `72e1f87`.
  - **Purpose:** persist the Slice 83 planner output as the safe exact-name job artifact `visual_inclusion_plan.json`,
    derived **only** from the already-sanitized `visual_assets_manifest.json`. Sanitized, deterministic, degrade-never-fail.
  - **New writer:** `pipeline/visual_inclusion_plan_artifact.py` → `write_visual_inclusion_plan(job, visual_manifest=None)`
    builds the Slice 83 plan and writes deterministic JSON via `job.save_text(...)`. Disk-write failure prints a safe
    message (exc type only) and returns the in-memory plan; generation never fails.
  - **New `Job.visual_inclusion_plan_json`** = `<job>/visual_inclusion_plan.json`. **Exact-name download only** via
    `api/server.py` `_artifact_path` (`application/json`), modeled on `source_coverage_report.json`. NOT in `ARTIFACTS`,
    generic `_artifact_urls`/`_artifact_details` rows, `EXPORT_ARTIFACTS`, `EXPORT_ARTIFACT_ALIASES`, or
    `VISUAL_ADVISORY_EXPORT_ARTIFACTS`. No UI.
  - **Integration:** `run_llm_job._attach_sources`, right after the visual manifest is written + read back, alongside the
    scoring/replacement-plan writers, via `_write_visual_inclusion_plan_safely(...)`. Written when the manifest is written;
    missing/skipped/malformed manifest → safe **skipped** plan; non-PDF / no-extraction jobs omit it.
  - **Behavior inherited from Slice 83:** plans **ALL eligible useful non-table visuals by default (not top-1/2)**, skips
    **table-like** records (counted; table reconstruction is Slice 85), skips decorative/logo/header/footer/background/
    watermark/tiny/blank/low-information/unsafe/unknown records.
  - **Candidate mapping deferred:** Slice 84 keeps the Slice 83 plan schema **as-is** (smallest safe option). No
    `candidate_id` added. If a future insertion slice needs one it must be a **generated internal id**
    (e.g. `visual_candidate_0001`), never a filename/path/raw image-ref/caption/OCR/source text.
  - **What changed:** new `pipeline/visual_inclusion_plan_artifact.py`, new `Job.visual_inclusion_plan_json`, exact-name
    `_artifact_path` mapping, `run_llm_job` wiring, new `test_scripts/test_visual_inclusion_plan_artifact.py` (**62/0** on
    host; `api.server` section SKIPs without FastAPI, covered in Docker). `visual_markdown_insertion.py`, visual-pilot
    files, renderers, exporters, prompts, providers, frontend all unchanged.
  - **Scope:** persistence only — no Markdown insertion, no table policy (Slice 85), no PDF/DOCX render change, no export
    bundle change, no API beyond exact-name download, no UI, no extraction/OCR routing change, no visual-pilot
    ranking/classification/cap/default/two-key-gate/caption change, no Chandra/Mistral/Gemini/model/provider/cloud call, no
    direct `clean.md` write. Closed warning tokens only; no leaks (hostile-canary tested). Chandra remains blocked by its
    own live-validation gate.
  - **Slice 84 was committed `7cc9d6f`, merged (ff), and pushed to `chrome-renderer-v1`.**

### Prior position (Slice 83 — committed & merged)
- **Working tree:** **Slice 83 (full non-table visual inclusion planner core) — COMMITTED `72e1f87` + MERGED (ff) +
  PUSHED to `chrome-renderer-v1`** on branch
  `slice83-full-visual-inclusion-planner-core` (branched from fresh trunk after Slice 82 was committed/merged/pushed).
  Slice 82 is now trunk commit `fd3fb97`.
  - **Purpose:** add a pure, deterministic planner that decides **which non-table visuals from the already
    material-page-filtered visual manifest** to plan for future guide inclusion. Deliberate move **away from "top 1–2
    visuals forever"** toward Full Material Coverage.
  - **Product goal:** include **all useful non-table figures/diagrams/graphs/charts/instructional visuals from included
    pages, after deterministic safety filtering** — NOT every crop/logo/decorative header/background/tiny/blank/low-info
    crop, and NOT tables-as-screenshots.
  - **New module:** `pipeline/visual_inclusion_planner.py`, stdlib-only, **unwired**. API
    `build_visual_inclusion_plan(visual_manifest: dict | None, *, max_items: int | None = None) -> dict`.
  - **Default plans ALL eligible non-table visuals** (no hard cap at 1/2). `max_items` is a defensive ceiling only
    (default `None`); when it truncates → `status:"partial"` + `max_items_applied`.
  - **Eligibility:** positive-int `source_page`; not table-like; not decorative/logo/header/footer/background/watermark;
    not unsafe; not low-information (`blank_or_low_text`); not tiny (`crop_*_px < 24`); recognized non-table type
    (`page_visual_signal`→supporting, `extracted_figure`→primary figure, explicit kind tokens honored with `plot→graph`,
    `illustration→figure`). **Table-like records skipped** (counted) — table reconstruction is Slice 85, never screenshot
    insertion. **Unknown type → skipped** (`visual_type_unknown`, the safer choice; documented). Manifest order preserved
    (stable sort source→page→position); internal `asset_id` used for dedupe only, never emitted.
  - **Plan shape:** `{version, kind:"visual_inclusion_plan", status, summary{source_count, candidate_count, planned_count,
    non_table_planned_count, table_like_skipped_count, unsafe_or_incomplete_skipped_count, page_count_with_planned_visuals},
    items[], warnings[]}`. Item: `{plan_index, source_index, source_page, visual_kind, inclusion_role, reason, warnings}`.
  - **What changed:** new `pipeline/visual_inclusion_planner.py` + new `test_scripts/test_visual_inclusion_planner.py`
    (**178/0** on host). No other file touched — `run_llm_job.py`, `visual_markdown_insertion.py`, visual-pilot files,
    renderers, exporters, prompts, `api/server.py`, frontend all unchanged.
  - **Scope:** planner-core only and unwired — no artifact persisted (Slice 84), no table policy (Slice 85), no
    Markdown/PDF/DOCX insertion, no API/UI, no extraction/OCR routing change, no render/export/prompt/provider change, no
    visual-pilot ranking/classification/cap/default/two-key-gate/caption change, no Chandra/Mistral/Gemini/model/provider/
    cloud call, no direct `clean.md` write. Closed warning tokens only; no leaks (hostile-canary tested).
  - **Roadmap (83–86 = Full Material Coverage backend foundation):** **83** planner core (this) · **84** persist
    `visual_inclusion_plan.json` (safe exact-name artifact; stable safe candidate IDs + source pages OK, never raw image
    refs/filenames/text) · **85** table reconstruction/simplification policy core · **86** material-coverage E2E. **No
    UI** until the backend chain proves selections apply consistently to extraction, visual candidates, table policy, and
    coverage reporting.
  - **Slice 83 is COMMITTED `72e1f87`, fast-forward merged, and pushed to `chrome-renderer-v1`.**

### Prior position (Slice 82 — committed & merged)
- **Slice 82 (apply material page selections to visual/table manifests) — COMMITTED `fd3fb97` + MERGED to
  `chrome-renderer-v1` (fast-forward) + PUSHED** on branch `slice82-apply-material-page-selection-to-visuals`. It applied
  the **same** effective material page selection Slice 81 used for text extraction to **visual-assets manifest planning**:
  `_attach_sources` keeps `visual_page_filters` in lockstep with `extraction_metadata_sources` and passes them as the new
  `page_filters=` kwarg to `write_visual_assets_manifest`, which drops `page_visual_signal` candidates whose `source_page`
  is not in their source's allowed set (the Slice-81 intersection of the `page_selections` universe with the material
  selection — never expands beyond it). Missing/invalid `source_page` under an active filter is dropped conservatively
  (`material_selection_visual_page_unknown`). No table manifest exists yet (reserved token
  `material_selection_table_manifest_not_present`). New pure helper `page_is_in_material_selection(...)`. Validated: host
  suite green; Docker `test_page_selection_request_persistence.py` 182/0 and `test_page_selections.py` 24/24; Docker
  rebuild + `/api/health` + `smoke_release.py` 29/0/0.

### Prior position (Slice 81 — committed & merged)
- **Slice 81 (apply material page selections to extraction/content planning) — COMMITTED `7ca109d` + MERGED to
  `chrome-renderer-v1` (fast-forward) + PUSHED** on branch `slice81-apply-material-page-selection-to-extraction`. It
  applied the persisted material selection to attachment text extraction: `_attach_sources` filters the pages passed to
  `extract_file(path, pages=...)` via the new pure `apply_material_selection_to_page_universe(...)`, bounded by the
  load-bearing `page_selections` universe (further-filter only, never expand); `exclude`/`all` with no known universe
  defers. Per-attachment over global precedence. Degrade-never-fail, closed tokens only.

### Prior position (Slice 80 — committed & merged)
- **Slice 80 (per-attachment material page-selection persistence) — COMMITTED `55eb243` + MERGED to
  `chrome-renderer-v1` (fast-forward) + PUSHED** on branch `slice80-per-attachment-material-page-selections`. It added
  the top-level `material_page_selections` field, persisted as the envelope `{version, attachments:{attachment_<i>:
  <model>}, warnings}` with SAFE `attachment_<index>` keys only (never filenames/paths), wired into both request paths,
  the retry path, and the response echoes; the global `material_page_selection` (Slice 79) remained the fallback.
  Degrade-never-fail; applied to nothing.

### Prior position (Slice 79 — committed & merged)
- **Slice 79 (persist page/slide selection with job requests) — COMMITTED `d4d2513` + MERGED to `chrome-renderer-v1`
  (fast-forward) + PUSHED** on branch `slice79-page-selection-request-persistence`. It added the top-level
  `material_page_selection` field on `LLMJobRequest` (Slice 78 normalized shape), wired into both request paths, the
  retry path, and the response echoes via `_normalize_material_page_selection`/`_safe_material_page_selection`, and
  persisted it in the `Job.create` manifest. Separate from the load-bearing `page_selections` field; degrade-never-fail;
  applied to nothing. New `test_scripts/test_page_selection_request_persistence.py`.

### Prior position (Slice 78 — committed & merged)
- **Slice 78 (page/slide inclusion-exclusion pure model) — COMMITTED `ee04f55` + MERGED to `chrome-renderer-v1`
  (fast-forward) + PUSHED** on branch `slice78-page-slide-selection-model`. It added stdlib-only
  `pipeline/page_selection_model.py` (`normalize_page_selection`, `apply_page_selection`, `summarize_page_selection`)
  plus synthetic tests `test_scripts/test_page_selection_model.py`. Pure/unwired: no API route, no request/job-manifest
  wiring, no extraction/OCR, no visual manifest, no render/export, no frontend/UI, no prompt, no provider/model/cloud
  call, no `clean.md`, and no visual-pilot behavior changed.

### Prior position (Slice 77 — committed & merged)
- **Slice 77 (source coverage report artifact writer) — COMMITTED `3ebfe54` + MERGED to `chrome-renderer-v1`
  (fast-forward) + PUSHED** on branch `slice77-source-coverage-report-artifact`. It persisted Slice 76's pure report as
  the safe exact-name artifact `source_coverage_report.json` (new `pipeline/source_coverage_artifact.py`,
  `Job.source_coverage_report_json`, an exact-name `_artifact_path` mapping, and `_attach_sources` wiring after
  extraction metadata / optional visual manifest). Exact-name download only — not added to `ARTIFACTS`, generic
  JobDetails rows, export selectors, or export ZIP ride-alongs. Deterministic, closed-vocabulary, degrade-never-fail;
  no `clean.md`, no extraction/OCR routing, no render/export/prompt/provider/model/cloud, no Chandra/Mistral/Gemini
  call, and no visual-pilot behavior changed.

### Prior position (Slice 76 — committed & merged)
- **Slice 76 (source coverage report pure core) — COMMITTED `91e3845` + MERGED to `chrome-renderer-v1`
  (fast-forward) + PUSHED** on branch `slice76-source-coverage-report-core`. It added pure stdlib-only
  `pipeline/source_coverage_report.py` with public API
  `build_source_coverage_report(extraction_metadata, *, visual_manifest=None)` plus synthetic tests in
  `test_scripts/test_source_coverage_report.py`. No API route, no job artifact writer, no `clean.md`, no frontend/UI,
  no export, no extraction/OCR routing, no render/prompt/provider/model/cloud behavior, and no visual-pilot behavior
  changed.

### Prior position (Slice 75 — committed & merged)
- **Slice 75 (diverse visual-pilot exit validation) — COMMITTED `00c3f79` + MERGED to `chrome-renderer-v1`
  (fast-forward) + PUSHED** on branch `slice75-visual-pilot-diverse-exit-validation`. This was a **validation /
  exit-decision slice only**: not another caption polish slice, not another table/diagram heuristic slice, and not a UI
  slice. It recorded whether enough diverse, manually categorized, known non-private operator samples were available to
  decide whether the default-off visual markdown pilot should remain opt-in, become more discoverable, or pause pending a
  controlled understanding layer. Chandra remains blocked by its own live-validation gate.
  - **Outcome:** `diverse_visual_pilot_exit_validation: not_run`; `reason:
    non_private_diverse_samples_not_available`. A local operator sample count alone was not enough: no safe manual
    mapping from samples to the requested closed categories was available, and the slice rules forbid guessing categories
    from local PDFs. No harness run; no trace/render/export artifacts.
  - **Target categories:** `math_heavy_deck`, `mostly_text_only_pdf`, `low_quality_or_scan_like_pdf`,
    `mixed_diagrams_tables_deck`, and `no_good_figures_deck` were all recorded as `status: skipped`,
    `skip_reason: sample_not_available`, `failure_category: sample_unavailable`, `no_leak_sweep: clean`, with all
    candidate/type/selected/render/export counts zero or `not_applicable`.
  - **Aggregate exit record:** `validated_category_count: 0`, `available_category_count: 0`,
    `pilot_inserted_count: 0`, `graceful_omission_count: 0`, `bad_selection_count: 0`, `caption_safe_count: 0`,
    `pdf_image_visible_count: 0`, `docx_render_ok_count: 0`, `export_png_included_count: 0`,
    `no_leak_sweep: clean`, `exit_recommendation: insufficient_evidence`, `exit_reason:
    diverse_validation_insufficient_sample_count`.
  - **Decision:** keep the visual markdown pilot default-off / opt-in until diverse evidence exists. The morphology loop
    remains paused; the caption micro-loop is not starting; Slice 75 did not change visual behavior.
  - **Files:** docs only — `docs/VISUAL_PILOT_OPERATOR_VALIDATION.md`, `docs/CURRENT_TASK.md`, this file,
    `docs/DECISIONS.md`. No frontend/UI; no production pipeline/API code; no harness correction; no extraction/
    OCR-routing/prompt/render/export/caption/cap/ranking/classification/selection/provider change; no Chandra/model/
    provider/cloud call. No committed binary/image/PDF/DOCX/ZIP/runtime output, eval JSON, or selection trace. No sample
    path/filename, document text, OCR text, source caption/table text, image bytes, base64, data URI, full URL, raw argv,
    provider payload, token, model/mmproj/executable path, or raw exception recorded. **Slice 75 commit `00c3f79`,
    fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

### Prior position (Slice 74 — committed & merged)
- **Slice 74 (visual caption / source-page polish) — COMMITTED `9e92e5a` + MERGED to `chrome-renderer-v1`
  (fast-forward)** on branch `slice74-visual-pilot-caption-page-polish` (branched from fresh trunk after Slice 73 was
  committed/merged). **Final in-lab visual-pilot polish slice — NOT a new heuristic/caption micro-loop.** It adds a
  safe, generic italic caption line **below** each inserted visual; it changes **no** selection, ranking,
  classification, cap, default, two-key gate, export, renderer, provider/model/cloud, OCR-routing, prompt, or UI
  behavior. The table-vs-diagram morphology loop is **paused/frozen** after Slice 73's real-sample success. **No
  separate caption-validation follow-up slice exists.**
  - **Status flags:** `visual_pilot_morphology_loop_status: paused_after_real_success`,
    `visual_pilot_polish_scope: final_in_lab_caption_page_polish`,
    `next_recommended_slice: diverse_visual_pilot_exit_validation`.
  - **What changed (one file):** `pipeline/visual_markdown_insertion.py` gains `_visual_caption_line(source_page)`
    (returns exactly `*Source visual, page N.*` for a positive integer page, else `*Source visual.*`) and
    `build_visual_markdown_block(candidate)` (appends that caption one blank line below the unchanged
    `build_visual_markdown_image(...)` ref); both insert entry points emit the block. The caption is a fixed closed
    string + bounded integer page only — no source filename, path, title, raw manifest caption, OCR/document/table text,
    base64/data URI, provider payload, token, or URL can survive into it. Caption construction degrades-never-fails to
    the image ref alone.
  - **Invariants proven:** image refs byte-identical, selected order/count/ranking unchanged, default-off byte-identical,
    caption only when **both** gates on, cap hard-capped at **2** / default **1**, no UI count selector, export ref-scan
    + Slice 68 trace unchanged (trace never carries the caption text).
  - **Tests:** new `test_scripts/test_visual_pilot_caption_page_polish.py` (24 scenarios) — **133 PASS / 0 FAIL / 0 SKIP
    in the container** (host 1 SKIP: python-docx absent). Full visual-pilot + insertion/render/export/options/anki
    suites + offline eval pass on host; image rebuilt + recreated, `/api/health` `{"ok":true}`, `smoke_release.py`
    29/0/0, visual-pilot suite (incl. the new test) re-run inside the container all green. `git diff --check` clean.
  - **Optional real operator caption validation:** `caption_operator_validation: not_run`; `reason:
    non_private_operator_sample_not_available`. The non-private sample is not available this session; no real caption
    rerun, **no sanitized `caption_operator_validation` recorded** (none invented). It may be inspected inside Slice 74
    when the sample is available (no follow-up slice).
  - **Next slice is NOT more visual polish/heuristics** — it should be a **diverse validation / exit-decision** slice
    across multiple document types (math-heavy deck, mostly text-only PDF, low-quality/scan-like PDF if available, mixed
    diagrams/tables deck, and a no-good-figures deck to verify graceful omission) to decide whether visual markdown stays
    opt-in, becomes more discoverable, or pauses pending a controlled understanding layer (e.g. Chandra, still blocked by
    its own live-validation gate).
  - **Files:** `pipeline/visual_markdown_insertion.py`, new `test_scripts/test_visual_pilot_caption_page_polish.py`, and
    docs (`CURRENT_TASK.md`, this file, `DECISIONS.md`). No frontend/UI; no extraction/OCR-routing/prompt/render/export
    change; no Chandra/model/provider/cloud call. Only a fixed caption string + bounded page integer is emitted — no real
    PDF path/filename, document/OCR/table/source-caption text, image bytes, base64, data URI, full URL, raw argv, token,
    or model/mmproj/executable path. Every test PNG is runtime-built in a temp dir; nothing binary/image/PDF/DOCX/ZIP/
    runtime committed. **Slice 74 commit `9e92e5a`, fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

### Prior position (Slice 73 — committed & merged)
- **Slice 73 (dense-wrapped-table real operator validation) — COMMITTED `76e837b` + MERGED to `chrome-renderer-v1`
  (fast-forward)** on branch `slice73-visual-pilot-dense-wrapped-operator-validation` (branched from fresh trunk after
  Slice 72 was committed/merged). **Validation/docs slice — no production pipeline/API/frontend code changed; no
  heuristic tuned; no ranking/cap/default/gate/render/export/extraction-OCR routing change; no model/provider/cloud
  call.** It reran the existing operator harness on the real, **non-private** sample now that Slice 72's dense /
  wrapped-cell two-column table detection is on trunk, then read Slice 68's sanitized selection trace + manually
  inspected the rendered PDF/HTML/DOCX. **No harness correction was needed.**
  - **Outcome this session — the long-standing `tables_only` result finally flipped.** Recorded (sanitized, closed
    vocab): `dense_wrapped_table_operator_validation: run`, `status: ok`, `trace_artifact_present: true`,
    `trace_no_leak_sweep: clean`, `effective_max_images: 2`, `inserted_visual_count: 2`, `safe_candidate_count: 11`,
    `unsafe_candidate_count: 0`, `selected_count: 2`,
    `type_counts {diagram_or_figure: 9, reconstructable_table: 2, unknown: 0, decorative_or_low_information: 0}`,
    **`selected_visual_type: diagrams_or_figures_present`**, **`irreplaceable_visual_selected: true`**,
    `selected_figures_quality: all_useful_or_acceptable`,
    **`selection_explanation: diagrams_selected_after_dense_table_fix`**,
    `pdf_render_ok/pdf_image_visible/docx_render_ok/export_zip_ok/export_png_included: true`,
    `warnings: [multiple_figures_present_one_inserted]`, `failure_category: none`, `no_leak_sweep: clean`.
  - **What unblocked it.** The trace still reads `diagram_or_figure: 9` / `reconstructable_table: 2`, but the two
    reconstructable definition tables Slice 71 *selected* are now **deprioritized** behind the diagram tier
    (`rejection_reason_counts.deprioritized_reconstructable_table: 2`), so diagram-first ranking reaches the genuine
    schematic figures. Both selected candidates are `classified_diagram_or_figure` with `selection_reason:
    selected_by_diagram_first_ranking`; manual ground-truth confirms both are legible, content-bearing,
    non-decorative graphics from distinct source pages that render visibly in PDF/DOCX and ride along in the export
    ZIP.
  - **Decision / next work:** `decision_gate: irreplaceable_diagram_selected_on_real_sample`; `next_recommended_slice:
    visual_placement_or_citation_polish_may_now_be_considered` — because an irreplaceable diagram/figure is finally
    selected on the real sample, future visual work **may** now consider placement/citation polish as a
    separately-designed slice (a *may*, not a mandate; classification precision can be revisited if other samples
    regress). **Do not** expand beyond cap 2; no UI count selector; no Chandra/Mistral/Gemini/model/provider/cloud
    integration; no OCR-routing/renderer/prompt/export change. Chandra remains blocked by its own live-validation gate.
  - **Files:** docs only — `docs/VISUAL_PILOT_OPERATOR_VALIDATION.md`, `docs/CURRENT_TASK.md`, this file,
    `docs/DECISIONS.md`. No frontend/UI; no extraction/OCR-routing/prompt/render/export change; no Chandra/model/
    provider/cloud call. Only sanitized closed-vocab + bounded-numeric fields recorded — no real PDF path/filename,
    document text, OCR text, source caption/table text, image bytes, base64, data URI, full URL, raw argv, token,
    model/mmproj/executable path, or provider payload. The runtime `visual_markdown_selection_trace.json` was
    **inspected but not committed**; nothing binary/image/PDF/DOCX/ZIP/runtime committed. **Slice 73 commit `76e837b`,
    fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

### Prior position (Slice 72 — committed & merged)
- **Slice 72 (dense ruled / wrapped-cell two-column table detection) — COMMITTED + MERGED to `chrome-renderer-v1`
  (fast-forward)** on branch `slice72-visual-pilot-dense-wrapped-table-detection` (branched from fresh trunk after
  Slice 71 was committed/merged). **Production classification slice — precision only; cap/default/two-key gate/UI/
  `/api/options`/render/export/extraction-OCR routing/prompts all unchanged; no model/provider/cloud call.** It acted
  on Slice 71's real-sample finding that Slice 70 split the type buckets (`diagram_or_figure: 9`,
  `reconstructable_table: 2`) yet the two *selected* visuals were still reconstructable **dense ruled / wrapped-cell**
  two-column definition tables that Slice 70's `two_col_split` per-column band guard missed.
  - **What changed:** `pipeline/visual_markdown_insertion.py` gained one bounded, deterministic, pixel-only feature —
    **`dense_wrapped_two_col`** — and a fourth `_looks_like_reconstructable_table` path. It does **not** rely on band
    count (wrapped/antialiased cells legitimately merge bands); instead it requires **exactly two substantial dense
    columns**, a **persistent clean vertical gutter** (`_gutter_consistency` — a diagram's connectors/diagonals break
    it), and **both columns text-rich** (`_column_text_richness` — several ink-runs per row, i.e. text, not a
    continuous shape outline). So dense / wrapped / ruled / lightly-ruled two-column definition tables — including the
    *merged-band* case Slice 70 cannot catch — now type as `reconstructable_table`, while labeled diagrams /
    flowcharts / irregular diagrams stay `diagram_or_figure`. The public classification token and the Slice 68 trace
    schema are unchanged.
  - **Effect (tests):** diagrams/figures still beat reconstructable tables at cap 1 and rank first at cap 2; tables
    remain selected when best/only; default stays **1**, hard cap stays **2**, two-key gate / default-off
    byte-identical / export ride-along all unchanged. New `test_visual_pilot_dense_wrapped_table_detection.py`
    (81 PASS, cap-1 + cap-2) plus the full visual-pilot + insertion/render/export/options/anki suites and the offline
    eval passed on host; production image rebuilt + recreated, `/api/health` `{"ok":true}`, `smoke_release.py` 29/0/0,
    `git diff --check` clean. **Slice 72 commit `5a23852`, fast-forward merged + pushed to trunk
    `chrome-renderer-v1`.** Its real-sample revalidation is the subject of the Slice 73 current-position record above.

### Prior position (Slice 71 — committed & merged)
- **Slice 71 (table-vs-diagram precision operator validation) — COMMITTED + MERGED to `chrome-renderer-v1`
  (fast-forward)** on branch `slice71-visual-pilot-table-diagram-operator-validation`. Validation/docs slice: the
  real-sample rerun showed Slice 70 split the type buckets (`diagram_or_figure: 9`, `reconstructable_table: 2`) but the
  two *selected* visuals were still dense wrapped two-column definition tables
  (`selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`,
  `selection_explanation: tables_still_misclassified_as_diagram_or_figure`) — localizing the residual case that Slice
  72 targets. Only sanitized closed-vocab fields were recorded; no real path/text/image bytes.

### Prior position (Slice 70 — committed & merged)
- **Slice 70 (table-vs-diagram visual-classification precision) — COMMITTED + MERGED to `chrome-renderer-v1`
  (fast-forward)** on branch `slice70-visual-pilot-table-diagram-precision` (branched from fresh trunk after Slice 69
  was committed/merged). **Production classification slice — precision only; cap/default/two-key gate/UI/`/api/options`/
  render/export/extraction-OCR routing all unchanged; no model/provider/cloud call.** It acts on Slice 69's trace
  finding that all safe candidates were classified `diagram_or_figure` while the selected visuals were, by manual
  inspection, reconstructable two-column tables (`selection_explanation: tables_misclassified_as_diagram_or_figure`).
  - **What changed:** `pipeline/visual_markdown_insertion.py` gains one bounded, deterministic, pixel-only feature —
    **`two_col_split`** — and a third `_looks_like_reconstructable_table` path. It fires only when the crop has
    **exactly two substantial text columns separated by a real gutter** (whitespace or a thin drawn divider) **AND
    each column independently contains several separated horizontal text bands**. So **two-column / glossary /
    definition tables now classify as `reconstructable_table`** (regularity of row spacing is *not* required — which
    is what fixes variable-height definition rows), while a **labeled diagram stays `diagram_or_figure`** (its
    columns are continuous shapes, not stacks of text rows; text presence alone never flips it). Diagram-first
    ranking (Slice 64) then prefers diagrams over reconstructable tables, but tables are still selected when best/only.
  - **Trace:** the Slice 68 selection trace reflects the improved classification automatically — `type_counts` no
    longer collapse to one bucket. **No artifact schema change.**
  - **New test:** `test_scripts/test_visual_pilot_table_diagram_precision.py` (24-point coverage). **70/70 pass host
    and at cap 2.** Full visual-pilot suite + operator self-test + insertion/render/export/anki/options +
    `eval --offline --all` (no regression, 0.8306→0.8306) green host-side; container rebuilt+recreated, `/api/health`
    `{"ok":true}`, in-container visual suite green. `git diff --check` clean.
  - **Release smoke:** `release_smoke_status: transient_failure_then_green_on_rerun`,
    `release_smoke_failure_category: outline_ordering_check`, `slice70_visual_tests: green`,
    `slice70_docker_health: green`, `slice70_not_cause: confirmed`. A first `smoke_release.py` run was 28/29 with one
    flaky `outline_ordering_check` miss; an unchanged rerun on the same Slice 70 branch/container passed **29/0/0**
    with that check green. The check is an LLM section-ordering assertion, unrelated to the deterministic pixel-only
    classifier change. No raw generated guide content recorded.
  - **Decision:** classification precision was the real bottleneck; fix it deterministically and locally, do not
    guess ranking/threshold changes. **Do not** expand beyond cap 2; **no** UI count selector; **no**
    Chandra/Mistral/Gemini/model/provider/cloud/`llama-server` integration; **no** OCR-routing/renderer/prompt/export
    change. Chandra remains blocked by its own live-validation gate.
  - **No-leak:** no real PDF path/filename, document/OCR text, image bytes, base64, data URI, full URL, raw argv,
    token, model/mmproj/executable path, or provider payload recorded; nothing binary/image/PDF/DOCX/ZIP/runtime
    committed (every PNG is runtime-built in a temp dir). **Slice 70 is NOT committed.**

### Prior position (Slice 69 — committed & merged)
- **Slice 69 (real operator selection-trace audit) — COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward)** on
  branch `slice69-visual-pilot-selection-trace-operator-audit` (branched from fresh trunk after Slice 68 was
  committed/merged). **Validation/docs slice — no production pipeline/API/frontend code changed; no new visual
  behavior; no ranking/cap/default/gate/render/export/extraction-OCR routing change; no model/provider/cloud call.**
  It uses Slice 68's sanitized selection trace (`visual_markdown_selection_trace.json`) on the real, **non-private**
  operator sample to explain *why* tables still win over diagrams — the one thing Slices 63/65/67 could not answer
  without leaking source material.
  - **Outcome this session: `selection_trace_operator_audit: run` — `status: ok`, `trace_artifact_present: true`,
    `trace_no_leak_sweep: clean`, `effective_max_images: 2`, `inserted_visual_count: 2`, `safe_candidate_count: 11`,
    `unsafe_candidate_count: 0`, `selected_count: 2`.** The non-private sample was available, so the cap-2 harness
    **was** run inside the rebuilt Slice 68 container (`GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1`,
    `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION=1`, `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`); the trace + rendered
    PDF/HTML/DOCX were copied to a host folder and inspected by hand. The trace was checked for leaks **before** any
    field was transcribed (clean).
  - **Root cause finally localized — classification, not extraction or pure ranking.** The trace's `type_counts`
    shows **all 11 safe candidates classified `diagram_or_figure`** (`reconstructable_table: 0`, `unknown: 0`,
    `decorative_or_low_information: 0`). Manual inspection ground-truths the discrepancy: the two **selected** visuals
    are clean two-column definition/glossary **tables** (`selected_visual_type: tables_only`,
    `irreplaceable_visual_selected: false`, `selected_figures_quality: all_useful_or_acceptable`), and at least one
    **genuinely irreplaceable schematic diagram was present among the safe candidates but was NOT selected**. Because
    the pixel classifier over-accepts reconstructable tables as `diagram_or_figure`, every candidate carries the same
    `visual_type_score: 3`, diagram-first ranking has no discriminating signal, and pure quality score picks the
    clean tables (`quality_score: 1.2`) ahead of the real diagram. `selection_explanation:
    tables_misclassified_as_diagram_or_figure`.
  - **Next work (recorded, not started):** `improve_visual_type_classification_table_vs_diagram_precision` — the
    deterministic local pixel classifier must separate reconstructable tables from genuine diagrams so diagram-first
    ranking gets a real signal. **Not** extraction (diagrams present) and **not** a blind ranking/threshold change
    (ranking is signal-starved, not wrong). The trace is **sufficient** to localize this; its per-candidate
    rejection-reason coverage is sparse (only `rejected_secondary_below_quality_floor: 1` for the nine unselected
    safe candidates) — a possible future *trace* refinement, not a reason to guess heuristics.
  - **Decision:** **do not proceed to UI polish or cap expansion** until an irreplaceable diagram/figure is selected
    in real validation, or there is a deliberate product decision to accept tables. **Do not expand beyond cap 2; no
    UI count selector; no Chandra/Mistral/Gemini/model/provider/cloud integration.** Chandra remains blocked by its
    own live-validation gate.
  - **Docs-only:** updated `VISUAL_PILOT_OPERATOR_VALIDATION.md`, `CURRENT_TASK.md`, this file, `DECISIONS.md`. No
    harness correction needed; no frontend/UI; no extraction/OCR-routing/prompt/render/export change; no
    Chandra/model/provider/cloud call. `git diff --check` clean. Only sanitized closed-vocab + bounded-numeric fields
    recorded — no real PDF path/filename, document text, OCR text, source caption/table text, image bytes, base64,
    data URI, full URL, raw argv, token, model/mmproj/executable path, or provider payload. The runtime
    `visual_markdown_selection_trace.json` was **inspected but not committed**; nothing binary/image/PDF/DOCX/ZIP/
    runtime committed. **Slice 69 is NOT committed.**

### Prior position (Slice 68 — committed & merged)
- **Slice 68 (sanitized visual-pilot selection trace / candidate audit) — COMMITTED + MERGED to `chrome-renderer-v1`
  (fast-forward)** on branch `slice68-visual-pilot-sanitized-selection-trace` (branched from fresh trunk after
  Slice 67 was committed/merged). **Production diagnostic slice — visibility only; ranking/cap/default/two-key
  gate/UI/render/export/extraction-OCR routing all unchanged; no model/provider/cloud call.** It acts on Slice 67's
  finding that the real post-Slice-66 cap-2 run STILL selected two useful-but-reconstructable tables only: rather
  than tune another heuristic blind, it adds a bounded, sanitized candidate-audit artifact so future real runs can
  explain *why* diagrams were not selected.
  - **What changed (one production file):** `pipeline/visual_markdown_insertion.py` — added
    `build_visual_markdown_selection_trace(...)` + `_emit_selection_trace(...)` (and small pure helpers), wired into
    `apply_visual_markdown_pilot` at the three both-gates-pass exits. The selection/ranking core, cap reader, and
    two-key gate are byte-for-byte unchanged; the trace is an independent read-only pass.
  - **Exact artifact:** `visual_markdown_selection_trace.json`, written to the job dir **only** when the master env
    switch is ON **and** the job opted in **and** selection was attempted (including the no-candidate/low-quality
    skip). Never written when the master switch is off, the job did not opt in, or the pilot is not reached.
    Build/write is degrade-never-fail (a trace problem never fails generation, leaves no partial file).
  - **Sanitized + bounded:** whitelisted top level (`schema_version`, `status`, `reason`, `effective_max_images`,
    `inserted_visual_count`, `selected_candidates`, `candidate_summary`, `warnings`); per-candidate safe fields +
    closed-vocabulary reason tokens only; `candidate_summary` is counts only. No path/filename/document/OCR/caption/
    table text, image bytes, base64, data URI, provider payload, raw exception, URL, token, raw argv, or model path.
    Chandra/Mistral/page_visual_signal candidates are counted/rejected, never written raw.
  - **New test:** `test_scripts/test_visual_pilot_selection_trace_sanitized.py` (20-point coverage). **56/56 pass
    host and in-container.** Full visual-pilot suite + operator self-test + insertion/render/export/anki/options +
    `eval --offline --all` green host-side; container rebuilt+recreated, `/api/health` `{"ok":true}`,
    `smoke_release.py` **29/29**, in-container suite green. `git diff --check` clean. **Slice 68 commit `9a8f10d`,
    fast-forward merged + pushed to trunk `chrome-renderer-v1`.** Its real-sample selection-trace audit is the
    subject of the Slice 69 current-position record above.

### Prior position (Slice 67 — committed & merged)
- **Slice 67 (improved-light-table real operator validation) — COMMITTED + MERGED to `chrome-renderer-v1`
  (fast-forward)** on branch `slice67-visual-pilot-light-table-operator-validation` (branched from fresh trunk after
  Slice 66 was committed/merged). **Validation/docs slice — no production pipeline/API/frontend code changed; no new
  visual behavior.** It closed the one gap Slice 66 left open: rerun the cap-2 operator harness on the **real**
  non-private sample to see whether the strengthened lightly-ruled-table detector finally lets diagram-first
  ranking pick a hard-to-reconstruct diagram/figure instead of tables only.
  - **Outcome this session: `light_table_operator_visual_quality_review: run` — `status: ok`,
    `inserted_visual_count: 2`, `selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`,
    `selected_figures_quality: all_useful_or_acceptable`,** all render/export checks `true`,
    `warnings: [multiple_figures_present_one_inserted]`, `failure_category: none`, `no_leak_sweep: clean`. The
    non-private operator sample was available again, so the cap-2 operator harness **was** run inside the rebuilt
    Slice 66 container (`GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1`, `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION=1`,
    `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`); rendered PDF/HTML/DOCX copied to a host folder and inspected by hand.
  - **Honest outcome — improved light-table detection did *not* change the real selection.** Slice 66 improved the
    synthetic / light-table detection tests, but the real cap-2 run still selected **two useful tables only** —
    readable and useful, yet **reconstructable from extracted text**. **No irreplaceable diagram/figure was
    selected, so visual-type selection is still not solved for the real sample.** `decision_gate:
    light_table_detection_did_not_change_real_outcome` · `next_recommended_slice:
    add_sanitized_selection_trace_before_more_heuristics`.
  - **Decision:** **do not proceed to UI polish or cap expansion.** Before further heuristic tuning, add a
    **sanitized selection trace / candidate audit** (closed-vocab / bounded-numeric only) so future runs can explain
    *why* diagrams were not selected. **Do not expand beyond cap 2; no UI count selector; no
    Chandra/Mistral/Gemini/model/provider/cloud integration.** Chandra remains blocked by its own live-validation
    gate.
  - **Docs-only:** updated `VISUAL_PILOT_OPERATOR_VALIDATION.md`, `CURRENT_TASK.md`, this file, `DECISIONS.md`. No
    harness correction needed; no frontend/UI; no extraction/OCR-routing/prompt/render/export change; no
    Chandra/model/provider/cloud call. `git diff --check` clean. Only the sanitized closed-vocabulary fields
    recorded — no real PDF path/filename, document/OCR text, image bytes, base64, data URI, full URL, raw argv,
    token, model/mmproj/executable path, or provider payload; nothing binary/image/PDF/DOCX/ZIP/runtime committed.
    **Slice 67 is NOT committed.** Chandra remains blocked by its own live-validation gate.

### Prior position (Slice 66 — committed & merged)
- **Slice 66 (lightly-ruled / text-heavy table detection) — COMMITTED + MERGED to `chrome-renderer-v1`
  (fast-forward)** on branch `slice66-visual-pilot-light-table-detection` (branched from fresh trunk after Slice 65
  was committed/merged). **Production-behavior slice — visual-type *detection* only; ranking/cap/gates unchanged.**
  It acted on Slice 65's recorded `next_recommended_slice: improve_visual_type_detection_before_ui_polish`:
  strengthen table-vs-diagram detection so diagram-first ranking actually has a signal on real, lightly-ruled
  tables.
  - **What changed (one file):** `pipeline/visual_markdown_insertion.py`. Extended the bounded grayscale feature
    summary (`_summarize_gray_pixels`) with a **softer-ink** (`_LT_INK`) horizontal **text-band rhythm** and a
    vertical **column-gutter** structure, and added `_looks_like_reconstructable_table(...)` (+ pure helpers
    `_profile_runs`, `_runs_regular`, `_count_col_blocks`) wired into `_classify_visual_type_from_features`
    **after** the strong-grid table rule and **before** the diagram rule. Two **dual-signal** table paths:
    (a) **text-grid** — regular repeated text-band rhythm *and* a multi-column gutter structure; (b)
    **lightly-ruled** — multiple full horizontal rules *without* a strong vertical-rule grid, backed by row rhythm
    or column structure. A genuine diagram (irregular rows, no clean full-height gutters, no repeated h-rules)
    satisfies neither and stays `diagram_or_figure`.
  - **Behavior:** lightly-ruled and text-band (weak/no vertical rule) tables now classify as
    `reconstructable_table` (were `unknown`); the diagram stays `diagram_or_figure`; **diagram beats a lightly-ruled
    table at cap 1**, and at cap 2 the diagram is selected **before** a table. **Tables remain allowed when they are
    the best/only useful visual.** Pixel-only over the already-safe job-dir-contained crop; **no OCR / model /
    provider / network / cloud / `llama-server` / image-gen**, no bytes/base64/data-URI/path/text retained, **no new
    artifact**; Pillow-absent / unreadable / too-small ⇒ `unknown` ⇒ **byte-identical fallback** to prior selection.
  - **Invariants unchanged:** two-key gate, **default cap 1**, **hard cap 2** (server-side only), `fitz_local` /
    `extracted_figure`-only, unsafe-ref / Chandra / Mistral / `page_visual_signal` rejection, decorative rejection
    still dominates, default-off **byte-identical**, export ride-along unchanged. **No frontend/UI, no
    `/api/options`/route change, no cap change, no extraction/OCR-routing/prompt/render/export change.** Chandra
    still blocked by its own live-validation gate.
  - **Tests:** new `test_scripts/test_visual_pilot_light_table_detection.py` (runtime-built tiny PNG fixtures, never
    committed) — strong/lightly-ruled/text-band → table, diagram → diagram, cap-1 diagram-beats-table, cap-2
    diagram-first / two-diagrams / only-tables, decorative rejection, unknown-preserves-prior, analysis-failure
    degrade, unsafe-ref / blocked-provider exclusion, determinism, two-key gate, default-off byte-identical,
    default-1 / hard-cap-2, export ride-along, full no-leak sweep. Host + **in-container** (Pillow 12, no skips)
    green: light-table 66/0, ranking 64/0, multifigure 78/0, quality-gate 54/0, operator `--self-test` PASS;
    `compileall` clean; Docker `build`+`up`+`/api/health`+`smoke_release.py` 29/0; `git diff --check` clean.
  - **Optional real operator revalidation: NOT run** — the non-private sample is not available this session. The
    desired flip (`selected_visual_type: diagrams_or_figures_present` / `irreplaceable_visual_selected: true`) is
    **not assumed**; re-run the cap-2 operator harness when the sample is available and record only if true.
  - **No-leak:** closed-vocab tokens + bounded numeric features only; no real PDF path/filename, document/OCR text,
    image bytes, base64, data URI, full URL, raw argv, token, or model/mmproj/executable path; nothing
    binary/image/PDF/DOCX/ZIP/runtime committed. **Slice 66 is COMMITTED + MERGED to `chrome-renderer-v1`
    (fast-forward).** Its optional real operator revalidation is the subject of the Slice 67 record above.

### Prior position (Slice 65 — committed & merged)
- **Slice 65 (diagram-first real operator validation record) — COMMITTED + MERGED to `chrome-renderer-v1`
  (fast-forward)** on branch `slice65-visual-pilot-diagram-first-operator-validation`. **Validation/docs slice — no
  production code changed.** Recorded the real cap-2 operator revalidation of the Slice 64 diagram-first ranking:
  outcome **did not change** — `selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`,
  `selected_figures_quality: all_useful_or_acceptable`, `inserted_visual_count: 2`, all render/export OK,
  `no_leak_sweep: clean`. Root cause (`decision_gate: diagram_first_ranking_did_not_change_real_outcome`): the
  strong-grid classifier did not recognize lightly-ruled tables, so ranking had no signal — directly motivating
  Slice 66 (`next_recommended_slice: improve_visual_type_detection_before_ui_polish`).

### Prior position (Slice 64 — committed & merged)
- **Slice 64 (prefer diagrams over reconstructable tables — visual-type ranking) — COMMITTED + MERGED to
  `chrome-renderer-v1` (fast-forward)** on branch `slice64-visual-pilot-diagram-first-ranking`.
  **Production-behavior slice, ranking only — no expansion.** Added a pixel-only visual-type classifier
  (`classify_visual_markdown_candidate_type_for_pilot`) + priority scorer
  (`score_visual_type_priority_for_pilot`) wired as a **type-first / quality-second** tier into the existing
  pickers (`_pick_candidate`, `_pick_candidates`/`_select_multi`, new `_best_typed`); closed vocab
  `diagram_or_figure > reconstructable_table > unknown > decorative_or_low_information`. Pillow-absent /
  unreadable / too-small ⇒ `unknown` ⇒ **byte-identical fallback** to prior Slice 60/62 quality-only selection;
  default-off byte-identical, two-key gate unchanged, **default cap 1**, **hard cap 2**, `fitz_local`/
  `extracted_figure`-only, unsafe-ref / Chandra / Mistral / `page_visual_signal` still rejected. Tests: new
  `test_scripts/test_visual_pilot_visual_type_ranking.py`; Docker build/up ok, `/api/health` `{"ok":true}`,
  `smoke_release.py` **29/0/0**. **Its optional real operator revalidation is now recorded in Slice 65 above.**

### Prior position (Slice 63 — committed & merged)
- **Slice 63 (cap-2 real operator validation record) — COMMITTED + MERGED to `chrome-renderer-v1`** on
  branch `slice63-visual-pilot-cap2-operator-validation` (branched from fresh trunk after Slice 62 was
  committed/merged). **Validation/docs slice — no production pipeline/API/frontend code changed and no new
  visual behavior added.** It records a real, sanitized operator validation of the Slice 62 **cap-2** path
  (Slice 62 had validated cap-2 only synthetically + in Docker; this closes the optional **real** revalidation).
  - **What was done:** ran the existing operator harness inside the Slice 62 container with
    `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2` (plus the two enable gates) against the already-supplied
    non-private sample, copied the rendered PDF/HTML/DOCX to a host folder, and inspected the inserted figures.
  - **One tiny safe harness correction (only code touched):** the export check previously hard-coded exactly one
    bundled PNG (`len(png_entries) == 1`), which falsely reported `export_png_included: false` when cap-2
    legitimately bundled two referenced PNGs. It now requires the bundled-PNG count to equal the sanitized
    `inserted_visual_count` (within `1..2`), each still a safe `assets/<slug>.png` ref. `--self-test` stays green.
  - **Recorded (sanitized):** `cap2_operator_visual_quality_review: run` · `status: ok` · `pilot_inserted: true` ·
    **`inserted_visual_count: 2`** · **`selected_figures_quality: all_useful_or_acceptable`** ·
    `pdf_render_ok/pdf_image_visible/docx_render_ok/export_zip_ok/export_png_included: true` ·
    `warnings: [multiple_figures_present_one_inserted]` · `failure_category: none` · `no_leak_sweep: clean`.
  - **Operator-review nuance (sanitized, closed vocab):** `selected_visual_type: tables_only` ·
    `irreplaceable_visual_selected: false` · `decision_gate:
    cap2_plumbing_passed_but_visual_type_priority_incomplete` · `next_recommended_slice:
    prefer_diagrams_over_reconstructable_tables`. Both selected visuals were useful/acceptable **tables**, not
    diagrams/figures that are hard to reconstruct.
  - **Decision gate:** Slice 63 **proves the cap-2 pipeline works on a real, non-private sample**, and the output
    is useful (`all_useful_or_acceptable`). **But** both visuals were **tables**, which are often reconstructable
    from extracted text into clean generated tables; the visual feature exists especially to preserve visuals an
    LLM **cannot** recreate from text (diagrams, flowcharts, screenshots, labeled figures, network maps).
    **Therefore the next visual slice is NOT placement/UI polish yet** — it should **improve visual-type ranking**
    (prefer diagrams/figures over reconstructable tables when both are available, still allowing tables when they
    are the best/only useful visual). **Do not expand beyond cap 2; no Chandra/Mistral/Gemini/model/provider/cloud
    integration.** Default stays exactly 1. Chandra remains blocked by its own gate.
  - **Files:** `docs/VISUAL_PILOT_OPERATOR_VALIDATION.md`, `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`,
    `docs/DECISIONS.md`; tiny correction in `test_scripts/validate_visual_pilot_operator_sample.py`. **Slice 63
    is NOT committed.**
  - **No-leak:** only sanitized closed-vocab fields + safe relative refs; no real PDF path/filename, document/OCR
    text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable path, or raw
    exception; no committed binary/image/PDF/DOCX/ZIP/runtime output.

### Prior position (Slice 62 — committed & merged)
- **Working tree:** **Slice 62 (capped multi-figure visual pilot) — COMMITTED + MERGED to `chrome-renderer-v1`
  (fast-forward)** on branch `slice62-visual-pilot-capped-multifigure` (branched from fresh trunk after Slice 61
  was committed/merged).
  **Cautiously extends the off-by-default visual pilot from one figure to up to a small server-configured cap
  (hard upper bound 2); default behavior stays exactly one figure.** Slices 59/60/61 cleared the single-figure
  plumbing + Slice 60 quality gate on a real non-private sample; Slice 62 is the first step beyond one figure.
  - **Gate (unchanged) + cap:** the existing two-key gate (global master env + per-job opt-in) is untouched. New
    server-side env integer `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES`: default `1`, min `1`, **hard max `2`**;
    absent/empty/non-integer/`0`/negative/`>2`/huge all degrade to `1` (never clamp upward). Relevant only when
    both gates are on AND local figure extraction produced safe candidates.
  - **Selection reuses the Slice 60 quality gate:** `fitz_local` + `extracted_figure` + safe contained
    `assets/<slug>.png` only (never Chandra/Mistral/page-signal/unsafe). First/strongest pick is byte-for-byte
    the existing single-best decision; each extra figure must clear a secondary quality floor (`score ≥ 1.15`),
    not duplicate an `asset_id`/`asset_ref`, and prefer a distinct source page. Only-decorative ⇒ none; weak
    second ⇒ one. The cap is never filled with junk.
  - **Insertion:** one figure ⇒ byte-identical to the legacy pilot (singular `## Visual Reference`). More than
    one ⇒ anchored placements where markers exist, else one trailing plural `## Visual References` section.
    Captions stay generic page-only (`Extracted figure from source page N`).
  - **Export:** rides along all and only referenced pilot PNGs, capped at 2, contained; never the whole
    `assets/` dir / unreferenced crops. PNG ride-alongs still don't count toward `files_included`, so a
    pilot-PNG-only job with no requested artifact still 404s. Index keeps `visual_pilot_asset` (first/`null`) and
    adds `visual_pilot_assets` (capped list).
  - **Out of scope (unchanged):** no Chandra/Mistral/Gemini/model/provider/cloud call, no OCR-routing/extraction/
    prompt/renderer change, no new route, no arbitrary N-figure support, no UI count selector. `/api/options` and
    frontend untouched. Chandra remains blocked by its own live-validation gate.
  - **Files:** `pipeline/visual_markdown_insertion.py`, `api/server.py`; new
    `test_scripts/test_visual_pilot_multifigure.py` (63/0/3); operator harness gained a safe
    `inserted_visual_count` field + accepts 1..2 safe refs. **Slice 62 is NOT committed.**
  - **No-leak:** only sanitized closed-vocab fields + safe relative refs; no real PDF path/filename, document/OCR
    text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable path, or raw
    exception; no committed binary/image/PDF/DOCX/ZIP/runtime fixture.

### Prior position (Slice 61 — committed & merged)
- **Working tree:** **Slice 61 (post-fix visual-quality operator review record)** on branch
  `slice61-visual-pilot-postfix-quality-review` (branched from fresh trunk). **Docs / validation-record
  only — adds NO production code and changes NO behavior** (no frontend/UI, export, extraction/OCR-routing,
  prompt, render, route, multi-figure, or Chandra/model/provider/cloud change; no committed binary/image/PDF/
  DOCX/ZIP/runtime output).
  - **Slice 60 is now committed and merged to trunk** (`chrome-renderer-v1`, fast-forward) — it fixed the quality
    gate and the PDF image-visibility check and reran the real, non-private operator validation green. Slice 61
    records the one thing Slice 60 left open: the **human** quality verdict on the now-selected figure, as the
    decision gate for the next visual step.
  - **What was done:** reran the existing operator harness inside the freshly rebuilt Slice 60 container against
    the already-supplied non-private sample, copied the rendered PDF/HTML/DOCX to a host folder, and had the
    operator classify the selected figure with the closed vocabulary `useful_diagram_or_table` ·
    `acceptable_but_not_best` · `decorative_or_low_information` · `wrong_or_bad_crop` · `unclear`.
  - **Recorded post-fix review (sanitized):** `postfix_operator_visual_quality_review: run` · `status: ok` ·
    `pilot_inserted: true` · **`selected_figure_quality: useful_diagram_or_table`** · `pdf_render_ok: true` ·
    `pdf_image_visible: true` · `docx_render_ok: true` · `export_zip_ok: true` · `export_png_included: true` ·
    `warnings: [multiple_figures_present_one_inserted]` · `failure_category: none` · `no_leak_sweep: clean`. The
    pre-fix Slice 60 review (`decorative_or_low_information`, `pdf_image_visible: false`, …) is preserved for
    comparison in `docs/VISUAL_PILOT_OPERATOR_VALIDATION.md`.
  - **Decision-gate outcome:** the verdict is in the `useful_diagram_or_table` / `acceptable_but_not_best` band →
    **cautious multi-figure or improved placement may be considered next**, as a separately-designed slice and
    still one figure at a time until scoped. Chandra remains blocked by its own live-validation gate.
  - **Files:** `docs/VISUAL_PILOT_OPERATOR_VALIDATION.md`, `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`,
    `docs/DECISIONS.md` — docs only. **Slice 61 is NOT committed.**
  - **No-leak:** only sanitized closed-vocab fields recorded; no real PDF path/filename, document/OCR text,
    image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable path, or raw exception.

### Prior position (Slice 60 — committed & merged)
- **Working tree:** **Slice 60 (visual-pilot quality gate + PDF image-visibility validation)** on branch
  `slice60-visual-pilot-quality-gate` (branched from fresh trunk; trunk HEAD
  Slice 59 `a79e99d`). **Replaces an earlier, abandoned Slice 60 trace-artifact direction** — that work is
  **parked in a `git stash` (not committed)** after manual review showed the real issues were selection quality
  and PDF image visibility, not missing trace metadata.
  - **What changed:** `pipeline/visual_markdown_insertion.py` gains a conservative, deterministic **quality
    gate** that **ranks** the already-safe `extracted_figure` candidates using **only** existing manifest
    metadata (`source_page`, `bbox`, `signals` page/crop dims) — preferring content figures and dropping
    decorative title-page/header/footer/banner/logo crops. New helpers
    `score_visual_markdown_candidate_for_pilot` / `rank_visual_markdown_candidates` /
    `is_decorative_visual_candidate`; new closed skip reason `visual_candidate_low_quality` when every safe
    candidate is decorative (omit, byte-identical guide). **All hard safety gates and the one-figure rule are
    unchanged; sparse metadata degrades to neutral so good figures are never over-rejected.** The operator
    harness adds an **eleventh** summary field `pdf_image_visible` (embedded image object via PyMuPDF
    `get_images(full=True)`), distinct from `pdf_render_ok`. **No production wiring change** (`apply_visual_
    markdown_pilot` is still the only call site, from Slice 54); **no frontend/UI, export, extraction/OCR-
    routing, prompt, route, multi-figure, or Chandra/model/cloud change; no committed binary/image/PDF/DOCX/ZIP
    fixture.**
  - **Files:** `pipeline/visual_markdown_insertion.py`; `test_scripts/validate_visual_pilot_operator_sample.py`
    (+`pdf_image_visible`); new `test_scripts/test_visual_pilot_quality_gate.py`; `docs/CURRENT_TASK.md` /
    `docs/NEXT_CHAT_HANDOFF.md` / `docs/DECISIONS.md`. (e2e test gained a fitz-guarded image-embed check.)
  - **Safety/no-leak:** the gate reads no private text/OCR/caption/image bytes and makes no model/provider call;
    all diagnostics are closed-vocab tokens + numeric scores. The real sample PDF path/filename/contents are
    **not** recorded anywhere.
  - **Root cause of the "broken PDF marker" — a harness layout artifact, NOT a production bug.** `render_pdf`
    writes its intermediate HTML next to the **output PDF**, so Chromium resolves the relative `assets/<slug>.png`
    ref against the output PDF's directory. **Production renders to `job.final_pdf` (a sibling of `clean.md` +
    `assets/`)**, so the figure embeds correctly. The Slice 59 harness wrote the PDF to the temp base dir
    (outside the job dir) → `assets/` didn't resolve → Chromium embedded only a tiny ~14×16 broken-image
    placeholder icon (what review saw). **Fixed** by rendering the harness PDF inside the job dir; **the
    renderer was not changed** (it was already correct for the production layout).
  - **Pre-fix human review (sanitized, closed vocab):** `operator_visual_quality_review: run` ·
    `selected_figure_quality: decorative_or_low_information` · `extraction_candidate_quality: mostly_usable` ·
    `crop_quality: mostly_good_some_label_loss` · `pdf_image_visible: false` · `docx_image_visible: true` ·
    `failure_category: selection_quality_insufficient` · `no_leak_sweep: clean`.
  - **Post-fix sanitized result (in-container `--self-test`):** `status: ok` · `pilot_inserted: true` ·
    `pdf_render_ok: true` · **`pdf_image_visible: true`** · `docx_render_ok: true` · `export_zip_ok: true` ·
    `export_png_included: true` · `warnings: []` · `failure_category: none` · `no_leak_sweep: clean`.
  - **Results:** host — `compileall` clean; new gate test **50/0/1** (PDF-vis skips w/o PyMuPDF+Chromium);
    operator `--self-test` PASS; `test_visual_pilot_e2e_validation.py` 16/0/3; insertion 53/0 (off) & 77/0 (on);
    render 6/0/1; export-asset 9/0; options 16/0; anki 46/0; eval `--offline --all` no regression; `git diff
    --check` clean. **Docker:** `compose build` + `up -d --force-recreate` OK; `/api/health` → `{"ok":true}`;
    `smoke_release.py` **29/0/0**; in-container gate test **54/0/0** (PDF-vis positive+negative pass), e2e
    **30/0/0**, operator `--self-test` PASS with `pdf_image_visible: true`. Test scripts were copied into the
    container `/tmp`, run, then removed; nothing committed.
  - **Slice 60 is now committed and fast-forward merged to trunk `chrome-renderer-v1` (see Slice 61 above).**

### Prior position (superseded)
- **Working tree:** **Slice 59 (visual-pilot manual operator validation harness + runbook) — UNCOMMITTED
  (per instruction)** on branch `slice59-visual-pilot-operator-validation-harness` (branched from trunk after
  **Slice 58** committed `39dc162` + fast-forward merged + pushed). **Validation/harness slice only — adds NO
  production code and changes NO behavior.** Adds an **opt-in manual** harness so an operator can validate the
  **current single-figure pilot** against a real, **non-private** sample PDF by driving the genuine pipeline
  (`extract_local_figures` `fitz_local` → manifest/scoring/plan writers → `apply_visual_markdown_pilot` via
  `save_clean_md` → HTML/PDF/DOCX render → `export_bundle`).
  - **Files:** new `test_scripts/validate_visual_pilot_operator_sample.py` (manual CLI; `--pdf` real run that
    **refuses without `--pdf`**, plus a synthetic `--self-test` dry run verifying summary schema + no-leak
    without an operator PDF); new `docs/VISUAL_PILOT_OPERATOR_VALIDATION.md`; doc updates. **No production/
    frontend/renderer/export/extraction/OCR-routing/prompt change, no new route, no multi-figure/Chandra/model/
    cloud call, no committed PDF/image/DOCX/ZIP fixture.**
  - **Safety/no-leak:** never prints the PDF path/basename/text, OCR text, image bytes, base64, data URIs,
    tokens, headers, model paths, raw argv, or full URLs; emits only a fixed **closed-vocab** 10-field summary
    (`status` · `pilot_inserted` · `safe_asset_ref_present` · `html_render_ok` · `pdf_render_ok` ·
    `docx_render_ok` · `export_zip_ok` · `export_png_included` · `warnings` · `failure_category`) + closed-vocab
    step markers; exceptions sanitized to closed `failure_category` tokens; final sweep over every
    pipeline-derived string; all working files under a temp/output dir, nothing committed.
  - **Results:** host `--self-test` PASS (DOCX/export skip calmly w/o deps); **in-container `--self-test` PASS**
    (all stage booleans `true`, 0 warnings, no leak). Refusal + sanitized missing-file paths verified.
    `compileall` + `git diff --check` clean; `/api/health` ok.
  - **Real operator validation — RUN, successful (sanitized):** ran on **one real, non-private,
    operator-supplied PDF**. Recorded `manual_operator_pdf_validation: run`, `status: ok`,
    `pilot_inserted: true`, `safe_asset_ref_present: true`, `html/pdf/docx_render_ok: true`,
    `export_zip_ok: true`, `export_png_included: true`, `warnings: [multiple_figures_present_one_inserted]`,
    `failure_category: none`, `no_leak_sweep: clean`. Multiple candidates present, **exactly one** inserted
    (one-figure rule obeyed; warning expected). **Clears the single-figure visual-pilot operator-validation
    gate.** Only sanitized closed-vocab fields recorded — no real path/filename/document/OCR text/image bytes/
    base64/data URI/full URL/raw argv/token/raw exception. **Chandra still blocked by Slice 45 `not_run`;
    multi-figure insertion NOT yet approved — stays deferred until separately designed.**

### (previous) Slice 58 — visual-pilot stitched E2E validation harness + record — committed `39dc162`, merged to trunk
- **Validation/harness slice only — adds NO production code and changes NO behavior.** Proves the
  already-shipped **single-figure** pilot (Slices 52–57) works as **one connected chain** before any visual
  expansion: safe job-local `assets/<slug>.png` → manifest / replacement-plan shape → master flag ON → per-job
  opt-in ON → exactly one markdown image → HTML/PDF/DOCX render → export ZIP carrying the single referenced PNG.
  - **Files:** new `test_scripts/test_visual_pilot_e2e_validation.py` (stitches a real `JobManager.Job` +
    `apply_visual_markdown_pilot` + `save_clean_md` + render + `export_bundle`; reuses existing insertion /
    render / export / options test helpers); new `docs/VISUAL_PILOT_E2E_VALIDATION.md`; doc updates
    (`CURRENT_TASK.md`, `NEXT_CHAT_HANDOFF.md`, `DECISIONS.md`). **No production/frontend/renderer/export/
    extraction/OCR-routing/prompt change, no new route, no multi-figure/Chandra/model/cloud call, no committed
    binary/image fixture.** Test PNG generated at runtime via stdlib `zlib`+`struct`; all temp artifacts removed.
  - **Verifies (13):** one image · safe `assets/<slug>.png` ref · generic page caption (real `None`-caption
    path, not raw OCR) · unsafe refs rejected · manifest/plan/source-PNG unmutated · HTML safe relative `<img>`
    + no abs path · non-empty PDF (SKIP w/o Chromium) · non-empty DOCX (SKIP w/o python-docx) · export carries
    exactly one referenced PNG under `assets/` · extra crop / blanket assets dir excluded · `files_included`
    counts requested artifacts only and PNG-alone still `404`s the gate · bundle index records only safe
    relative `visual_pilot_asset` · final no-leak sweep over every serialized output.
  - **Results:** host **16/0/2** (DOCX + export skip w/o python-docx/FastAPI); **in container 29/0/0** (full
    chain). Existing visual/insertion/render/export/options + Anki + offline eval green; `compileall` +
    `git diff --check` clean; `/api/health` ok. **Manual operator PDF review:
    `manual_operator_pdf_validation: not_run` (reason `non_private_operator_sample_not_supplied`).** **Chandra
    extraction still blocked by Slice 45 `not_run`.**

### (previous) Slice 57 — visual-pilot readiness capability + Builder guard — committed `9c4ccc0`, merged to trunk
- Makes the Builder's per-job visual opt-in **accurately
  reflect whether the pilot can work for a new job**. The toggle stays **default-off** but is **enabled only
  when the backend reports readiness** = global pilot master flag **AND** local figure extraction (which
  produces the `fitz_local` figure the pilot inserts). **Readiness/UX guard only** — it does **not** enable
  insertion, change the backend dual gate, or auto-enable extraction.
  - **Scope:** `/api/options.capabilities` refinement (`api/server.py`) + Builder guard
    (`frontend/src/visualPilotOptIn.js` + `BuilderWorkspace.jsx`) + tests/docs. **No** new page/route, broad
    visual settings, export-bundle change, generic artifact-row change, advisory schema change,
    renderer/prompt/extraction/OCR-routing change, Chandra, model/network call, image processing, image
    fixtures, or `clean.md` write. **≤1 figure / `fitz_local` only / safe `assets/<slug>.png` only — all
    unchanged.**
  - **Capabilities (non-secret booleans):** `visual_markdown_image_pilot` (master flag — **preserved**,
    backward-compatible) · `local_figure_extraction` · `visual_references_ready` (= **both** true). No env
    names/paths/tokens/raw config in the response.
  - **Builder guard:** new pure helpers `isVisualReferencesReady(caps)` (trusts derived flag; falls back to
    AND of components) + `visualPilotReadinessNote(caps)` (fixed safe copy). Toggle enabled only when ready;
    calm note when not — master-off ⇒ *"Visual references are not enabled on this server."*, extraction-off ⇒
    *"Visual references need local figure extraction to be enabled on this server."* Request still adds
    `enable_visual_references` **only** when opted in (Slice 55 behaviour; default/not-ready ⇒ byte-identical).
  - **Backend gates unchanged:** master flag **cannot be bypassed**; per-job opt-in still default false;
    `/api/options` readiness is a **UI affordance only**, **not** a new insertion gate —
    `apply_visual_markdown_pilot` independently re-checks both switches and stays degrade-never-fail.
    Extraction is **never** auto-enabled / run by the toggle.
  - **Tests:** new `test_scripts/test_visual_pilot_options.py` (Part A pure truth table **16/0** host; Part B
    `server.options()` capability shape under FastAPI/Docker — keys/booleans/backward-compat/no-leak/default-
    not-ready) + updated `frontend/scripts/verify-visual-pilot-opt-in.mjs` (readiness table, calm notes,
    ready⇒enabled, payload-only-when-checked, no leak). Existing visual/OCR/Chandra batteries + eval +
    frontend build/all-verifies green. **Docker rebuild + `/api/health` + `smoke_release.py` + `/api/options`
    readiness spot-check run before commit.** **Chandra extraction still blocked by Slice 45 `not_run`.**

### (previous) Slice 56 — export the referenced visual-pilot PNG with bundles — committed `2a09261`, merged to trunk
- Makes exported Markdown/HTML **portable**: when a
  guide's `clean.md` contains the Slice 54 pilot's safe image ref `![caption](assets/<slug>.png)`, the
  export bundle now includes **that single referenced job-local PNG**. Nothing else about export changes.
  - **Scope:** backend `export_bundle` (`api/server.py`) + two read-only detection helpers in
    `pipeline/visual_markdown_insertion.py` + a focused test. **No frontend/UI, no new route, no generic
    artifact row, no schema/renderer/prompt/extraction/OCR-routing change, no Chandra, no model/network,
    no image processing, no `clean.md` write.**
  - **Detection:** `extract_visual_pilot_asset_refs(text)` (pure; keeps only refs passing the Slice 54
    `validate_visual_asset_ref`) + `find_exportable_visual_pilot_asset(job)` (reads `clean.md` read-only,
    returns the **first** referenced ref **only if** the file exists **inside** the job dir via the existing
    `_asset_file_ok` realpath containment ⇒ symlink escapes rejected; **≤1** ref; `None` on
    missing/unsafe/none). Never raises; never opens image bytes.
  - **Wiring:** ZIP entry `<base_dir>/assets/<slug>.png` after the Slice 51 advisory ride-alongs; defence-in-
    depth `is_relative_to`+`is_file` re-check; any problem skipped calmly (export still succeeds). **Not**
    counted toward `files_included` (a pilot-PNG-only job with no requested artifact still **404s**). Only
    the *referenced* PNG — never the whole `assets/` dir, never unreferenced/extra crops. Bundle index records
    only the safe relative ref (`visual_pilot_asset`) — no absolute path, no image bytes.
  - **Unchanged:** guide output / prompts / PDF·HTML·DOCX render / extraction / OCR routing; Slice 51
    advisory JSON ride-alongs; Slice 53 Anki `.apkg`; CSV/TSV quiz exports; the default-off Slice 54/55 gate.
  - **Tests:** `test_scripts/test_visual_pilot_export_asset.py` — **Part A (pure, host) 9/0** (extraction
    order/de-dup, unsafe-ref rejection, present/missing/none/unreferenced/**symlink-escape**); **Part B
    (bundle, Docker/FastAPI)** referenced-PNG rides along once, unreferenced not bundled, relative+safe entry,
    real bytes but no manifest leak, `files_included` requested-only, missing skipped calmly, unsafe rejected,
    pilot-PNG-only 404s, source PNG + `clean.md` byte-identical. Host battery + offline eval + frontend
    build/test/verify green; **Docker rebuild + `/api/health` + `smoke_release.py` + Part B run before
    commit.** **Chandra extraction still blocked by Slice 45 `not_run`.**

### (previous) Slice 55 — per-job opt-in for the visual markdown image pilot — committed `c2c4dd1`, merged to trunk
- Makes the proven Slice 54 pilot **user-controllable per job** behind a
  **two-key AND gate**: the global env master switch `GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT`
  (unchanged, default off) **and** an explicit per-job opt-in. **A job opt-in can never bypass the env
  master switch.** Default stays **off ⇒ byte-identical output**; all Slice 54 visual behaviour (≤1
  `fitz_local` `extracted_figure`, safe `assets/<slug>.png`, existing render path, degrade-never-fail,
  no Chandra, no renderer rewrite) is unchanged — the opt-in only adds a second gate in front of it.
  - **Truth table:** (off,off)/(off,on) ⇒ `visual_pilot_disabled`; (on,off) ⇒ `visual_pilot_job_opt_out`;
    (on,on) ⇒ may insert (still subject to all candidate/path gates).
  - **Per-job option:** manifest key **`visual_markdown_image_pilot`** (bool, default false; absent on
    pre-Slice-55 jobs ⇒ false; non-bool coerces to false). **Request field:** **`enable_visual_references`**
    (bool, default false) on `LLMJobRequest`, wired into **both** JSON and multipart `_parse_llm_request`;
    `create_llm_job` → `run_llm_job(enable_visual_references=…)` stores it as the manifest option. LLM path
    only (only LLM+PDF jobs produce a `fitz_local` figure).
  - **Pilot gate:** `pipeline/visual_markdown_insertion.py` gained `is_job_visual_pilot_opt_in(job)`;
    `apply_visual_markdown_pilot` checks env **first**, then opt-in, before any candidate read (new
    closed-vocab reason `visual_pilot_job_opt_out`). Single `save_clean_md` chokepoint unchanged.
  - **Capability + Builder:** `/api/options` now returns non-secret `capabilities.visual_markdown_image_pilot`
    (= master-switch state). Builder LLM block has one experimental toggle **"Add one visual reference
    (experimental)"**, default unchecked, **disabled-with-note** when the capability is off; pure helper
    `frontend/src/visualPilotOptIn.js` keeps payload/toggle logic node-testable. No new page / broad visual
    settings / export-artifact rows / Job Details change.
  - **Tests:** insertion **flag-off 53/0 · flag-on 77/0** (added a flag-independent truth-table + opt-in
    coercion checks); render **6/0, 1 skip** both modes (added a negative-gate render case); new
    `frontend/scripts/verify-visual-pilot-opt-in.mjs` in `npm test`. Full backend battery + offline eval +
    frontend build/test green; **Docker rebuild + `/api/health` `{"ok":true}` + `smoke_release.py` 29/0**;
    live: image ships the dual gate and an LLM job with `enable_visual_references:true` completes `done`
    with no effect while the master switch is off. **Chandra extraction still blocked by Slice 45 `not_run`.**

### (previous) Slice 54 — minimal V4/V5 visual markdown image pilot, off by default — committed `cdebbaa`, merged to trunk
- When `GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT` is set, it inserts
  **at most one** existing `fitz_local` `extracted_figure` (already cropped to `assets/<slug>.png` by
  Slice 40) into the guide as a standard Markdown image `![safe caption](assets/<slug>.png)`, through
  the **existing** `save_clean_md` chokepoint and the **existing** PDF/HTML/DOCX renderers. Flag **off
  ⇒ byte-identical** clean.md / output (no artifact reads). **Degrade-never-fail. No Chandra. No
  renderer rewrite. No new artifact. No frontend toggle.** (Slice 55 adds the per-job opt-in on top.)
  - **Proven:** the existing renderers already resolve a job-local relative `assets/<slug>.png` ref
    (PDF/HTML via the job `file://` root; DOCX via `_resolve_image_path`, degrading to `[image missing]`)
    — so **no renderer change was needed**.
  - **New module `pipeline/visual_markdown_insertion.py` (stdlib-only):** `is_visual_markdown_pilot_enabled()`,
    `apply_visual_markdown_pilot(job, clean_md) -> (str, info)` (the degrade-never-fail entry point wired
    at `run_markdown_job.run_raw_markdown_pipeline` just **before** `save_clean_md`),
    `select_visual_markdown_candidate(...)`, `validate_visual_asset_ref(...)`,
    `build_visual_markdown_image(...)`, `insert_visual_markdown_reference(...)`.
  - **Candidate:** `fitz_local`+`extracted_figure` only, ≤1; prefer a replacement-plan
    `candidate_include_as_figure` item resolved in the manifest, fallback to first safe manifest figure;
    never Chandra/`mistral_ocr`/`page_visual_signal`.
  - **Safety:** ref must be `^assets/[A-Za-z0-9_]+\.png$` **and** a real file inside the job dir
    (realpath-containment; rejects absolute/`..`/backslash/url/data-uri/non-png/symlink-escape). Generic
    page-only caption (≤80, escaped). Placement = `<!-- visual-anchor: source_page_NNNN -->` marker if
    present, else a trailing `## Visual Reference` section. Closed-vocab skip reasons; stderr-only; no
    job.json/artifact-list change; no `clean.md` write outside `save_clean_md`.
  - **Tests:** `test_scripts/test_visual_markdown_insertion.py` (flag-off **26/0**, flag-on **50/0**) +
    `test_scripts/test_visual_markdown_render.py` (HTML/PDF/DOCX render, host-skippable). **Chandra
    extraction still blocked by Slice 45 `not_run`.**

### (previous) Slice 53 — true Anki `.apkg` export, merged to trunk
- Adds a real,
  importable Anki package export for the *already generated* quiz/flashcard items —
  **direct user-visible study value**, deliberately untouching the visual advisory pipeline, visual
  rendering, Chandra, OCR routing, extraction, and guide prompts.
  - **New module `pipeline/anki_export.py` (stdlib-only:** `sqlite3`/`zipfile`/`json`/`hashlib`/`html`/
    `io`/`os`/`re`/`tempfile`). An `.apkg` = ZIP{`collection.anki2` SQLite **schema 11** + empty `media`
    map}. **No `genanki`/third-party dep added** (requirements.txt unchanged); no network/model/media/LaTeX.
    API: `build_apkg(items, *, job_id, quiz_n, title=None) -> bytes`, `normalize_cards(...)`,
    `deck_id_for(...)`, `deck_name_for(...)`, `apkg_filename(...)`.
  - **Card model:** shared **"GuideForge Basic"** `Front`/`Back` (HTML-escaped). MCQ lists options on
    Front + resolves answer letter to full option text on Back (mirrors existing `_render_quiz_export`).
  - **Deterministic IDs:** fixed app-level `MODEL_ID`; per-job deck id = stable SHA-256(job+quiz) →
    safe id range under `GuideForge::<title>`; **index-based note GUIDs** (never card text) + **fixed
    timestamps** ⇒ byte-stable re-export that updates (not duplicates) on re-import.
  - **Route (no new route):** `GET /api/jobs/{job_id}/quizzes/{quiz_n}/export?format=apkg` —
    `apkg` added to `VALID_EXPORT_FORMATS` (`{csv, anki_tsv, quizlet, apkg}`); returns
    `application/octet-stream` + `attachment; filename="quiz-<job>-<n>.apkg"`. **CSV/anki_tsv/quizlet
    unchanged.** Empty/malformed cards skip safely; **zero cards → valid empty-deck `.apkg`** (no error).
  - **Frontend:** one button added to the existing quiz export row in `RecentJobsPanel.jsx`
    (`{ format: "apkg", label: "Anki .apkg" }`); no new page/redesign; no visual-advisory UI touched.
  - **Test:** `test_scripts/test_anki_export.py` (**46/0** host; route section runs in Docker). No-leak:
    no keys/paths/urls/data-uris/sockets/job-id; no images/media in decks. **Chandra extraction still
    blocked by Slice 45 `not_run`; visual render insertion remains a separate decision.**

### (previous) Slice 52 — visual insertion planner core (pure & unwired), merged to trunk at `88c1aa8`
- **Working tree:** **Slice 52 (visual insertion planner core — pure & unwired)** on branch
  `slice52-visual-insertion-planner-core` (branched from trunk after Slice 51 merged at `ee9be55`).
  Adds `pipeline/visual_insertion_planner.py`: given a `visual_replacement_plan.json`-shaped plan (and,
  optionally, a **safe-only** source-page anchor inventory), it returns a **separate advisory
  insertion-position plan** — per-asset `insertion_mode` / `placement` / `anchor_status` with
  closed-vocab `reasons`. Planning-core slice only: **no artifact written, no embedding, no production
  decision**.
  - **Public API (stdlib-only `re`/`typing`):** `plan_visual_insertion_item(item, *,
    anchors_by_page=None) -> dict`; `plan_visual_insertions(items, *, anchors_by_page=None) ->
    list[dict]`; `build_visual_insertion_plan(replacement_plan, *, source_page_anchors=None) -> dict`.
  - **Report shape:** `{version:1, kind:"visual_insertion_plan", status:"completed",
    source:"visual_replacement_plan.json", insertions:[…], summary:{insertion_count,
    figure_reference_count, table_reference_count, text_summary_reference_count, review_only_count,
    unknown_count, anchor_matched_count, anchor_missing_count}, warnings:[…]}`. Each insertion:
    `{asset_id, source_page, source_provider, asset_type, candidate_action, insertion_mode, placement,
    anchor_id, anchor_status, reasons, warnings}`.
  - **Mapping (advisory):** include_as_figure→`figure_reference`, convert_to_table→`table_reference`,
    summarize_as_text→`text_summary_reference`, review_only→`review_only`(`review_appendix`,
    anchor `not_required`), unknown/malformed→`unknown`. A matching source-page anchor →
    `anchor_status:"matched"` + `source_page_reference` + sanitized `anchor_id`; any miss → `missing` +
    placement `unknown` + `anchor_lookup_missing` (stays advisory). **Chandra** (`chandra_local`
    provider OR a `chandra_blocked` input marker) is **never** a direct insertion → degrades to
    `review_only` + `chandra_blocked`.
  - **Anchors:** safe-only inventory (list of `{source_page, anchor_id}`, dict keyed by page, or None);
    only a slug-safe `anchor_id` is read; invalid/empty anchor ids are **dropped** (never emitted), a
    page they covered then degrades to `missing`.
  - **Confirmations:** pure & total (never raises); **not wired** into `run_llm_job.py`/anything; **no
    artifact written** (no `visual_insertion_plan.json` this slice); no API route; no frontend/UI; no
    export-bundle/generic artifact-list exposure; manifest/scoring/replacement-plan schemas unchanged and
    **never mutated**; replacement plan and anchors **not mutated**; no prompt/render/extraction/
    OCR-routing/guide-output change; no `clean.md` write; no model/`llama-server`/cloud/network call; no
    image files/bytes; no caption/source-text/provider-payload/path/token/data-URI/base64/argv leak.
    Chandra *extraction* integration remains **blocked** by Slice 45 `status:not_run`.
  - **Files:** new `pipeline/visual_insertion_planner.py`, new
    `test_scripts/test_visual_insertion_planner.py`; + `CURRENT_TASK.md` / `NEXT_CHAT_HANDOFF.md` /
    `DECISIONS.md`.
  - **Validation:** `compileall api pipeline test_scripts` OK; insertion-planner **243/0**; existing
    replacement-planner **186/0**, plan-artifact **68/0**, scoring **146/0** + **58/0**,
    advisory-export-bundle host-SKIP (no FastAPI; covered live in Slice 51), manifest **65/0**, figure
    **50/0**+2skip, chandra **68/68/96**, ocr **121/120/56**; offline eval 3 guides (no regression);
    frontend build + `npm run test` + advisory mjs green; `git diff --check` clean. `smoke_release.py` /
    Docker **not required** (pure/unwired — no server/extraction/render/artifact/export/UI behavior
    touched). **Status:** NOT committed (per instruction).

- **Prior slice — Slice 51 (include visual advisory JSON artifacts in export bundles) — committed
  `ee9be55`, fast-forward merged + pushed to trunk `chrome-renderer-v1`, BACKEND export-bundle inclusion
  (+ focused test), NO frontend change** (was on branch `slice51-visual-advisory-export-bundle`, branched
  from trunk after Slice 50 merged at `1ed94c9`). `export_bundle` (`POST /api/exports/bundle`) gained a
  narrow `VISUAL_ADVISORY_EXPORT_ARTIFACTS` constant + ride-along loop that bundles the three advisory
  visual **JSON diagnostics** (`visual_assets_manifest.json`, `visual_asset_scoring.json`,
  `visual_replacement_plan.json`) **alongside** requested exports **only when present**; the three names
  stayed **out of** `EXPORT_ARTIFACTS`/`EXPORT_ARTIFACT_ALIASES`/`ARTIFACTS` (no export-UI type, no
  generic UI row); ride-alongs do **not** count toward `total_included` (all-absent bundle still 404s);
  bundle index records a `visual_advisory_included` filename list only. JSON diagnostics only — no
  cropped images/image bytes; artifacts read-only & never mutated; no guide/prompt/render/extraction/
  routing/schema change. Full Docker rebuild/recreate + `/api/health` + `smoke_release.py` passed.

- **Prior slice — Slice 50 (Job Details "Visual advisory" diagnostics panel) — committed `1ed94c9`,
  fast-forward merged + pushed to trunk `chrome-renderer-v1`, FRONTEND read-only UI (+ pure helper +
  node harness), NO backend change** (was on branch `slice50-jobdetails-visual-advisory-panel`,
  branched from trunk after Slice 49 merged at `9338eb9`). Read-only Job Details `Visual Advisory`
  drawer tab surfacing the advisory visual artifact chain via **exact-name artifact fetches only**,
  showing **safe COUNTS + closed-vocab status only**; **404 ⇒ calm "Not available"**; no raw JSON
  inline. The three artifacts stayed **out of** `ARTIFACTS` / `EXPORT_ARTIFACTS` / `_artifact_urls` /
  `_artifact_details` / existing artifact UI rows. Guide output, prompts, rendering, extraction, OCR
  routing, and artifact schemas unchanged; visual artifacts not mutated; candidate actions advisory
  only; Chandra *extraction* still **blocked** by Slice 45 `status:not_run`.

- **Prior slice — Slice 49 (persist `visual_replacement_plan.json` as an advisory exact-name artifact)
  — committed `9338eb9`, fast-forward merged + pushed to trunk `chrome-renderer-v1`, CODE
  (production-wired artifact writer/serving + new test)** (was on branch
  `slice49-visual-replacement-plan-artifact`, branched from trunk after Slice 48 merged at `967748a`).
  Wires the Slice 48 planner core into the job artifact flow as the sibling artifact
  `visual_replacement_plan.json`, **derived from** the already-written `visual_asset_scoring.json`
  (with the manifest passed only for a **presence-only** asset-id cross-check). **Not** a Chandra
  integration slice; no visuals embedded; no production include/omit decision.
  - **What it does:** in `run_llm_job._attach_sources`, immediately after
    `write_visual_asset_scoring_report(...)`, calls
    `write_visual_replacement_plan_report(job, scoring_report, manifest=visual_manifest_obj)` reusing
    the already-read manifest object and the returned scoring report (no re-read). Reachable **only by
    exact name** at `/api/jobs/{id}/artifacts/visual_replacement_plan.json` (dedicated `_artifact_path`
    branch); absent → graceful 404. New `Job.visual_replacement_plan_json` property. Stable JSON
    (`indent=2, sort_keys=True`).
  - **Advisory / degrade-not-fail / no mutation:** new writers
    `write_visual_replacement_plan_report` / `write_skipped_visual_replacement_plan_report` live in
    `pipeline/visual_replacement_planner.py` (added stdlib `json`+`sys`; take a duck-typed `job`, no
    `job_manager` import; the pure planning core is unchanged). The writer never raises into job
    generation, never gates/fails the job, never touches job status / validation / `clean.md`, and
    **never mutates** `visual_asset_scoring.json` or `visual_assets_manifest.json` (manifest =
    presence only). Scoring unavailable/skipped → `skipped` (`visual_scoring_unavailable`); write
    error → `skipped` (`write_failed`). Closed skip reasons; short `safe_message`; stderr (if reached)
    carries an exception class name only.
  - **Report shape (Slice 48, preserved):** `{version:1, kind:"visual_replacement_plan",
    status:"completed"|"skipped", source:"visual_asset_scoring.json", items, summary, warnings}`.
    Candidate actions stay **advisory only** (candidate_include_as_figure / candidate_convert_to_table
    / candidate_summarize_as_text / review_only / unknown). The plan never carries
    `image_ref`/`caption`/`source_text`, image bytes, data URIs, base64, paths, URLs, headers, tokens,
    socket/model/mmproj/executable paths, raw argv, or raw provider/OCR payloads.
  - **Deliberately NOT exposed generically:** not in `ARTIFACTS`, `EXPORT_ARTIFACTS`, `_artifact_urls`,
    `_artifact_details`, export bundles, or any frontend/UI row — exact-name download only.
  - **Chandra still blocked:** any `chandra_local` item is planned only as advisory and carries
    `chandra_blocked`; Chandra *extraction* integration remains gated by Slice 45 `status:not_run`
    (`operator_input_not_supplied`).
  - **Files:** `pipeline/visual_replacement_planner.py` (+writers), `pipeline/job_manager.py`
    (+property), `api/server.py` (+exact-name branch), `pipeline/run_llm_job.py` (+wiring + import),
    new `test_scripts/test_visual_replacement_plan_artifact.py` (**68/0**), updated
    `test_scripts/test_visual_replacement_planner.py` (**186/0**, import hygiene now allows `json`/`sys`),
    + `CURRENT_TASK.md` / `NEXT_CHAT_HANDOFF.md` / `DECISIONS.md`.
  - **Validation:** `compileall api pipeline test_scripts` OK; planner **186/0**; plan-artifact
    **68/0**; scoring-core **146/0**; scoring-artifact **58/0**; manifest **65/0**; figure **50/0**
    (+2 skip); chandra normalizer/provider/live-harness green; ocr suites green; extraction-metadata
    **9/9**; offline eval 3 guides (no regression); frontend build+test green; `git diff --check`
    clean. Full Docker rebuild/recreate + `/api/health` + `smoke_release.py` required (touches
    `api/server.py` + `job_manager.py` + `run_llm_job.py`). **Status:** NOT committed (awaiting
    operator review).

- **Prior slice — Slice 48 (visual replacement planner core — pure, unwired; roadmap V3) — committed
  `967748a`, fast-forward merged + pushed to trunk `chrome-renderer-v1`, CODE (new module + test, NO
  production wiring)** (was on branch `slice48-visual-replacement-planner-core`, branched from trunk
  after Slice 47 merged at `b1680fa`). Added `pipeline/visual_replacement_planner.py` — pure,
  deterministic planner that turns a `visual_asset_scoring.json`-shaped report into an advisory
  `visual_replacement_plan` (public API `plan_visual_replacement_candidate` /
  `plan_visual_replacement_candidates` / `build_visual_replacement_plan`). Slice 49 then wired its new
  artifact writers in. Advisory candidate actions only; never mutates report/manifest; Chandra items
  carry `chandra_blocked`. Test `test_visual_replacement_planner.py`.

- **Prior slice — Slice 47 (persist `visual_asset_scoring.json` as an advisory exact-name artifact) —
  committed `b1680fa`, fast-forward merged + pushed to trunk `chrome-renderer-v1`, CODE
  (production-wired artifact writer/serving + new test)** (was on branch
  `slice47-visual-asset-scoring-artifact`, branched from trunk after Slice 46 merged at `e8e69ed`).
  Persists the Slice 46 scoring report as the sibling artifact `visual_asset_scoring.json`,
  **derived from** the already-written `visual_assets_manifest.json`.
  - **What it does:** writes `visual_asset_scoring.json` in `run_llm_job._attach_sources`
    immediately after `write_visual_assets_manifest(...)` (reads the just-written manifest back via
    `_read_visual_manifest_for_scoring`, total/`None`-on-error, then
    `write_visual_asset_scoring_report(job, manifest)`). Reachable **only by exact name** at
    `/api/jobs/{id}/artifacts/visual_asset_scoring.json` (dedicated `_artifact_path` branch); absent
    → graceful 404. New `Job.visual_asset_scoring_json` property. Stable JSON
    (`indent=2, sort_keys=True`).
  - **Advisory / degrade-not-fail / no mutation:** the writer never raises into job generation,
    never gates/fails the job, never touches job status / validation / `clean.md`, and **never
    mutates** `visual_assets_manifest.json`. Non-scorable/unavailable manifest → `skipped`
    (`visual_manifest_unavailable`); write error → `skipped` (`write_failed`). Closed skip reasons
    only; `safe_message` is a fixed constant; stderr (if reached) carries an exception class name
    only. `recommended_action` stays `unknown` for every score.
  - **Deliberately NOT exposed generically:** not in `ARTIFACTS`, `EXPORT_ARTIFACTS`,
    `_artifact_urls`, `_artifact_details`, export bundles, or any frontend/UI row — exact-name
    download only. Written **exactly when** the manifest is written; non-PDF / no-extraction jobs
    omit **both** artifacts. No guide-output / prompt / render / extraction / OCR-routing / visual-
    embedding change; no model/`llama-server`/Chandra/Mistral/Gemini/network/image-file access.

- **Prior slice — Slice 46 (visual asset scoring core — pure, unwired; roadmap V3) —
  committed `e8e69ed`, fast-forward merged + pushed to trunk `chrome-renderer-v1`, CODE (new
  module + test, NO production wiring)** (was on branch
  `slice46-visual-asset-scoring-core` (branched from trunk after Slice 45 merged at `591d664`).
  Returns to the **provider-agnostic visual stack** — NOT a Chandra integration slice.
  - **New module:** `pipeline/visual_asset_scoring.py` — a pure, deterministic, stdlib-only
    (`re`, `typing`) scoring core for `visual_assets_manifest.json`-shaped asset candidates. It is
    the V3 "candidate scoring" step (`docs/VISION_ROADMAP.md` §8) between the advisory manifest (V1)
    and any future inclusion decision (V4+). Public API:
    `score_visual_asset_candidate(asset, *, page_context=None)`,
    `score_visual_asset_candidates(assets, *, page_context_by_page=None)`,
    `score_visual_assets_manifest(manifest, *, page_context_by_page=None)`.
  - **Output:** a brand-new `visual_asset_scoring` report (`scores[]` + `summary` priority counts +
    closed `warnings`). Each score has `priority` ∈ {high, medium, low, unknown}, a numeric
    `include_score`, closed-vocab `reasons`/`warnings`, and `recommended_action` that **stays
    `unknown` for every score this slice** (no include/omit decision yet). Captions are used only as
    a boolean `has_caption` signal and are **never emitted**; ids/page/provider/type are coerced to
    safe closed-vocab/slug-safe values; the function never raises and **never mutates** the input.
  - **Pure / unwired / no production change:** not imported by `run_llm_job.py` or anything else; no
    artifact written; `pipeline/visual_assets_manifest.py` unchanged (no schema change); no
    extraction/OCR-routing/API/frontend/Provider-Settings/LMM/render/export change; no `clean.md`
    write; no model/llama-server/cloud calls; no image files/bytes.
  - **Chandra still blocked:** Chandra *extraction* integration remains gated by Slice 45
    `status:not_run` (`operator_input_not_supplied`) until a live harness pass is recorded — this
    slice only reads the asset *shape* the Slice 42 normalizer would emit; it integrates nothing.
  - **New test:** `test_scripts/test_visual_asset_scoring.py` (**146/0**).
  - **Validation:** `compileall api pipeline test_scripts` OK; scoring **146/0**, manifest **65/0**,
    figure-extraction **50/0** (+2 skipped), chandra-normalizer **68/0**, chandra-local-provider
    **68/0**, chandra-live-harness **96/0**, ocr-modes **121/121**, ocr-routing-policy **120/120**,
    ocr-routing-integration **56/56**, offline eval 3 guides (no regression), frontend build+test
    green, `git diff --check` clean. `smoke_release.py` not required (pure unwired module, no
    production behavior touched). **Status:** committed `e8e69ed`, fast-forward merged + pushed to
    trunk `chrome-renderer-v1`; Slice 47 (above) builds the persisted artifact on top.

- **Prior slice — Slice 45 (Chandra live-harness validation report + operator runbook) — committed
  `591d664`, fast-forward merged + pushed to trunk `chrome-renderer-v1`, DOCS-ONLY** (was on branch
  `slice45-chandra-live-harness-validation-report`). A **gate/report** slice — no code/test/app change.
  - **New doc:** `docs/CHANDRA_LIVE_HARNESS_VALIDATION.md` — operator runbook for the Slice 44
    harness: purpose (proves the request/response/normalizer boundary only — not production wiring,
    not extraction integration, not release smoke), operator-owned preconditions (operator starts
    their own `llama-server`, supplies a non-private image; no path/endpoint/port/token/socket/
    model/mmproj/exec recorded), a **placeholder-only** run-command template, the safe-output
    policy (closed-vocab summary fields only), a recordable-result spec, the gate decision, and
    future-slice notes.
  - **Recorded result:** `status: not_run`, reason `operator_input_not_supplied` — no live server
    endpoint / non-private image supplied this slice, so **no live HTTP request was made** and no
    result was fabricated. **Gate:** `not_run` ⇒ the disabled extraction-side adapter slice **stays
    blocked** until a live run passes (pass ⇒ proceed to a still-**disabled**, off-by-default
    extraction-side adapter with Tesseract/`fitz` fallback, degrade-not-fail).
  - **No production change:** docs-only — no `pipeline/extract.py`/OCR-routing/`ocr_routing`/
    `extraction_metadata.json`/`visual_assets_manifest.json`/`clean.md`/API/frontend/Provider
    Settings/LMM/render/export/artifact change; no `llama-server` management; no subprocess/Docker;
    no model/mmproj/quant file or raw OCR/provider output committed.
  - **Validation:** `git diff --check` clean; `git diff --name-only` docs-only
    (`docs/CHANDRA_LIVE_HARNESS_VALIDATION.md` + `CURRENT_TASK.md` + this handoff + `DECISIONS.md`).
    No build/smoke required. **Status:** committed `591d664`, fast-forward merged + pushed to trunk.

- **Prior slice — Slice 44 (Chandra local provider live validation harness) — committed `8468c16`,
  fast-forward merged + pushed to trunk `chrome-renderer-v1`, MANUAL / OPT-IN ONLY** (was on branch
  `slice44-chandra-local-provider-live-harness`, branched from trunk after Slice 43 merged at
  `2bc14ef`). A manual harness so an operator can prove — *outside
  production app flow* — that a local Chandra-capable `llama-server` **they started themselves**
  can return output that flows through the Slice 43 boundary
  (`parse_chandra_chat_response` → `normalize_chandra_chat_response` → Slice 42 normalizer →
  **safe closed-vocabulary summary only**). A real HTTP request happens **only** when the operator
  runs the CLI with their own `--endpoint` and `--image`; importing the module triggers no
  network/file/model/subprocess/Docker/server access; automated tests inject a fake transport.
  - **Script:** new `test_scripts/validate_chandra_local_provider_live.py` — stdlib `urllib`
    transport (operator-only), `run_validation(endpoint, image_path, *, transport=None,
    timeout_seconds=60.0, prompt=None)`, `redact_endpoint_for_display(...)` →
    `http://<host>:<port>/...` or `local_endpoint_supplied`, `safe_summary_from_normalized(...)`,
    `http_transport(...)` (no auth header), `print_safe_summary(...)` (whitelisted keys).
  - **Safe summary only:** `reachable` / `request_ok` / `image_supplied` / `endpoint_display` /
    `parse_status` / `normalized_kind` / `normalized_status` / `source_text_char_count` /
    `asset_count` / `parse_warnings` / `normalize_warnings` / `failure_category` / `elapsed_ms`
    (verbose). Never echoes raw OCR text, raw provider payload, image path/bytes, base64/data URI,
    full URL/query/headers, `Authorization`/`Bearer`, argv, or model/mmproj/exec/socket paths.
  - **No production change:** no `pipeline/extract.py`/OCR-routing/`ocr_routing`/
    `extraction_metadata.json`/`visual_assets_manifest.json` change; no `clean.md`; no API route;
    no frontend/Provider Settings/LMM change; no render/export/artifact change; no `llama-server`
    management; no subprocess/Docker; no model/mmproj/quant file or raw OCR dump committed.
  - **Tests:** new `test_scripts/test_chandra_live_harness.py` — **96/0**, fake transport only, no
    live server (success parse+normalize; counts/tokens-only summary; no raw OCR; malformed /
    `response_malformed` / `connection_failed` / `request_failed` categories without traceback;
    endpoint/query/token/userinfo/path redaction; image path & base64 never leaked; raw malicious
    payload never leaked; request built via the Slice 43 builder; `provider_empty_content` /
    `image_read_failed`; real transport never invoked; no forbidden imports). Full battery green
    (compileall; chandra/normalizer/manifest/figure/ocr/pdf/math/lint/eval/ask suites; frontend
    build+test; `git diff --check` clean). `smoke_release.py` not required (manual-harness-only).
  - **Status:** committed `8468c16`, fast-forward merged + pushed to trunk. **Next:** Slice 45
    (above) records the operator runbook + gate; only after a live harness pass does a later slice
    add a still-**disabled** extraction-side adapter.

- **Prior slice — Slice 43 (Chandra local provider/client skeleton) — committed `2bc14ef`, merged
  to trunk, DISABLED / UNWIRED.** A small skeleton that names the third Chandra boundary and makes
  it testable **without running any model**: page image bytes → **OpenAI-compatible `llama-server`
  request shape** → (a future integration runs the model) → raw output string → **Slice 42
  normalizer** → safe output. **Foundation only**, NOT a provider integration — nothing in a
  production path constructs or calls it.
  - **Module:** new `pipeline/chandra_local_provider.py` — stdlib-only (`base64`, `typing`) +
    the Slice 42 normalizer; no new dependency; **no import** of `fitz`/Tesseract/llama.cpp/
    `openai`/Mistral/Gemini/Chandra-runtime/LMM/`socket`/`subprocess`/HTTP client. Public API:
    `build_chandra_image_message_payload(image_bytes, *, mime_type="image/png", prompt=None)`,
    `parse_chandra_chat_response(response)`, `normalize_chandra_chat_response(response, *,
    source_page=1)`, and `class ChandraLocalProvider` (`provider_id="chandra_local"`,
    `enabled=False`, `is_enabled()→False`).
  - **Request shape:** OpenAI-compatible multimodal chat payload
    (`messages=[{role:"user", content:[{type:"text"}, {type:"image_url"}]}]`,
    `temperature=0.0`, `max_tokens`); image → base64 data URI **only inside the builder**; no
    model id / base URL / host path / argv embedded. `CHANDRA_OCR_LAYOUT_PROMPT` requests layout
    HTML w/ `data-label` + `data-bbox`, HTML tables, LaTeX math, captioned diagrams/figures (a
    template constant, **not** wired into generation). Non-bytes → `TypeError` w/o echo; unknown
    mime collapses to PNG.
  - **Response shape:** `parse_chandra_chat_response` accepts `{"choices":[{"message":{"content":
    ...}}]}` + SDK-object equivalents; **total** (never raises); degrades to closed-vocab warnings
    (`empty_response`/`no_choices`/`no_message`/`no_content`/`malformed_response`) and **never
    echoes the raw payload**. `normalize_chandra_chat_response` bridges parse →
    `normalize_chandra_output(...)`, returning the Slice 42 `kind:"chandra_normalized_output"`
    envelope (all leak-scrubbing delegated to Slice 42); empty/malformed → valid `completed` +
    `empty_output`.
  - **NOT done this slice:** no real Chandra/`llama-server`/network/socket call (injected fake
    responses only); no model/mmproj/quant file; no `pipeline/extract.py` or OCR-routing wiring;
    no `ocr_routing`/`extraction_metadata.json`/`visual_assets_manifest.json` change; no
    `clean.md` write; no visual embed; no API route; no frontend toggle / Provider Settings / LMM
    change; no prompt/render/export change; no generated-guide change. `enabled` is `False`.
  - **Tests:** new `test_scripts/test_chandra_local_provider.py` — **68/0** (injected fake
    responses only; payload shape + no model/path/argv leak; prompt requests `data-label`/
    `data-bbox`/tables/LaTeX/captions; image data URI only in request not in parsed/normalized;
    mime whitelist; non-bytes rejected w/o echo; parse normal/object/degrade/no-echo; normalizer
    bridge incl. empty + malicious scrub; provider disabled; no-forbidden-imports). Validation all
    green: `compileall`; `test_chandra_normalizer` 68/0; the focused battery incl.
    `test_visual_assets_manifest` 65/0 (unchanged) + `test_local_figure_extraction` 50/0/2 +
    `test_ocr_provider`/`test_ocr_routing_policy`/`test_ocr_routing_integration`; eval
    `--offline --all` (no regression, delta 0.0); frontend build + test; `git diff --check` clean.
    `smoke_release.py` not required — no production behavior touched.
  - **Files:** `pipeline/chandra_local_provider.py`, `test_scripts/test_chandra_local_provider.py`,
    `CURRENT_TASK.md`, this handoff, `DECISIONS.md`. **Do not commit until the operator says so.**
  - **Next (design, not built):** an integration slice that flips `enabled` behind an explicit,
    **off-by-default** local OCR route on the LMM `llama-server` path — running the model, handing
    its raw string to this bridge, with **Tesseract/`fitz` fallback and degrade-not-fail**; then
    candidate scoring/`recommended_action` and asset-aware prompt/render embed.
- **Slice 42 (Chandra output normalizer core) — committed `6e7f55f`, merged + pushed to trunk
  `chrome-renderer-v1`.** A pure, deterministic, model-free normalizer (`pipeline/
  chandra_normalizer.py`) that turns a raw Chandra layout string into a safe `source_text` fragment
  + `visual_assets_manifest.json`-shaped asset candidates (closed vocab, field-by-field scrubbed,
  total/never-raises). Slice 43 builds the disabled request/response skeleton on top of it.
- **Slice 41 (Chandra GGUF hands-on spike) — committed `218de18`, merged + pushed to trunk
  `chrome-renderer-v1`; docs-only.** Hands-on confirmation that Chandra OCR 2 runs as GGUF on
  the existing `llama.cpp`/`llama-server` path (self-built ~676 MB mmproj + text quants from
  the official `datalab-to/chandra-ocr-2`; near-perfect layout-HTML w/ `data-bbox`+`data-label`,
  tables, LaTeX, captioned diagrams — even at Q4_K_M). **Verdict: proceed to provider design,
  gated.** No model files committed (throwaway workspace outside the repo). Full write-up:
  `docs/CHANDRA_GGUF_SPIKE_REPORT.md`. Slice 42 builds the normalizer it recommended.
- **Slice 40 (Local figure extraction / cropping into the visual manifest) — committed
  `bed7cf8`, merged + pushed to trunk `chrome-renderer-v1` (0 ahead / 0 behind).** The
  **first real extractor-output change** in the visual stack: with PyMuPDF (`fitz`) it
  **crops embedded image regions out of the PDF** and adds real **`extracted_figure`**
  assets (real `bbox`, safe relative `image_ref` `assets/<slug>.png`, PNG under the new
  `Job.assets_dir`) to `visual_assets_manifest.json`. **`fitz_local` only** — no
  Chandra/Mistral/Gemini/VLM/network/OCR. **Gated off by default**
  (`GUIDEFORGE_LOCAL_FIGURE_EXTRACTION`) ⇒ manifest **byte-identical to Slice 38** when
  off; assets do **not** reach the guide (manifest/PNGs only — asset-aware prompt/render
  is a later slice). **Explosion prevention** (skip tiny/decorative, collapse duplicate
  placements, caps 12/page · 200/job) + manifest **re-sanitises every extracted field**
  so it stays the un-poisonable security boundary. Files:
  `pipeline/visual_asset_extractor.py`, `test_scripts/test_local_figure_extraction.py`
  (new); `visual_assets_manifest.py`, `job_manager.py`, `run_llm_job.py` (edited).
  **Validated green:** compileall OK; `git diff --check` clean; focused test
  **59/0/0 in Docker**; `test_visual_assets_manifest.py` **65/0**; fresh
  `docker compose build` + `up --force-recreate`; `/api/health` `{"ok":true}`;
  `smoke_release.py` **29/0/0** on live :8000.
- **Slice 39 (Chandra local feasibility verification) — DOCS-ONLY, committed `7b97146`,
  merged + pushed to trunk.** It is the **Chandra equivalent of Slice 35's
  Mistral gate**: a docs-only feasibility verification of **Chandra (Datalab)** as a
  future **high-quality local** OCR / document-extraction / visual-asset provider
  (`chandra_local`) for the Local/Private mode. **Chandra was NOT installed, cloned,
  built, run, or downloaded; no dependency / provider code / API route / setting / key /
  prompt / routing / extraction / render / `visual_assets_manifest.json` schema change.**
  New **`docs/CHANDRA_OCR_VERIFICATION.md`** (§0–§12) records facts from **official
  Datalab sources** (GitHub repo, HF model cards, `MODEL_LICENSE`) checked **June 2026**:
  the target is **Chandra 2 (`datalab-to/chandra-ocr-2`, released 3/2026, ~4B reported)**
  — distinct from **Chandra 1 (`datalab-to/chandra`, 9B)** which needs **18 GB+** (16 GB
  insufficient). Verified: **olmOCR 85.9**; outputs **MD/HTML/JSON with detailed layout
  info** + image/diagram extraction **with captions + structured data**, tables/math/
  forms/handwriting/multi-column, 90+ languages; **throughput 1.44 pages/s on H100 80 GB
  @96 concurrency** (≈2 pages/s real-world est.) — **far less expected on a 16 GB
  consumer GPU**; **license = Apache-2.0 code + "AI PUBS OPEN RAIL-M (MODIFIED)" weights
  (free for research/personal/<$2M startups, no competing with Datalab's OCR API).**
  **PATCHED with GGUF evidence (feasibility-changing):** a community
  **`prithivMLmods/chandra-ocr-2-GGUF`** conversion reports **5B params / `qwen35`** and a
  quant ladder (Q4_K_M ≈ 3.07 GB · Q5_K_M ≈ 3.51 GB · Q6_K ≈ 3.99 GB · Q8_0 ≈ 5.16 GB ·
  BF16/F16 ≈ 9.7 GB) + separate **`mmproj` ≈ 367–676 MB** — **community evidence, not the
  official `datalab-to` distribution.** So the **param count is no longer stated as "4B
  official"** (re-verify), and the **hardware verdict is revised from
  `uncertain-but-promising` to: GGUF-quantized Chandra OCR 2 likely feasible on the
  RTX 5070 Ti 16 GB; VRAM is likely NOT the main blocker.** The real blockers are now
  **multimodal `llama.cpp` support, `mmproj` loading, OCR quality, throughput,
  long-document behavior, and integration stability** (throughput caveat kept: a
  500–2,000-page deck may still be slow). **Integration is now two paths:** official
  vLLM/HF/Transformers (the **accuracy/reference baseline**) vs the **practical first
  spike = GGUF through existing `llama.cpp`/`llama-server`/LMM** — which **may avoid a new
  heavy vLLM service** if multimodal support works (don't assume until tested).
  **License verdict unchanged: fine for personal/single-operator; multi-user/commercial
  needs Datalab review.** The doc **honestly corrects roadmap §6** (rich Mermaid/chart-
  data/bbox/typed-block claims reported but NOT itemized; confirm via real output). **First
  spike checkpoint:** *can current `llama-server` load Chandra GGUF + `mmproj` and OCR a
  page image?* **Recommendation (revised): `Proceed to hands-on GGUF spike after manifest
  schema` (Slice 38 shipped) with a license caveat — still NOT approval to implement.**
  Files (docs only): `docs/CHANDRA_OCR_VERIFICATION.md` (new), `CURRENT_TASK.md`,
  `NEXT_CHAT_HANDOFF.md`, `DECISIONS.md`. Validation: `git diff --check` clean,
  `git diff --name-only` docs-only (no build/smoke needed — no code touched).
- **Trunk HEAD is now Slice 39 (`7b97146`), committed + merged + pushed** — Slices 30–39
  are on trunk (Slice 40 above is the uncommitted working tree). Slice 38 (`8a788c7`,
  Visual assets manifest schema from existing signals) was
  validated green (`test_visual_assets_manifest` 65/65, fresh Docker rebuild +
  `--force-recreate`, `/api/health` 200, `smoke_release.py` **29/0/0** on live :8000,
  exact-name route confirmed wired, `git diff --check` clean) before the fast-forward
  merge.
- **(deeper history) Slice 37 (`9fbbb1d`) + Slice 36 detail below** —
  Slices 30–37 are on trunk. Slice 37 (OCR/extraction mode + cost/budget skeleton)
  added `pipeline/ocr_modes.py` (pure stdlib framework — modes, provider roles/ids,
  budget/cost DTOs, `resolve_ocr_mode_config` returning the Slice 33 routing shape
  with `allow_cloud_ocr=False` unless a cloud-capable mode + real-bool
  `cloud_opt_in=True`) + `test_ocr_modes.py`; **no** extraction/routing/prompt/API/UI
  change and **no** network call. Slice 36 (Revised visual / cost / provider-strategy
  roadmap) added `docs/VISION_ROADMAP.md` and updated the live docs; it touched
  **no** application code, dependency, key, prompt, routing, extraction, schema, or
  render path, and called **no** external OCR/vision API. The roadmap reframes the
  visual/cost direction around the
  **Capture → Explain → Show → Trust → Retain** north star, a **provider-agnostic
  `visual_assets_manifest.json`** normalization boundary, a **three-mode** cost/
  privacy framework (Local/Private default · Smart Cloud Assist · Maximum Fidelity),
  **Chandra** as a near-roadmap high-quality *local* provider (gated, not
  production-approved), **Mistral** kept on the near map as the likely first cloud
  document-extraction provider (now **proposed Slice 43**, disabled/unwired), and a
  dependency-ordered **V1–V7** visual stack. It **resequences (does not cancel)** the
  old `HYBRID_OCR_DESIGN.md` §9 "Slice 36 = Mistral provider" item. Slices 37–43 in
  `docs/VISION_ROADMAP.md` are **proposed, not done** (Slice 37 is now the
  *implemented* item above). See `docs/VISION_ROADMAP.md`.
- **Slice 35 (Mistral OCR prerequisite verification) — DOCS-ONLY, committed +
  merged to trunk (`45a54d2`).** It added `docs/MISTRAL_OCR_VERIFICATION.md` and
  updated the live docs; it touched **no** application code, dependency, key,
  prompt, routing, or schema, and called **no** Mistral API. **Recommendation of the
  verification:** *Mistral OCR is
  a clean architectural fit (Slice 32 boundary + Slice 33/34 routing already provide
  the seams) with no technical blockers; **proceed only after the operator confirms
  live per-page pricing and accepts the privacy posture** (3rd-party processing of
  student notes, default 30-day retention unless ZDR), then implement strictly behind
  an explicit off-by-default opt-in.* The original "Slice 36 = Mistral provider
  skeleton" plan is **resequenced to proposed Slice 43** by `docs/VISION_ROADMAP.md`
  (provider-agnostic mode/budget + visual manifest land first). See
  `docs/MISTRAL_OCR_VERIFICATION.md` and `docs/VISION_ROADMAP.md`.
- **(Historical, retained below)** **Slice 34 (wire local OCR routing into extraction)**
  was at one point uncommitted on `slice34-wire-local-ocr-routing`; it is **now
  committed to trunk** (`25e3fd3`). **Trunk commit chain:** Slice 34 = `25e3fd3`;
  Slice 33 = `5296976`; Slice 32 = `c42837c`; Slice 31 = `ce0332e`; Slice 30 =
  `752bf03`. Do not force-push.
- **Slice 34 (wire local OCR routing into extraction):** first **live, local-only,
  behaviour-compatible** integration of the Slice 33 policy into the PDF extraction
  path. `pipeline/extract.py` now imports `ocr_routing.decide_ocr_route` +
  `extraction_metadata.classify_pdf_page_record`; new
  `_pdf_route_decision(record, *, ocr_ready)` maps a page's already-collected signals
  → advisory `classification` (shared classifier) → policy decision
  (`local_ocr_available = ocr_ready`, `allow_cloud_ocr=False`), attached by
  `_pdf_page_metadata(..., ocr_ready=...)` to every PDF page. **Recorder, not a
  router:** it never decides whether OCR runs — the unchanged `_extract_pdf` per-page
  logic still does — so **extracted text + `## Page N` anchors are byte-identical**
  and OCR-availability behaviour is preserved (a blank page extraction historically
  *attempts* is still attempted even though the advisory route says `skip_ocr`).
  Adds additive per-page fields `ocr_route_action` / `ocr_route_provider` /
  `ocr_route_reason` / `ocr_route_confidence` / `ocr_route_warnings` — closed-vocab,
  JSON-safe, **local-only** (`ocr_route_provider` is only `"tesseract_local"` or
  `null`, never a cloud id). `extraction_metadata._safe_page` carries them through
  with new `_safe_route_*` whitelists (vocab imported from `ocr_routing`) — same
  carry-and-coerce posture as `method`/`warnings`; a smuggled value coerces to a safe
  token, no path/secret/blob/URL/free-text survives; emitted only when present so
  legacy/non-PDF records stay byte-identical. **`extraction_metadata.json` stays
  `version: 2`** (additive-field rule). Degrade-not-fail: any adapter error records a
  fixed safe route and never fails a generation. New
  `test_scripts/test_ocr_routing_integration.py` (56 checks; fitz e2e skipped on
  host). **No** Mistral/cloud OCR, provider settings, prompt, `/api/jobs/llm`-field,
  frontend/UI, Ask/retrieval, LanceDB/embeddings, generic-`ARTIFACTS`/export-bundle,
  render-pipeline, generation-gating, or other artifact-schema change; OCR still goes
  through the Slice 32 local provider boundary unchanged. **Next: Slice 35** — Mistral
  OCR prerequisite verification (docs-only; gate for the gated cloud provider 36).
- **Slice 33 (hybrid OCR routing policy core):** new **pure, deterministic,
  dependency-free** module `pipeline/ocr_routing.py` — the "pure core, then
  integrate" step in `HYBRID_OCR_DESIGN.md` §9 (policy = §5/§6). Public:
  `decide_ocr_route(page_metadata, config=None)` (single page),
  `decide_ocr_routes(pages, config=None)` (list + shared OCR-page budget),
  `default_config()`. Reads **only** `page_metadata["classification"]`; output is
  a JSON-safe `{action, provider, reason, confidence, warnings}` of **closed-vocab
  tokens only** — `action` ∈ `{use_embedded_text, use_local_ocr, skip_ocr,
  cloud_ocr_candidate, unknown}`, `provider` is `null` or `"tesseract_local"`.
  **Local-first, cloud-off by default**: `cloud_ocr_candidate` is returned only
  when `allow_cloud_ocr` is explicitly `True` AND local OCR is unavailable
  (provider stays `null` — nothing is wired). Budget caps OCR-bound pages
  deterministically; malformed/hostile input → fixed safe `unknown` decision (no
  path/secret/blob leak). **NOT wired into extraction** — nothing in `extract.py`,
  `api/`, or the frontend imports it (grep-verified). No extraction-text, OCR-call,
  Mistral/cloud, provider-settings, prompt, `/api/jobs/llm`-field, frontend/UI,
  Ask/retrieval, LanceDB/embeddings, generic-`ARTIFACTS`/export-bundle, render-
  pipeline, generation-gating, or artifact-schema change. New
  `test_scripts/test_ocr_routing_policy.py` (120 checks). **Next: Slice 34** wires
  the router into the local Tesseract path and records
  `ocr_recommended`/`ocr_attempted`/`skipped_reason` (first extraction-recording
  change; still local-only).
- **Slice 32 (OCR provider boundary refactor):** backend/pipeline refactor +
  tests/docs only — the "pure refactor" step in `HYBRID_OCR_DESIGN.md` §9. New
  `pipeline/ocr_provider.py` (`OcrRequest` / `OcrResult` / `OcrProvider` /
  `TesseractLocalOcrProvider` (`provider_id = "tesseract_local"`) +
  `get_default_ocr_provider()`) isolates OCR behind a backend-only boundary;
  `pipeline/extract.py::_extract_pdf` now OCRs through the default provider instead
  of the in-line `_ocr_page`. **Local behaviour is byte-identical**: same pages
  OCR'd, same text, same `mode`/`method`, same degrade warnings and once-per-doc
  availability messages; the old in-line path didn't catch OCR exceptions so the
  provider doesn't either (`error_category` is reserved for future cloud providers).
  `_ocr_available()` kept as a thin shim delegating to the provider (for
  `preflight_pdf` + existing tests). **`extraction_metadata.json` UNCHANGED** — no
  `ocr_provider` field, **no version bump** (stays `version: 2`); provider-id
  surfacing deferred to the routing slice (34). New
  `test_scripts/test_ocr_provider.py` (37 checks; fitz integration paths via a stub
  provider + a real-tesseract gated e2e). **No** Mistral/cloud OCR, OCR routing,
  page-classification, prompt, provider-settings, `/api/jobs/llm` field, frontend/UI,
  Ask/retrieval, LanceDB/embeddings, generic `ARTIFACTS`/export-bundle, render-
  pipeline, generation-gating, or other artifact-schema change.
- **Slice 32 (OCR provider boundary refactor):** backend/pipeline refactor +
  tests/docs only — the "pure refactor" step in `HYBRID_OCR_DESIGN.md` §9. New
  `pipeline/ocr_provider.py` (`OcrRequest` / `OcrResult` / `OcrProvider` /
  `TesseractLocalOcrProvider` (`provider_id = "tesseract_local"`) +
  `get_default_ocr_provider()`) isolates OCR behind a backend-only boundary;
  `pipeline/extract.py::_extract_pdf` now OCRs through the default provider instead
  of the in-line `_ocr_page`. **Local behaviour is byte-identical**: same pages
  OCR'd, same text, same `mode`/`method`, same degrade warnings and once-per-doc
  availability messages; the old in-line path didn't catch OCR exceptions so the
  provider doesn't either (`error_category` is reserved for future cloud providers).
  `_ocr_available()` kept as a thin shim delegating to the provider (for
  `preflight_pdf` + existing tests). **`extraction_metadata.json` UNCHANGED** — no
  `ocr_provider` field, **no version bump** (stays `version: 2`); provider-id
  surfacing deferred to the routing slice (34). New
  `test_scripts/test_ocr_provider.py` (37 checks; fitz integration paths via a stub
  provider + a real-tesseract gated e2e). **No** Mistral/cloud OCR, OCR routing,
  page-classification, prompt, provider-settings, `/api/jobs/llm` field, frontend/UI,
  Ask/retrieval, LanceDB/embeddings, generic `ARTIFACTS`/export-bundle, render-
  pipeline, generation-gating, or other artifact-schema change.
- **Slice 31 (advisory PDF page classification metadata):** backend/pipeline
  metadata + tests/docs only — the next step after Slice 30. Uses the existing
  text/word/method signals (24A) plus the Slice 30 visual/object signals to emit an
  **advisory page classification** in `extraction_metadata.json`. New pure helper
  `pipeline/extraction_metadata.py::_classify_pdf_page(record)` is called from
  `_safe_page` **after** sanitisation and reads only the sanitized
  numeric/method/visual fields (never any upstream `classification` key — smuggled
  values are overwritten by construction). Adds per page: `classification`
  (`embedded_text | ocr_fallback | likely_scanned | blank_or_low_text | mixed |
  unknown | error`; `unknown` fallback), `classification_reasons` (whitelisted
  fixed tokens only), and `ocr_recommended` (bool hint, `True` only for
  `likely_scanned`; nothing reads it yet). Heuristics are conservative and
  deterministic (meaningful = ≥40 chars OR ≥5 words, mirroring
  `_is_meaningful_page_text`); `_classify_pdf_page` never raises (degrades to
  `unknown` + `classification_unavailable`); `_safe_classification`/`_safe_reasons`
  whitelist the persisted output. Artifact stays **`version: 2`** (purely additive).
  New `test_scripts/test_pdf_page_classification.py` (56 checks, plain-dict — no
  fitz needed). **No** OCR call/routing change, Mistral/cloud OCR, provider, prompt,
  `/api/jobs/llm` field, frontend/UI, Ask/retrieval, LanceDB/embeddings, generic
  `ARTIFACTS`/export-bundle, render-pipeline, generation-gating, or other
  artifact-schema change; extraction text output unchanged.
- **Slice 30 (PDF page visual-signal metadata):** backend/pipeline metadata +
  tests/docs only — the first implementation step after the Slice 29 design. Adds
  cheap, additive, advisory-only per-PDF-page visual/object signals to
  `extraction_metadata.json` so a **future** slice can classify scanned/image-heavy
  pages and route OCR. New `pipeline/extract.py::_pdf_visual_signals(page)`
  collects, per processed page in `_extract_pdf`'s loop: `image_object_count`
  (`page.get_images`), `drawing_object_count` (`page.get_drawings`),
  `has_images`/`has_drawings`, `page_width`/`page_height` (`page.rect`), and an
  optional `visual_warnings` list of safe degrade categories. Merged via
  `_pdf_page_metadata(..., visual=...)` and carried through the sanitiser
  `extraction_metadata.py::_safe_page` (whitelisted + coerced; smuggled keys still
  stripped). Each signal degrades independently to `None` on any PyMuPDF failure —
  **never raises, never changes extraction text / mode / method / job status**, and
  no image bytes/paths/text enter the metadata. Artifact bumped `version: 1 → 2`
  (both `completed` and `skipped`) per the Slice 29 rule; all v1 keys unchanged,
  new fields optional/additive (missing = "not measured"). New
  `test_scripts/test_pdf_visual_signals.py` (44 checks, fake-page based — no fitz
  needed) + updated `test_extraction_metadata.py` (version 1→2 + visual asserts).
  **No** OCR routing/heuristic, page-classification (Slice 31), Mistral/cloud OCR,
  provider, prompt, `/api/jobs/llm` field, frontend/UI, Ask/retrieval, LanceDB/
  embeddings, generic `ARTIFACTS`/export-bundle, render-pipeline, generation-gating,
  or other artifact-schema change.
- **Slice 29 (hybrid OCR & scan-aware extraction architecture):** docs-only,
  **committed `d0b91f1`, merged to trunk**.
  New `docs/HYBRID_OCR_DESIGN.md` decides the architecture before any OCR code —
  current extraction flow (grounded in `pipeline/extract.py` /
  `extraction_metadata.py` / `run_llm_job.py` / `api/server.py`), a page
  classification model, a backward-compatible `extraction_metadata.json` evolution
  (additive/optional, `version: 1` stays readable), a backend-only OCR provider
  boundary (`tesseract_local` default + future `mistral` + future local model), a
  cost/privacy-aware routing policy (cloud opt-in, off by default), large-PDF
  interaction reusing existing preflight/page-range, Mistral OCR **prerequisites
  to verify** (not implemented), OCR security/privacy constraints, and a proposed
  7-slice sequence (Slices 30–36). Also updated `CURRENT_TASK.md`,
  `NEXT_CHAT_HANDOFF.md`, `DECISIONS.md`. **No** code/test/fixture/dependency/
  schema/extraction/OCR/prompt/provider/Ask/render change. Proposed next slices:
  30 image-object signal, 31 classification field, 32 OCR provider boundary
  refactor, 33 routing core, 34 wire router (local only), 35 Mistral prereq
  verification (docs), 36 Mistral provider (cloud, opt-in, gated).
- **Slice 28 (JobDetails guide-lint UI tab):** frontend/UI only. New read-only
  **"Guide Lint"** tab in the JobDetails drawer (`RecentJobsPanel.jsx`, after
  Verification), backed by `GuideLintPanel.jsx` + the pure normalizer
  `frontend/src/guideLintArtifact.js`, lazy-fetching `guide_lint.json` via the
  existing `getJobArtifact` helper only when the tab opens. Renders completed
  (summary + top findings, advisory copy), skipped, missing-404, malformed, and
  fetch-error states. New `frontend/scripts/verify-guide-lint.mjs` wired into the
  frontend `test` chain (+ `test:guide-lint`). Two severity-tint CSS rules added
  for the reused compact finding rows. **No** backend/pipeline/artifact-schema/
  generic-list/Exports/prompt/provider/request-field/OCR/Ask/retrieval/
  render-pipeline change; no rerun button; no job mutation.
- **Slice 27 (persist `guide_lint.json` advisory artifact):** backend/pipeline +
  tests/docs only. New `_write_guide_lint(job)` in
  `pipeline/run_markdown_job.py` runs the Slice 19 deterministic guide-lint core
  against the final sanitized `clean.md` (right after `_write_math_verification`)
  and writes `<job>/guide_lint.json` (`version`/`kind`/`status`/`source`/`report`,
  or a safe `skipped`+`lint_error` artifact on any failure). New
  `Job.guide_lint_json` property and an exact-name special-case in
  `api/server.py::_artifact_path` (`GET /api/jobs/{id}/artifacts/guide_lint.json`),
  kept OUT of `ARTIFACTS` so no generic list row appears. `expected_sections` and
  `available_source_pages` are intentionally **not** passed (manifest stores only
  canonical section keys, not emitted headings; source page anchors aren't
  reliably available here) — documented in `CURRENT_TASK.md`. Advisory-only:
  never fails/changes job status, never blocks render. New
  `test_scripts/test_guide_lint_artifact.py` (26 host checks; +1 Docker-only route
  check). **No** UI/JobDetails/generic-list/Exports/validation.json/
  math_verification.json/extraction_metadata.json/prompt/provider/request-field/
  OCR/Ask/retrieval/render-pipeline/generation-gating change.
- **Committed slice sequence (most recent first):** 25B Ask lexical retrieval
  hygiene (`ae44a85`) · 25A Ask retrieval relevance baseline (`2e97f73`) · 24A PDF
  `extraction_metadata.json` (`226767c`) · 23B source page-citation directive +
  checks (`1aac60b`) · 23A page-anchor reachability proof (`d4cd95b`) · 22
  JobDetails math-verification UI (`b932667`) · 21 per-job `math_verification.json`
  (`a492e3b`) · 20 eval harness Phase 1 (`2078c8d`) · 19 guide-lint core (`9f1becf`)
  · 18 math-verifier core (`2c47d03`) · 17 hygiene checkpoint (`ff214fd`). The
  detailed per-slice result bullets below remain accurate; ignore any older
  "uncommitted / PENDING REVIEW / branch in progress" wording in them — those
  slices are all on the trunk now.
- **Immediate next planned slice (in order):** (1) persist `guide_lint.json`
  advisory artifact — **DONE (Slice 27, committed on trunk `0d73f24`)**;
  (2) JobDetails guide-lint UI (read-only, mirror Slice 22) — **DONE (Slice 28,
  uncommitted on `slice28-jobdetails-guide-lint-ui`)**; then (3) eval golden
  corpus / baseline, then (4) true Anki `.apkg` export core. (3)–(4) not started.
- **Slice 25B (Ask lexical retrieval hygiene):** backend retrieval-ranking +
  tests/docs. New shared `pipeline/ask_lexical.py::lexical_terms` adds **stopword
  filtering** + conservative **single-`-s` plural folding**, used by **both** the
  index build (`ask_context._term_freqs`) and the query scorer
  (`ask_sessions._terms`) so they can't drift. `INDEX_VERSION` bumped `1 → 2` so
  existing Ask caches rebuild automatically (no manual deletion; index *shape*
  unchanged). Measured against the 25A baseline (k=5): blocking cases
  **unchanged** (`hit_rate@5=1.0`, `mrr=0.9`), and the paraphrase known-weakness
  case improves **rank 5 → 1** on the fixture — but it stays `known_weakness:
  true` because that win is still lexical overlap, not semantics (embeddings
  remain future work). New `test_scripts/test_ask_lexical_hygiene.py` (34 checks)
  locks it in. **No** UI/provider/LLM-call/LanceDB/embeddings/reranking/prompt/
  OCR/extraction/citation/artifact-schema/route/render-pipeline change. See
  `CURRENT_TASK.md` and `DECISIONS.md` → "Ask index version bump on lexical-
  hygiene change".
- **Slice 25A (Ask retrieval relevance harness + lexical baseline) is committed**
  on `chrome-renderer-v1` as `2e97f73`: test/docs only —
  `test_scripts/test_ask_retrieval_relevance.py` +
  `test_scripts/fixtures/ask_retrieval/`. Established the offline baseline 25B
  measures against. See `CURRENT_TASK.md`.
- **Slice 24A (persist per-page extraction metadata artifact) is committed** on
  `chrome-renderer-v1` as `226767c`. See `CURRENT_TASK.md` for its details.
- **Branch (trunk / PR target):** `chrome-renderer-v1` (all reskin slices land here).
- **Phase:** the **GuideForge reskin + UX phase is COMPLETE** (Slices 1–15
  reskinned every workspace to semantic GuideForge CSS — Tailwind utilities are
  inert in this app, live UI uses real `.sg-*` / element-cascade rules). Slice 16
  was the post-reskin **release audit + checkpoint**; Slice 17 is the follow-on
  **hygiene checkpoint** (dead-file sweep + `npm test` chain repair). With Slice 17
  the reskin/UX phase is closed and the codebase is clean — **the correctness /
  measurement phase has now begun with Slice 18 (deterministic math verification).**
- **Slice 18 (deterministic math-correctness verifier, **pure core only**) is
  committed** on `chrome-renderer-v1` as `2c47d03` (immediately after Slice 17
  `ff214fd`). Slice 18 added a standalone module + tests only — **no**
  job/artifact/API/prompt/frontend/UI integration.
- **Slice 19 (deterministic guide-lint core, pure advisory only) is committed** on
  `chrome-renderer-v1` as `9f1becf` (immediately after Slice 18 `2c47d03`). **Pure
  advisory core only:** no job integration, no artifact, no API, no
  `validation.json`, no prompt, no frontend/UI. (The advisory `guide_lint.json`
  artifact + JobDetails UI are the immediate next planned slices — see above.)
- **Slice 20 (eval harness Phase 1 — deterministic scoring framework) is
  committed** on `chrome-renderer-v1` as `2078c8d`.
- **Slice 22 (read-only JobDetails math-verification UI) is committed** on
  `chrome-renderer-v1` as `b932667`. Frontend-only, read-only JobDetails UI for
  Slice 21's per-job `math_verification.json`. The artifact is still intentionally
  excluded from generic artifact lists. `JobDetailsDrawer` has a new
  `Verification` tab that fetches `/api/jobs/{id}/artifacts/math_verification.json`
  on demand via a small API helper, then `MathVerificationPanel` renders
  completed/skipped/404/malformed/fetch-error states. Completed reports show
  summary counts and a bounded compact claim list. No backend, pipeline, prompt,
  provider, `/api/jobs/llm`, job mutation, artifact writing, guide-lint
  integration, or `validation.json` schema change.
- **Slice 23A result (page-anchor reachability proof):** PASS. The inspected path is
  `pipeline/extract.py` (`## Page N` PDF anchors) →
  `pipeline/run_llm_job.py::_attach_sources(...)` (attachment text appended under
  `## Attached Sources`) → `pipeline/orchestrator.py` (`build_messages(...)` or
  `build_messages_for_preset(...)`) → `generate_chat_completion(messages, config)`.
  The exact model-facing boundary is the assembled `messages` list. Focused test
  `test_scripts/test_page_anchor_reachability.py` plus fixture
  `test_scripts/fixtures/page_anchor_reachability/extracted_pages.txt` proves simple
  two-anchor source text, anchors surrounded by normal lecture text, attachment
  augmentation, and preset prompt assembly preserve `## Page 1` / `## Page 2` in
  the model-facing `user` content. It also proves no default citation directive or
  rendered citation assumption was added. Tests/docs only; no prompt behavior,
  frontend/UI, provider, OCR, extraction, retrieval, `validation.json`,
  `math_verification.json`, or `/api/jobs/llm` request-field change.
- **Slice 23B result (source page-citation directive + checks):** implemented
  on the Slice 23B branch before Slice 24A. `pipeline/orchestrator.py`
  conditionally inserts `SOURCE_PAGE_CITATION_DIRECTIVE` when source text contains
  `## Page N` anchors, in both template and preset prompt paths. The directive
  asks for compact `(p. 3)` / `(pp. 3-5)` citations for factual claims, examples,
  formulas, and definitions where possible, cites only anchored pages, and says
  not to invent page citations. It is inserted after axes/include-section
  guidance and before `MARKDOWN_MATH_SYSTEM`; the math system block remains last.
  No-anchor baselines remain unchanged. The old optional `slide_page_references`
  fragment now uses the same compact format to avoid conflicting prompt rules.
  `pipeline/guide_lint.py` has an optional advisory `page_citation_range` check
  when offline tooling supplies `available_source_pages`; it detects conservative
  `p. 3` / `pp. 3-5` / `page 3` forms and warns only. Eval specs may provide
  `source_page_anchors`, now used by `test_scripts/eval/score_guide.py`; the
  sample source/good guide fixtures include anchors and valid citations. New
  focused test: `test_scripts/test_source_page_citations.py`; updated
  page-anchor, page-reference-format, guide-lint, and eval-harness tests.
  No frontend/UI, JobDetails, backend route, provider, `/api/jobs/llm` field,
  OCR/extraction, retrieval/Ask, `validation.json`, `math_verification.json`,
  guide-lint artifact, or render/PDF pipeline changes.
- **Slice 24A result (PDF extraction metadata artifact):** implemented
  uncommitted on `slice24a-extraction-metadata-artifact`. `pipeline/extract.py`
  records per-page PDF extraction metadata while preserving the existing text
  output path (`## Page N` anchors, embedded-text/OCR decisions, warnings, modes,
  and page selections remain behaviorally unchanged). `pipeline/run_llm_job.py`
  writes `extraction_metadata.json` after PDF attachment extraction and before
  the LLM call. Artifact shape is `{version:1, kind:"extraction_metadata",
  status:"completed", sources:[...]}` with source filename/content type/page
  count/warnings and page method/text char/word count/page-anchor/warnings. Safe
  failure writes a skipped artifact (`reason: "metadata_unavailable"`) best
  effort, logs only exception type, and never changes job status. `api/server.py`
  exact-special-cases `GET /api/jobs/{id}/artifacts/extraction_metadata.json`,
  but the file is not in `ARTIFACTS`, export bundles, `_artifact_urls`, or
  `_artifact_details`, so generic UI/JobDetails artifact lists do not expose it.
  Coverage is PDF attachments only; non-PDF attachments are omitted. New focused
  test: `test_scripts/test_extraction_metadata.py`. No frontend/UI, prompt,
  provider, OCR heuristic, page-selection, `/api/jobs/llm` request-field,
  `validation.json`, `math_verification.json`, Ask/retrieval, VLM, or
  PDF/Chromium render-pipeline changes.
- **Slice 20 result (measurement spine only):** added `test_scripts/eval/`
  (`run_eval.py` CLI + `score_guide.py` pure core + `golden/sample.json` +
  fixtures + READMEs). It scores guide Markdown against a JSON **golden spec**
  using the Slice 18 verifier (`math`), the Slice 19 linter (`lint`), and simple
  normalized string checks (`concepts`, `must_not_claim`); live mode adds an
  `artifacts` metric. `overall` = renormalized weighted mean over the non-null
  metrics. **Offline mode is required and dependency-free** (no keys/Docker/LLM):
  `python test_scripts/eval/run_eval.py --offline --all`. Optional `--live` POSTs
  to the existing **no-provider** `/api/jobs/paste` only. Results are JSON +
  `summary.csv` under `test_scripts/eval/results/` (**git-ignored**; only fixtures/
  specs/READMEs are tracked); every result is **secret-scanned before write**.
  Regression comparison is keyed on `(spec_id, mode, guide)` and is **non-blocking**.
  **No** prompt/provider/`/api/jobs/llm`/Builder/JobDetails/artifact/OCR/retrieval/
  embedding/LanceDB/LLM-judge change; **no new dependency** (JSON specs, stdlib).
  Tests `test_scripts/test_eval_harness.py` (59/59); build, `npm test`,
  `compileall`, `test_math_verifier` (74/74), `test_guide_lint` (64/64),
  `--offline --all`, and diff check all green. `smoke_release.py` = 26/2/0; the 2
  failures are **environmental** (host thread limit → Chromium can't fork to
  render PDFs: `pthread_create: Resource temporarily unavailable (11)`), **not a
  regression** — Slice 20 adds no server/pipeline/frontend code.
- **Slice 19 result (pure advisory core only):** added `pipeline/guide_lint.py`,
  `lint_guide_markdown(markdown, *, source_name=None, expected_sections=None,
  run_katex=True) -> GuideLintReport` — a JSON-serializable findings report
  (`summary{total,error,warning,info}` + `findings[{id,rule,severity,line,message,
  excerpt}]`). Rules: `empty_heading` (nested-aware), broken-table family
  (`separator_without_header`/`header_separator_mismatch`/`malformed_separator`/
  `body_row_mismatch`, all warnings — conservative), `unbalanced_math` (`$$`/`\(`/
  `\[` = error, single `$` = warning for currency ambiguity), KaTeX bridge
  (`katex_render` error / `katex_skipped` info — **reuses** `scripts/validate_math.js`
  via `pipeline.math_validator.validate`, degrades gracefully when Node/KaTeX is
  missing), and `missing_section` (normalized, order not enforced). Fenced code +
  inline code are excluded; input is never mutated; no HTML/`dangerouslySetInnerHTML`.
  **NOT wired into jobs / artifacts / API / frontend / `validation.json`**;
  `math_validator.py` is reused unchanged and `math_verifier.py` is untouched; **no
  new dependency**. Tests `test_scripts/test_guide_lint.py` (64/64) + fixtures under
  `test_scripts/fixtures/guide_lint/`; build, `npm test`, `compileall`,
  `test_math_verifier` (74/74), diff check, and `smoke_release.py` (28/0/0) all
  green. Optional CLI: `python -m pipeline.guide_lint <file>`.
- **Slice 18 result (pure core only):** added `pipeline/math_verifier.py`, a safe,
  deterministic numeric-correctness verifier (`verify_math_claims(text, *,
  source_name=None)` → JSON-serializable report with per-claim `ok` / `mismatch` /
  `unparseable`). Conservative Tier-A, line-based extraction of `expression
  <relation> number` claims (`=`, `≈`, `~=`, `->`, `→`); skips fenced/inline code;
  unwraps `$…$` / `$$…$$` / `\(…\)` / `\[…\]`; small safe normalizer (unicode minus,
  `×·\times\cdot`→`*`, `÷`→`/`, `^`→`**`, `√`/`\sqrt`/`\frac`, `π`, `e`/`exp`).
  Evaluation is a stdlib `ast`-walk whitelist (no `eval`, no attribute access, no
  names beyond `pi`/`e`/`tau`, bounded length/tokens/nodes/exponent) — every
  verifier error downgrades to `unparseable`, never `mismatch`. **NOT wired into
  jobs / artifacts / API / frontend / `validation.json`** — it is **separate from
  `math_validator.py`** (which validates KaTeX rendering, not numeric values).
  **No new dependency** — SymPy is installed in the host env but unused/not added;
  a stdlib AST evaluator is safer and dependency-free. Tests
  `test_scripts/test_math_verifier.py` (74/74) + fixtures under
  `test_scripts/fixtures/math_verifier/`; build, `npm test`, `compileall`, diff
  check, and `smoke_release.py` (28/0/0) all green. Optional CLI:
  `python -m pipeline.math_verifier <file>`.
- **Slice 17 result:** carried out the dead-code sweep Slice 16 had deferred —
  `git rm` of the proven-unreachable mockup/legacy presentational set (`BrandMark`,
  `Chip`, `ClaudeIcons`, `DesktopMockup`, `FallbackImage`, `Field`, `GlowBackground`,
  `ImplementationNote`, `MobileScreenPicker`, `PasteGenerationPanel`, `PhoneMockup`,
  `StatCard`, `TopBar`, `data/mockups.js`, the 5 `public/mockups/*.png`, and the
  obsolete `verify-assets.mjs`); repaired `npm test` to chain the 9 maintained
  harnesses; updated the `App.jsx` comment and the deep report. Live render path
  stays clean — **0 undefined `sg-*`**; the only old-palette tokens left (2 lines in
  `RecentJobsPanel.jsx`) are inside the **unreachable** non-embedded `PreviewPanel`
  branch (sole caller `HomeShortcuts` always passes `embedded`), intentionally left
  rather than churned in a hygiene slice. Build, full `npm test` (9 harnesses),
  `compileall`, and `smoke_release.py` (28/0/0) all green; container confirmed
  serving the post-deletion build (deleted mockup PNG → 404, SPA → 200); security
  scan clean (no keys/tokens/socket/paths in any served API or the JS bundle).
  **Frontend + docs only; no behaviour/endpoint/payload/data changes, no new deps.**
- **`npm test` is now a real release check** — the former stale `verify-assets`
  mockup harness is gone; `npm test` chains the maintained shortcut/local-model/
  ask/style-compare harnesses, so its failures are now release-relevant. (The old
  "treat `npm test` failures as pre-existing" caveat no longer applies.)
- **Screenshots / visual review are operator-owned** — Claude Code does not produce
  them; the operator does visual inspection and supplies screenshots if needed.
- **NEXT (immediate, in order):** (1) persist `guide_lint.json` advisory artifact —
  the guide linter (Slice 19) is still a pure core; the next slice surfaces it as an
  advisory per-job artifact mirroring Slice 21's `math_verification.json` (advisory
  only; the linter may **never** make guide generation fail). Then (2) JobDetails
  guide-lint UI (read-only, mirroring Slice 22), then (3) eval golden corpus /
  baseline, then (4) true Anki `.apkg` export core. The math verifier (Slice 18) is
  already surfaced via Slice 21 (`math_verification.json`) + Slice 22 (JobDetails
  Verification tab). LMM Phase 2 remains **paused** — resume only with a separately
  designed approve-root or packaging slice; app-suggested settings remain deferred.

## What just landed
- **Slice 22 — JobDetails math verification artifact UI** (committed on
  `chrome-renderer-v1` as `b932667`). Note: Slices 23A–25B landed after this entry
  was written; see the committed slice sequence under **Current position** for the
  true most-recent work. Added
  `frontend/src/mathVerification.js`, `frontend/src/components/MathVerificationPanel.jsx`,
  a generic read-only `getJobArtifact()` helper, a `Verification` JobDetails tab,
  compact semantic CSS for claim rows, and
  `frontend/scripts/verify-math-verification.mjs` wired into `npm test`.
  UI fetches `math_verification.json` only when the tab is opened and handles
  completed, skipped, missing/404, malformed/unexpected, invalid JSON, and
  fetch/network error states. Read-only only: no rerun verifier action, no job
  mutation, no artifact writes, and no backend/pipeline behavior changes.
  Validation green: build, full `npm test`, helper harness, `compileall`,
  math-verifier tests, guide-lint tests, eval-harness tests, offline eval all,
  `git diff --check`, and `smoke_release.py` (29/0/0).
- **Slice 17 — hygiene checkpoint: dead-file sweep + `npm test` repair** (this
  branch, `chrome-renderer-v1`, PENDING REVIEW). Deleted the proven-unreachable
  mockup/legacy presentational set + 5 mockup PNGs + obsolete `verify-assets.mjs`
  via `git rm`; rewired `npm test` from the stale single mockup harness to the 9
  maintained harnesses; updated the `App.jsx` comment and the deep report's §6
  component/harness lists. Build + full `npm test` + `compileall` + `git diff
  --check` + `smoke_release.py` (28/0/0) green; container serving the post-deletion
  build; 0 undefined `sg-*`; only-remaining old-palette is in the unreachable
  `PreviewPanel` branch (left, not churned); security scan clean. **Frontend +
  docs only; no behaviour/endpoint/payload/data changes, no new deps.** See
  `CURRENT_TASK.md` for the per-audit detail.
- **Slice 16 — post-reskin release audit + checkpoint** (this branch,
  `chrome-renderer-v1`). Full validation pass after Slices 1–15: build + 4 pure
  frontend harnesses + `compileall` + Docker build/up + `smoke_release.py`
  (28 passed / 0 failed / 0 skipped) all green. Semantic-CSS audit (773 defined
  `.sg-*`, 0 undefined in the live path), inert-utility/old-palette audit (live
  path clean after a 1-file surgical strip of inert tokens in
  `RecentJobsPanel.jsx`; dead-branch/dead-file leftovers reported, not churned),
  and a security quick-scan (no raw secrets in `/api/options`, `/api/styles`,
  `/api/provider-settings`, `/api/local-model/status`, JobDetails, or the served
  bundle). **Frontend-only, 1 file changed, no behaviour/endpoint/payload/data
  changes.** See `CURRENT_TASK.md` for the per-audit detail. Status: awaiting
  review before commit.
- **Local Model Manager Phase 2G11 — final hardening/regression pass** (branch
  `lmm-phase2g11-final-hardening`). Added the pure/offline final harness
  `test_scripts/test_lmm_phase2_final_regression.py`. It validates the
- **Local Model Manager Phase 2G11 — final hardening/regression pass** (branch
  `lmm-phase2g11-final-hardening`). Added the pure/offline final harness
  `test_scripts/test_lmm_phase2_final_regression.py`. It validates the
  runtime-service examples and placeholders, example JSON parsing, `.ini` preset
  parsing through the companion loader, safe Compose/systemd template boundaries,
  backend/server/profile DTO redaction, CPU-safe/balanced/low-memory manual
  defaults, risky-only `gpu_layers=999` scope, no LMM Provider Settings writes,
  no Ask coupling, no direct frontend companion calls, no production Compose
  companion mount/env, companion-config-only approved roots, no browser folder
  picker, and safe selected-model persistence. No production backend behavior,
  frontend UI, Ask, Provider Settings, Docker Compose, installer/autostart,
  model download, or settings-recommendation behavior changed. **The current
  safe LMM Phase 2 milestone is complete/paused after 2G11.** Real validation
  facts remain: CPU-safe validation passed with `/usr/bin/llama-server`,
  `LMM_REAL_MODEL_ROOT=/mnt/ai/llm-models`,
  `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`, `port=18080`, `ctx_size=4096`,
  `gpu_layers=0`, and `threads=8`; full offload `gpu_layers=999` failed safely
  with CUDA OOM / `model_may_be_too_large` on the 26B model and is not a
  default. Deferred: approve-root flow design/implementation, app-suggested
  settings/recommendations, Ollama/simple-local-model path, Windows/macOS
  support/packaging, and model downloads.
- **Local Model Manager Phase 2G10 — companion runtime-service/operator
  packaging docs** (branch `lmm-phase2g10-runtime-service-docs`). Added
  `docs/LOCAL_MODEL_MANAGER_RUNTIME_SERVICE.md` plus safe templates under
  `docs/examples/`: companion JSON config, `.ini` profile presets, a systemd
  user-service example, and a temporary Docker Compose override example. The
  guide is Linux-first and covers operator-owned config/runtime/log/model-root
  paths, token generation and non-commit rules, manual companion startup and
  `/health`/`/profiles`/`/models/scan` checks, Docker socket-directory mounting,
  user-service enable/status/log/stop commands, the Phase 2G8 real-profile E2E
  validation env, troubleshooting, and a security checklist. Templates use
  placeholders only (`/mnt/ai/llm-models`, `/usr/bin/llama-server`,
  `replace-with-local-token`) and avoid whole-home mounts, Docker socket,
  privileged mode, host PID namespace, host networking, host-gateway TCP, and
  committed secrets. Scope preserved: docs/templates only; no production
  backend behavior changes, frontend UI changes, Ask changes, Provider Settings
  writes, permanent Docker Compose changes, app-installed service, actual
  installer, model download manager, or app-suggested settings.
- **Local Model Manager Phase 2G9 — approved-folder setup UX + safe manual
  helper defaults** (branch `lmm-phase2g9-runtime-setup-polish`). Manual command
  helper defaults are now CPU-safe first (`-c 4096 -ngl 0 --threads 8`), with
  GPU balanced (`-c 4096 -ngl 20 --threads 8`) and low-memory
  (`-c 2048 -ngl 0 --threads 8`) presets. Full offload `-ngl 999` remains only
  as an advanced profile labeled risky / may OOM and is not default. The Local
  Models UI now explains that approved GGUF folders come from host companion
  config, the web app cannot safely browse the whole PC or pick host folders
  directly, operators must configure `approved_roots`, restart the companion,
  then scan, and manual server mode still works without the companion. The setup
  template uses placeholder values only. Saved-selection copy distinguishes an
  unconfigured companion (saved model from a previous validation/session, not
  confirmed by live scan) from a configured scan where the file is missing.
  Companion/backend library payloads may include path-free root summaries
  (`id`, `recursive`, `model_count`), which the UI displays without root paths.
  Managed Server copy now states controls require a configured host companion,
  affect only companion-managed processes, do not stop manual servers, and do
  not change Provider Settings; missing profiles point to companion config or
  preset files. Scope preserved: no true browser folder picker, no companion
  config writes, no frontend-provided host path, no Provider Settings writes, no
  Ask changes, no permanent Docker changes, no model download manager, no
  app-suggested settings, no browser storage, no token/socket/absolute host
  path/raw argv exposure, no free-form flags UI, and no whole-PC scan.
- **Local Model Manager Phase 2G8 — real configured-profile E2E validation**
  (branch `lmm-phase2g8-real-profile-e2e-validation`). Added
  `test_scripts/validate_lmm_real_profile_e2e.py`, a live/manual harness for
  the actual configured-profile path: temporary explicit companion config,
  temporary companion runtime/socket, host companion, temporary Compose override
  mounting only that runtime/socket directory into the Docker app, and backend
  calls through `http://127.0.0.1:8000`. The harness requires explicit
  `LMM_REAL_LLAMA_SERVER_BIN`, `LMM_REAL_MODEL_ROOT`, model id/pattern,
  `LMM_REAL_PORT`, `LMM_REAL_CTX_SIZE`, `LMM_REAL_GPU_LAYERS`, and
  `LMM_REAL_THREADS`; missing env exits 0 with a clear skip before Docker work.
  It calls companion status, library scan, server profiles, library selection,
  server start, server status polling, server stop, verifies port release, and
  checks redaction/root-relative paths. It skips `/api/local-model/status`
  rather than writing Provider Settings to repoint the local provider, snapshots
  and restores the app-side local-model selection file, and restores/stops Docker
  with committed Compose only. Operator-run real E2E passed with
  `/usr/bin/llama-server`, `LMM_REAL_MODEL_ROOT=/mnt/ai/llm-models`,
  `LMM_REAL_MODEL_PATTERN=gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`,
  `LMM_REAL_PORT=18080`, `LMM_REAL_CTX_SIZE=4096`,
  `LMM_REAL_GPU_LAYERS=0`, and `LMM_REAL_THREADS=8`: the backend/companion path
  selected the real profile/model, reached `running` readiness via `/v1/models`,
  stopped cleanly, and released the port. Redaction passed: no token, socket
  path, absolute model root/executable path, Authorization header, full URL, or
  raw argv in backend responses; model paths were root-relative only. GPU
  validation remains separate: the earlier `gpu_layers=999` run failed safely as
  `model_may_be_too_large` / CUDA OOM and is not a passed GPU validation. Scope
  preserved: no Provider Settings writes, Ask changes, permanent Docker changes,
  host-gateway TCP, Docker socket, privileged container, host PID namespace,
  model download manager, direct companion frontend call, or settings
  recommendations.
- **Local Model Manager Phase 2G7 — operator setup docs + safe preset import**
  (branch `lmm-phase2g7-profile-presets-docs`). Added
  `docs/LOCAL_MODEL_MANAGER_OPERATOR_SETUP.md`, a Linux-first setup guide for
  finding `llama-server`, choosing approved model roots, companion JSON config,
  safe CPU / low-memory GPU / balanced GPU profile examples, Unix socket Docker
  mount concept, backend env vars (`LMM_COMPANION_SOCKET`,
  `LMM_COMPANION_TOKEN`, `LMM_COMPANION_TIMEOUT_SECONDS`), the real validation
  harness, troubleshooting, and platform scope. Implemented optional `.ini`
  profile-default import in `tools/local_model_companion/config.py` using stdlib
  `configparser` with interpolation disabled. Preset file paths are explicit
  companion JSON only via `profile_preset_files`; imported presets require
  `llama_server_executable` in JSON and cannot supply executable paths. Imported
  sections become normal `llama_server` profiles through the same whitelist path
  used by JSON profiles. Unknown keys are rejected; duplicate ids, `DEFAULT`
  values, invalid ints/bools/enums/ranges, env expansion, shell/path-like text,
  and command/args/shell/model_path/executable/free-form flag keys are rejected.
  CPU safe and GPU balanced preset defaults avoid `gpu_layers=999`; the Phase
  2G5 record remains CPU validation passed, full offload `gpu_layers=999`
  failed safely as `model_may_be_too_large` / CUDA OOM. Scope preserved: no
  app-suggested settings, Provider Settings writes, Ask changes, permanent
  Docker Compose changes, frontend UI changes, free-form flags, raw shell
  command execution, model downloads, host-gateway TCP, Docker socket,
  privileged container, host PID namespace, or token/socket/absolute path/raw
  argv exposure.
- **Local Model Manager Phase 2G6 — real-profile UI/defaults + safe parameter
  controls** (branch `lmm-phase2g6-real-profile-controls`). Added companion
  `GET /profiles` and backend `GET /api/local-model/server/profiles` safe DTOs.
  Profile metadata exposes only ids, display names/descriptions, real/test
  marker, runnable boolean/reason, configured defaults, typed schema, and
  warnings; it never exposes executable paths, model paths, token/socket details,
  raw argv, or a companion config dump. Companion JSON profiles now support
  arbitrary safe `llama_server` ids such as `cpu_safe`/`gpu_balanced`,
  `display_name`, `description`, `warnings`, `default_parameters`, and optional
  `parameter_schema`. Missing/non-executable configured profiles remain visible
  as `runnable:false` with safe reasons like `executable_missing`.
  Start/restart payloads remain `{model_id, profile_id, parameters}` only.
  Backend rejects unknown top-level fields and unknown parameter names before
  forwarding; companion validates against the selected profile schema. Supported
  whitelist parameters are `port`, `ctx_size`, `gpu_layers`, `threads`,
  `parallel`, `cache_type_k`, `cache_type_v`, `flash_attention`, and `mmap`;
  argv mapping is centralized and no free-form flags/args/command/model_path/
  executable fields are accepted. The Local Models Managed Server UI now fetches
  profiles from the backend, picks the safest runnable profile in memory
  (`cpu_safe`, then first runnable non-test, then `fake_test`), renders typed
  number/checkbox/select controls from the selected schema, builds safe payloads
  only, and has a **Use profile defaults** reset. UI copy states high GPU layers
  can OOM, CPU is safer but slower, Provider Settings are not changed, and the
  controls affect only the companion-managed server. Manual command helper
  fallback remains. `.ini` preset import was deferred in G6 and implemented in
  G7 through the same whitelist schema; app-suggested settings remain deferred.
  Scope preserved: no
  Provider Settings writes, Ask changes, permanent Docker Compose changes,
  browser storage, direct companion frontend calls, token/socket/path/raw argv
  exposure, host-gateway TCP, Docker socket, privileged container, host PID
  namespace, model download manager, or Windows/macOS support.
- **Local Model Manager Phase 2G5 — real Linux llama-server validation and
  lifecycle hardening** (branch `lmm-phase2g5-real-llama-validation`). Companion/
  backend hardening plus validation harness. Added explicit-config real profiles
  `llama_cpp_gpu_default` / `llama_server_gpu_default`; no default real
  executable exists. Executable path comes only from companion config, is
  canonicalized, and must be executable. Model path resolves only from approved
  scanned model id. Requests still accept only whitelisted `profile_id`,
  `model_id`, and typed bounded params (`port`, `ctx_size`, `gpu_layers`,
  `threads`); no shell/free-form args/model_path/executable request fields.
  Real argv is centralized as
  `<exe> -m <model> --host <configured-safe-host> --port <port> -c <ctx_size>
  -ngl <gpu_layers> --threads <threads>`.
  Lifecycle now persists `starting` after spawn, promotes to `running` only after
  host-side `GET http://127.0.0.1:<port>/v1/models`, and records stable
  `error`/`crashed` states for failures. Launch failures do not auto-restart.
  Child stdout/stderr are captured to bounded companion-owned logs; safe
  categories include `executable_missing`, `permission_denied`, `port_in_use`,
  `model_load_failed`, `model_may_be_too_large`, `readiness_timeout`,
  `process_start_failed`, and `process_crashed`. Launch uses
  `start_new_session=True`; stop targets only a verified tracked process group
  after Linux `/proc` identity checks, and foreign/reused/uncertain PIDs are not
  killed. Backend DTOs whitelist new states/categories, and frontend copy
  displays them without adding advanced flags UI. Added
  `test_scripts/validate_lmm_real_llama_server.py`; it skips without explicit
  `LMM_REAL_LLAMA_SERVER_BIN`, `LMM_REAL_MODEL_ROOT`, and model id/pattern env,
  and when configured starts a temporary companion, scans, launches real
  `llama-server`, verifies `/v1/models`, stops, verifies port release/redaction,
  and cleans up. Operator-run real Linux `llama-server` lifecycle validation
  passed in CPU mode with `LMM_REAL_LLAMA_SERVER_BIN=/usr/bin/llama-server`,
  `LMM_REAL_MODEL_ROOT=/mnt/ai/llm-models`,
  `LMM_REAL_MODEL_PATTERN=gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`,
  `LMM_REAL_PORT=18080`, `LMM_REAL_CTX_SIZE=4096`,
  `LMM_REAL_GPU_LAYERS=0`, and `LMM_REAL_THREADS=8`: the harness launched real
  `llama-server`, reached `/v1/models`, and stopped cleanly. A full GPU/offload
  stress attempt with the same binary/model on port `8080`, `ctx_size=8192`,
  `gpu_layers=999`, and `threads=8` failed safely before readiness, was
  classified as `model_may_be_too_large`, and logs showed CUDA OOM / failed CUDA
  allocation. Do not describe high-GPU-offload validation as passed; the proven
  result is CPU-mode real lifecycle validation plus safe model-load-failure
  detection. Practical GPU defaults still need a follow-up because
  `gpu_layers=999` can be too aggressive for large models on 16GB VRAM.
  Scope preserved: no Provider Settings writes, no Ask changes, no permanent
  Docker Compose changes, no host-gateway TCP, Docker socket, privileged
  container, host PID namespace, browser storage, automatic restart loop, model
  download manager, multi-server pool, Windows/macOS process control, or
  Ollama/simple-local-model implementation.
- **Local Model Manager Phase 2G4 — Local Models managed-server UI controls**
  (branch `lmm-phase2g4-process-ui`). Frontend/client/tests/docs only. Added API
  helpers for the existing Phase 2G3 bridge:
  `getLocalModelServerStatus()` → `GET /api/local-model/server/status`,
  `startLocalModelServer(payload)` → `POST /api/local-model/server/start`,
  `stopLocalModelServer(payload)` → `POST /api/local-model/server/stop`, and
  `restartLocalModelServer(payload)` → `POST /api/local-model/server/restart`.
  The Local Models panel now has a **Managed Server** section that fetches server
  status on load, uses the saved selected library model for start/restart, keeps
  the selected-model preview visible, and keeps the manual command helper
  fallback visible. Start/restart payloads include only
  `{model_id, profile_id: "fake_test", parameters: {port: 18080, ctx_size: 2048,
  gpu_layers: 0, threads: 2}}`; stop sends only `{grace_seconds: 5}`. The
  `fake_test` profile is clearly labeled as validation/test only. Controls are
  disabled when the companion is unavailable or no saved selected model exists;
  stop/restart require a companion-managed running state. Copy states that this
  controls only the companion-managed test/server process, manual servers are not
  stopped, and Provider Settings are not changed. No backend route addition,
  Docker Compose change, Provider Settings write, Ask change, local provider
  base URL/model behavior change, direct companion frontend call, real
  `llama-server` validation, host-gateway TCP, Docker socket, privileged
  container, host PID namespace, browser storage, free-form command args UI,
  arbitrary JSON editor, `dangerouslySetInnerHTML`, token/socket/Authorization
  exposure, raw absolute path rendering, or raw argv exposure was added.
  `frontend/scripts/verify-local-model-library.mjs` now verifies process API
  helper paths/methods, safe payload shape, disabled/no-selection state, manual
  helper fallback, companion-managed-only stop copy, no Provider Settings/Ask
  calls, no browser storage/raw HTML, no token/socket/Authorization UI strings,
  no raw absolute path rendering, and managed status/error normalization.
  Validation passed: frontend local-model library/status/command checks,
  frontend build (existing Vite large-chunk warning only), requested backend/
  process suites, `python -m compileall api pipeline tools`, `git diff --check`,
  `docker compose config >/tmp/compose-check.txt` exit 0, and manual/live
  fake-companion direct-backend validation 22/22 with a temporary Compose
  override. Live validation saved a fake GGUF selection, started the `fake_test`
  profile, confirmed running status, stopped it, confirmed stopped status,
  passed redaction checks, and restored the app with committed Compose only.
- **Local Model Manager Phase 2G3 — backend process bridge** (branch
  `lmm-phase2g3-backend-process-bridge`). Added backend-only FastAPI routes
  `GET /api/local-model/server/status`, `POST /api/local-model/server/start`,
  `POST /api/local-model/server/stop`, and
  `POST /api/local-model/server/restart`. The bridge extends
  `pipeline/local_model_companion_client.py` to call companion Unix-socket
  endpoints `GET /server/status`, `POST /server/start`, `POST /server/stop`, and
  `POST /server/restart` with server-side `Authorization: Bearer <token>` from
  `LMM_COMPANION_TOKEN`, socket path from `LMM_COMPANION_SOCKET`, and optional
  `LMM_COMPANION_TIMEOUT_SECONDS`. Start forwards only `model_id`, `profile_id`,
  and typed bounded params (`port`, `ctx_size`, `gpu_layers`, `threads`); stop
  forwards only bounded `grace_seconds`; restart forwards either explicit start
  payload or `{reuse_last: true}`. Unknown top-level fields and unknown parameter
  fields are rejected as safe `bad_request` DTOs before any socket request.
  Responses are whitelisted to `ok`, `configured`, `reachable`, `state`,
  `managed`, `model_id`, `profile_id`, `port`, `started_at`, `error`, and
  bounded/redacted `log_tail`; pid, params, executable path, private model path,
  raw argv, token, socket path, Authorization, absolute host paths, full URLs,
  tracebacks, and low-level socket details are not returned. No frontend UI,
  Docker Compose change, Provider Settings write, Ask change, local provider
  base URL/model behavior change, direct host filesystem scan, direct host
  process control, host-gateway TCP, Docker socket, privileged container, host
  PID namespace, subprocess/shell execution in the backend bridge, real
  `llama-server` validation, or free-form command args were added. New focused
  test: `test_scripts/test_local_model_companion_process_bridge.py`. Validation
  passed across the requested backend/frontend suites, compileall, frontend
  build, `git diff --check`, and Compose config. Manual fake-companion live
  validation through `http://127.0.0.1:8000` passed with a temporary `/tmp`
  Compose override; the app was restored afterward with committed Compose only.
- **Local Model Manager Phase 2G2 — companion HTTP process API** (branch
  `lmm-phase2g2-companion-process-api`). Added host-companion-only Unix-socket
  endpoints `GET /server/status`, `POST /server/start`, `POST /server/stop`, and
  `POST /server/restart`, all behind the existing companion bearer token auth.
  The HTTP handlers parse bounded JSON, reject unknown top-level fields with
  `bad_request`, expose safe lifecycle categories, and delegate start/stop/status
  to the Phase 2G1 process manager. Handlers do not call `subprocess.Popen`.
  Start/restart explicit payloads accept only `model_id`, whitelisted
  `profile_id`, and typed `parameters`; stop accepts only `grace_seconds`;
  `reuse_last` restart is allowed only when prior launch metadata exists. The
  companion config may now include `process_runtime_dir` and
  `profiles.fake_test.executable`; no default real executable is configured.
  HTTP DTOs expose only `ok`, `state`, `managed`, `model_id`, `profile_id`,
  `port`, `started_at`, `error`, and bounded/redacted `log_tail`; token, socket
  path, absolute host paths, executable path, raw argv, Authorization, and full
  URLs are not returned. Tests use a temp fake executable and fake `.gguf` files
  only; this sandbox denies Unix/TCP socket creation, so the new process API test
  uses an in-memory handler fallback and monkeypatches only the test manager port
  probe. No backend FastAPI server routes, frontend start/stop UI, Docker changes,
  Provider Settings writes, Ask changes, backend bridge start/stop, real
  `llama-server` validation, host-gateway TCP, Docker socket, privileged
  container, host PID namespace, shell execution, or free-form command args were
  added.
- **Local Model Manager Phase 2G1 — companion process-control internals**
  (branch `lmm-phase2g1-companion-process-internals`). Added companion-private
  lifecycle code only: `tools/local_model_companion/profiles.py` defines typed,
  bounded launch profiles plus the explicit `fake_test` profile constructor, and
  `tools/local_model_companion/process_manager.py` defines
  `ManagedServerProcessManager`, `start_managed_server`,
  `stop_managed_server`, and `get_managed_server_status`. Start resolves selected
  model ids against approved-root GGUF records, re-canonicalizes model paths
  inside configured roots, validates profile ids and typed params, validates a
  companion/test-configured executable path, checks port availability, builds argv
  arrays only, and launches with `subprocess.Popen(..., shell=False)`. Status and
  stop use Linux `/proc` PID identity checks; stale/reused/foreign PIDs are never
  killed. Active process state is written atomically to
  `managed_server_state.json` in a companion-owned runtime dir and includes pid,
  model/root/profile ids, port, params, started_at, executable metadata,
  redacted argv metadata, private model path, status, last error, and log path; it
  stores no token. Logs go to `managed_server.log`; safe DTOs expose only bounded
  redacted tails. The focused test creates a temporary fake Python executable
  that stays alive, prints predictable output/redaction bait, handles SIGTERM, and
  is cleaned up. No FastAPI backend route, frontend UI, Docker Compose change,
  Provider Settings write, Ask change, backend bridge start/stop, companion
  `/server/start`/`stop`/`restart` HTTP endpoint, real `llama-server` launch,
  shell execution, free-form args, host-gateway TCP, Docker socket, privileged
  container, or host PID namespace was added.
- **Local Model Manager Phase 2F — start/stop design review** (branch
  `lmm-phase2f-start-stop-design`). Docs-only safety review before implementing
  any `llama-server` process control. Updated
  `docs/LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md` with the future companion API
  contract for `GET /server/status`, `POST /server/start`,
  `POST /server/stop`, and `POST /server/restart`; backend bridge targets
  `GET /api/local-model/server/status`, `POST /api/local-model/server/start`,
  `POST /api/local-model/server/stop`, and
  `POST /api/local-model/server/restart`; and the future Local Models UI
  contract. The process-control boundary is reaffirmed: Docker FastAPI never
  directly starts/stops host processes; only the host companion may spawn
  `llama-server`; the companion may stop only a tracked process it started; no
  Docker socket, privileged container, host PID namespace, or direct
  Docker-to-host spawn; Linux Docker control remains Unix-socket-first with token
  auth; frontend never receives token/socket/Authorization/raw host paths. Start
  accepts only selected `model_id`, whitelisted `profile_id`, and typed bounded
  params (`port`, `ctx_size`, `gpu_layers`, `threads`, optional `batch_size`) with
  no shell command, no free-form args, no arbitrary executable path, and no
  frontend/backend model path. Stop refuses to kill stale/reused/foreign PIDs.
  Restart requires a fresh validated start payload or `reuse_last: true` only
  when last launch metadata still validates. Added threat model, allowed states,
  whitelisted profiles (`gpu_default`, `cpu`, later `low_memory`), process state
  file rules, Linux `/proc` stale-PID checks, port conflict handling, bounded and
  redacted logs, host-side health checks, backend/UI safety rules, future tests,
  rollout slices Phase 2G1-G5, and a lasting `DECISIONS.md` entry. No code,
  companion implementation, backend endpoint, frontend UI, Docker change,
  Provider Settings write, Ask change, dependency, subprocess launch, or
  `llama-server` start/stop/restart implementation was added. Validation:
  `python -m compileall api pipeline tools`, `git diff --check`, and docs-only
  `git diff --name-only`.
- **Local Model Manager Phase 2E — selected library model handoff** (branch
  `lmm-phase2e-selected-model-handoff`). Backend/frontend/docs/tests slice. Added
  app-side persistence for a chosen discovered GGUF model without starting
  anything. New backend endpoints:
  `GET /api/local-model/library/selection`,
  `POST /api/local-model/library/selection`, and
  `DELETE /api/local-model/library/selection`. Storage is
  `config/local_model_library_selection.json` with schema
  `{version: 1, selected: null | safe_model}`; only safe selected-model metadata is
  stored: `id`, `display_name`, `filename`, root-relative `relative_path`,
  `root_id`, `size_bytes`, `modified_at`, `family_hint`, `quant_hint`,
  `server_compatible`, and `selected_at`. Writes are atomic temp-file +
  `os.replace`. POST prefers validating `model_id` against the cached companion
  library when available and otherwise accepts a sanitized safe snapshot. Absolute
  `relative_path` values are dropped; unknown fields are dropped; path/token/auth/
  full-URL-like strings are redacted. `GET /api/local-model/command-profile` now
  also includes `selected_library_model` and a non-runnable
  `future_launch_preview` (`model_id`, filename, root-relative path, root id,
  `gpu_default` profile placeholder, companion-model-id resolver). The Local
  Models panel fetches saved selection on load, lets a clicked model be persisted
  via **Remember selected model**, shows the saved **Chosen library model**, marks
  saved selections stale when absent from the current library, shows **Clear
  selection**, and keeps the existing manual command helper available. No Provider
  Settings write, Ask change, Docker change, local provider base URL/model change,
  browser storage, raw companion token/socket/Authorization exposure, absolute
  host path exposure, start/stop/restart route/UI, subprocess/shell execution, or
  `llama-server` process launch was added. Validation passed: new backend
  selection 14/14, companion bridge 14/14 (FastAPI route inspection skipped in host
  Python), companion scan 21/21, local-model status 17/17, command profile 13/13,
  compileall, frontend local-model library/status/command checks, and frontend
  build with the existing Vite large-chunk warning only.
- **Local Model Manager Phase 2D — Local Models UI model-library picker** (branch
  `lmm-phase2d-model-library-ui`). Frontend/client/tests/docs only. Added a compact
  **Model Library** section inside the existing Local Models panel. New frontend
  API helpers: `getLocalModelCompanionStatus()` →
  `GET /api/local-model/companion/status`, `getLocalModelLibrary()` →
  `GET /api/local-model/library`, and `scanLocalModelLibrary()` →
  `POST /api/local-model/library/scan`. The panel fetches companion status and
  cached library on open, shows safe states for unconfigured/offline/auth
  failed/reachable/endpoint-unavailable/no-roots/no-models/warnings, and renders
  discovered GGUF models using only whitelisted fields: `display_name`, `filename`,
  `relative_path`, `root_id`, formatted `size_bytes`, formatted `modified_at`,
  `family_hint`, `quant_hint`, and `server_compatible`. Clicking a model only sets
  React UI state for visual selection; it does not write Provider Settings, change
  the default local model/base URL, persist to browser storage, affect Ask, or run
  any process. Existing Phase 1 manual command helper remains visible/usable when
  companion discovery is unavailable. No backend endpoint, Docker change,
  dependency, token/socket/Authorization exposure, absolute host path rendering,
  `dangerouslySetInnerHTML`, localStorage/sessionStorage, start/stop/restart route,
  or `llama-server` process control was added. Added pure helper
  `frontend/src/localModelLibrary.js` and verifier
  `frontend/scripts/verify-local-model-library.mjs` wired as
  `npm --prefix frontend run test:local-model-library`.
- **Local Model Manager Phase 2C socket-mount validation harness** (branch
  `lmm-phase2c-socket-mount-validation`). Added
  `test_scripts/validate_lmm_companion_socket_mount.py`, a manual/live validation
  harness for the deployed Docker app container reaching a host companion through
  a mounted Unix domain socket. The harness creates a temporary `/tmp`
  validation workspace, fake approved model root, fake `.gguf` files plus one
  non-GGUF file, explicit companion config, and a temporary Compose override. The
  override mounts only the temp runtime directory into service `app` and sets
  server-side `LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`, and
  `LMM_COMPANION_TIMEOUT_SECONDS`; it is removed during cleanup and no committed
  Compose or `.env` file is changed. It starts the host companion with
  `python -m tools.local_model_companion.companion --config <config> serve
  --socket <socket>`, waits for companion `/health`, starts/restores the Docker
  app through Compose, waits for `http://127.0.0.1:8000/api/health`, then calls
  `GET /api/local-model/companion/status`, `GET /api/local-model/library`,
  `POST /api/local-model/library/scan`, and `GET /api/local-model/library`. It
  asserts configured/reachable status, `scan` capability, safe pre-scan library,
  fake GGUF models returned, non-GGUF excluded, root-relative `relative_path`, and
  no token/socket/temp absolute host path leaks in backend responses. It also
  asserts `POST /api/local-model/server/start`, `/stop`, and `/restart` are
  unavailable. No frontend UI, production Docker Compose change, Provider
  Settings write, Ask change, host-gateway TCP, Docker socket, privileged
  container, host PID namespace, `llama-server` launch, or model process control
  was added. Live validation passed 17/17: status configured/reachable with
  `scan`, pre-scan library safe/empty, scan returned two fake GGUF models and
  excluded `notes.txt`, post-scan cache returned both models, redaction checks
  passed, process-control probes were unavailable (`405`), and the app service was
  restored healthy with committed Compose only.
- **Local Model Manager Phase 2C — read-only backend bridge to the host companion
  model library** (branch `lmm-phase2c-backend-companion-bridge`). Added
  `pipeline/local_model_companion_client.py`, wired `api/server.py`, and added
  `test_scripts/test_local_model_companion_bridge.py`. New backend endpoints:
  `GET /api/local-model/companion/status`, `GET /api/local-model/library`, and
  `POST /api/local-model/library/scan`. Config is server-side env only:
  `LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`, optional
  `LMM_COMPANION_TIMEOUT_SECONDS`. The bridge is a small stdlib Unix-socket HTTP
  client that sends `Authorization: Bearer <token>`, parses JSON with bounded
  timeout/body size, and normalizes failures to safe categories:
  `companion_config`, `companion_offline`, `companion_auth`,
  `companion_timeout`, `companion_error`. It whitelists model records to safe
  fields only, rejects absolute `relative_path` values, redacts tokens/auth text,
  raw socket paths, URLs, and absolute paths from responses/warnings, bounds
  warnings, and never exposes the raw token or socket path. `GET /library` reads
  cached companion models only; `POST /library/scan` delegates scanning to the
  companion. No frontend UI, Docker Compose mount, Provider Settings write, Ask
  change, local provider base-URL change, host-gateway TCP, direct host filesystem
  scan, process control, model launch, start/stop/restart route, shell execution,
  subprocess usage in the bridge, or new dependency was added. Validation passed:
  companion bridge 14/14 (FastAPI route introspection skipped in host Python
  because FastAPI is unavailable), companion scan 21/21 with the known sandbox
  AF_UNIX bind skip, local-model status 17/17, command profile 13/13, compileall,
  frontend local-model status/command checks, frontend build with the existing Vite
  large-chunk warning only, `git diff --check`, and Compose config exit 0.
- **Local Model Manager Phase 2B — companion approved-folder GGUF scanning
  prototype** (branch `lmm-phase2b-companion-scan`). Added stdlib-only host
  companion code under `tools/local_model_companion/`: explicit config loading,
  bounded approved-root `.gguf` scanner, safe model metadata, CLI, and a minimal
  Unix-domain-socket HTTP API. Config shape:
  `{"approved_roots":[{"id":"default","path":"/home/user/models","recursive":true}],"token":"optional-local-companion-token"}`.
  The config path must be supplied via `--config` or `LMM_COMPANION_CONFIG`; no
  default home scan, no implicit `~/models`, and no silent approved-root creation.
  Missing config returns no models plus a bounded `no_approved_roots` warning. The
  scanner canonicalizes roots/candidates, accepts `.gguf` case-insensitively,
  resolves symlink files and requires the resolved target to remain inside the
  approved root, rejects symlink escapes/traversal, skips symlinked directories,
  supports optional recursion, bounds files/models/time/warnings, and returns only
  safe records with stable opaque ids, root-relative paths, size, modified time,
  family/quant hints, and `server_compatible: true`. Implemented socket endpoints:
  `GET /health`, `GET /models` cached read, `POST /models/scan` explicit scan, all
  requiring `Authorization: Bearer <token>` from `LMM_COMPANION_TOKEN` or config.
  No backend bridge, frontend UI, Docker change, Provider Settings change, Ask
  change, dependency, model execution, whole-PC/home scan, arbitrary host path scan,
  shell execution, subprocess use, or `llama-server` process control was added.
  Focused test `python test_scripts/test_local_model_companion_scan.py` passed
  21/21; the sandbox denies AF_UNIX bind, so the socket runtime bind section is
  reported as implementation-shape checked/skipped by sandbox.
- **Local Model Manager Phase 2A — host companion + approved GGUF model library
  DESIGN** (branch `lmm-phase2-host-companion-design`). New doc:
  `docs/LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md`; reconciled
  `CURRENT_TASK.md`, `PROJECT_CONTEXT.md`, `LOCAL_MODEL_MANAGER_DESIGN.md`, and
  `DECISIONS.md`. The future architecture is React UI → Docker FastAPI backend →
  Unix-socket-first token-authenticated host companion → approved model directory
  scan → host `llama-server` process lifecycle. For Linux Docker, Phase 2B assumes
  a Unix domain socket mounted into the backend container; a host `127.0.0.1`-only
  companion is not assumed reachable from Docker. Host-gateway TCP is only an
  explicit alternative with operator sign-off, Docker-bridge firewall restriction,
  and token auth. Host networking/native packaging can use loopback, but is not the
  default Docker design. The React UI never talks directly to the companion; the
  backend reads the companion token/connection config server-side only and redacts
  host paths; Provider Settings remains the config writer unless a later accepted
  design deliberately changes that. Model scanning is explicit and limited to one
  or more user-approved roots, with canonicalized paths, safe symlink policy,
  `.gguf` only, and no whole-PC/home-default scan. Start requests use a model id
  plus whitelisted profile id and typed parameters only; no free-form args or shell
  strings. The companion may stop only the tracked process it started. If the
  companion is absent, the UI should fall back to the Phase 1 manual command helper.
  `llama-server` may still bind `--host 0.0.0.0` for the model `/v1` API so Docker
  can reach it; that is separate from the companion control API, which must never
  be public. **No
  companion implementation, backend endpoint, frontend UI, Docker change, process
  spawn, model scanning implementation, Provider Settings change, Ask behavior
  change, upload, dependency, or code edit was made.**
- **Compatibility fix — Ask local direct-answer guard** (branch
  `ask-local-direct-answer-guard`). Manual local llama-server testing with
  `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf` showed `/v1/chat/completions` can return HTTP
  200 with `choices[0].message.content == ""`, visible reasoning only in
  `reasoning_content`, and `finish_reason == "length"` unless explicitly instructed
  to put the answer in normal assistant content. The system-only guard helped tiny
  prompts but failed in the full Ask prompt, while adding `/no_think` in the
  model-facing user message produced visible content. `pipeline/ask_sessions.py`
  now keeps the concise direct-answer system rules and also inserts a standalone
  `/no_think` local thinking-model control immediately before the final `User
  question:` block assembled for `generate_chat_completion`. The marker is not user
  content: it is never appended to `history.jsonl`, returned by session load/list
  endpoints, included in session summaries, or rendered by the frontend. Citation
  and grounding rules are unchanged. `test_scripts/test_ask_local_chat.py` asserts
  the marker is present in model prompts, absent from stored/frontend-visible
  messages and summaries, citation rules remain present, empty-response handling
  still works, successful answers still work, and raw prompts/chunk text/secrets/full
  URLs/paths stay hidden. Verified: Ask local chat 45/45 pure checks passed with
  endpoint skip because FastAPI is unavailable in the host Python; inventory 11/11
  and prepare 28/28 passed with the same endpoint skips; `python -m compileall api
  pipeline`, frontend Ask checks, frontend build, and release smoke all passed;
  `docker compose config >/tmp/compose-check.txt` exit 0. Docker app was
  rebuilt/restarted healthy. Live Ask against reachable local Gemma returned
  `status: answered` with visible assistant content instead of
  `provider_empty_response`; session load/list/history did not expose `/no_think`.
  Headless Chromium verified the rebuilt browser shell is served; full browser
  click/send replay was not automated in this repo.
- **Bugfix — Ask empty local-model response guard** (branch
  `ask-empty-response-guard`). During manual Ask UI validation after the
  math/source polish slice, a browser Ask message returned
  `POST /api/ask/sessions/{session_id}/message` → 500. The traceback showed
  `generate_chat_completion` raised
  `RuntimeError("LLM returned an empty response.")`; Ask did not catch it, so
  FastAPI returned raw 500 text. `pipeline/ask_sessions.py` now catches that narrow
  empty local-model RuntimeError response case and returns a safe structured
  `provider_error` response with `error.category: provider_empty_response` and a
  retryable user-safe message. The failed turn does not append a successful
  user/assistant message to history. Local-only behavior is unchanged: no retrieval,
  prompt assembly, model fallback, citation validation, session management,
  clear/delete, provider settings, streaming, uploads, rolling summary, multimodal,
  or process-control behavior changed. `test_scripts/test_ask_local_chat.py` has
  focused coverage. Verified: `python test_scripts/test_ask_local_chat.py` 38/38
  passed with endpoint section skipped because plain Python lacks FastAPI; inventory
  11/11 and prepare 28/28 passed with endpoint skips for missing FastAPI;
  `.venv/bin/python -m compileall api pipeline` passed; `npm --prefix frontend run
  test:ask-guide` passed; `npm --prefix frontend run build` passed; `docker compose
  config >/tmp/compose-check.txt` exit 0; `.venv/bin/python
  test_scripts/smoke_release.py` ran 27/28 with one existing-looking non-Ask
  outline-ordering failure. Docker app was rebuilt/restarted and healthy. The
  original empty local-model behavior was not reproducible, but the simulated
  regression is now covered.
- **Ask Your Guide — chat math/source visual polish** (branch
  `ask-chat-math-source-polish`). Frontend-only polish in
  `frontend/src/askGuide.js`, `frontend/src/components/AskGuideWorkspace.jsx`, and
  `frontend/scripts/verify-ask-guide.mjs`. Added inert math-aware answer parsing for
  `$$...$$`, `\[...\]`, `\(...\)`, and escaped-dollar inline math. Display math now
  renders as readable monospace blocks preserving line breaks; inline math renders as
  small monospace chips. No `dangerouslySetInnerHTML`, no markdown dependency, no
  KaTeX/MathJax, and no new dependency. Trusted backend-used citations now appear in
  a clearer **Sources used** section; unsupported citations remain warning-only and
  are not trusted chips. Retrieved chunk metadata stays collapsed and shows cleaner
  label/type/page/score/token rows; chunk text is still never rendered. Local-only
  Ask behavior and session management are unchanged: no backend retrieval, prompt
  assembly, model-call, citation-validation, session, clear/delete, or lazy session
  creation logic changed. **No extra uploads, streaming, hosted/cloud Ask mode,
  DeepSeek/Qwen fallback, rolling summary, multimodal, local model process control,
  provider settings writes, browser storage, or new dependency.** Validation: root
  `npm run test:ask-guide` failed because the root package has no such script;
  `frontend` `npm run test:ask-guide` passed; `frontend` `npm run build` passed with
  the existing Vite chunk-size warning; `frontend` local-model command/status checks
  passed; `python -m compileall api pipeline` passed; Ask local-chat, inventory, and
  prepare scripts passed pure checks with host endpoint sections skipped because
  FastAPI is unavailable; release smoke passed **28/28**; compose config exit 0.
  Manual UI validation after this slice found the empty local-model response guard
  bug recorded above; keep any further manual Ask polish narrow and bug-driven.
- **Ask Your Guide — session management UI/API** (branch `ask-session-management`).
  Adds `GET /api/ask/jobs/{job_id}/sessions`,
  `DELETE /api/ask/sessions/{session_id}/history`, and
  `DELETE /api/ask/sessions/{session_id}`. Session listing returns safe summaries
  only: id/job/title, created/updated times, cheap message count, and a redacted
  bounded last-message snippet. Clear history empties `history.jsonl`, keeps the
  session id/metadata and prepared context cache, and updates metadata. Delete removes
  only the fenced session directory under the parent job and never touches guide,
  source, manifest, other sessions, or `ask/cache`. The Ask workspace now lists chats
  for the selected guide in a compact rail panel, can switch sessions, start a new
  chat without re-preparing context, clear the active chat, and delete the active
  session while selecting the next newest session when available. Lazy session creation
  on first send still works. **No extra uploads, chat export, streaming, cloud
  fallback, hosted selector, DeepSeek/Qwen fallback, rolling summary, multimodal,
  process control, provider settings writes, browser storage, or new dependency.**
  Verified: `npm run test:ask-guide`, `npm run build`, `python
  test_scripts/test_ask_local_chat.py` pure checks, Ask inventory/prepare pure checks,
  `python -m compileall api pipeline`, local-model frontend checks, release smoke
  28/28, and compose config exit 0. Host endpoint portions skipped because FastAPI is
  not installed; the running Docker image was healthy but did not include
  `test_scripts/`.
- **Ask Your Guide — chat polish + emitted-citation validation** (branch
  `ask-chat-polish-citations`). The local-only Ask message endpoint now validates
  bracket-style citations emitted by the model against the exact citation labels
  retrieved for the turn. Unsupported Ask-looking citations are stripped from the
  returned/stored answer and reported via `citations_unsupported` +
  `citation_validation`; normal bracketed prose is preserved. Responses also include
  `citations_allowed` and `citations_used`, with trusted `citations` mirroring used
  citations. The prompt still requires grounding/exact labels but now asks for fewer,
  clearer citations at paragraph ends or in a short sources line. Frontend polish:
  safe attachment-summary formatting fixes `Guide only · [object Object]`, full
  `ask_...` session ids are hidden behind a friendly status label, assistant answers
  render through a tiny inert heading/bold/list/preformatted subset renderer (no
  `dangerouslySetInnerHTML`, no markdown dependency), unsupported citations show a
  subtle warning and are not trusted chips, and retrieved chunk metadata is collapsed
  by default behind `Sources used` / `Show retrieved chunks`. **No chunk text, raw
  prompts, keys, full URLs, browser storage, extra uploads, streaming, cloud fallback,
  hosted selector, DeepSeek/Qwen fallback, local model process control, provider
  settings writes, or new dependency.** Verified: `npm run test:ask-guide`,
  `npm run build`, `npm run test:local-model-command`,
  `npm run test:local-model-status`, pure portions of the three Ask Python scripts on
  the host, `python -m compileall api pipeline`, and compose config exit 0. Host
  endpoint portions skipped because FastAPI is not installed; the running Docker image
  was healthy but did not include `test_scripts/`.
- **Ask Your Guide — frontend chat UI wiring (FRONTEND)** (branch `ask-chat-ui`).
  The existing `Ask Guide` workspace now consumes the backend local chat API:
  guide/context inventory and explicit prepare still use
  `GET /api/ask/jobs`, `GET /api/ask/jobs/{id}/context`, and
  `POST /api/ask/jobs/{id}/prepare`; chat uses lazy
  `POST /api/ask/jobs/{id}/sessions`, then `GET /api/ask/sessions/{session_id}`,
  then non-streaming `POST /api/ask/sessions/{session_id}/message`. The composer is
  enabled only when a guide is selected, context inventory is ready, prepare has
  succeeded, local model status is reachable, and no message is sending. It renders
  bounded history, answer text as plain text, backend-returned citation chips, safe
  retrieved chunk metadata only (id/source/page/tokens/score, **no chunk text**),
  and safe local model info. Offline/unconfigured local keeps the composer disabled
  and reuses the LMM command helper; failures keep the draft available for retry.
  Frontend normalizers redact obvious `sk-*` keys, Authorization bearer headers, full
  URLs, and host paths before storing/rendering; there is no browser storage
  persistence and no `dangerouslySetInnerHTML`. **No backend chat behavior change, no
  extra uploads, no export, no citation-validation backend slice, no rolling-summary
  UI, no streaming, no cloud fallback, no hosted selector, no DeepSeek/Qwen fallback,
  no process control, no provider writes, no dependency.** Verified:
  `npm run test:ask-guide`, `npm run build`, `npm run test:local-model-command`,
  `npm run test:local-model-status`, Ask backend regressions in Docker
  (`test_ask_context_inventory.py` 50/50, `test_ask_context_prepare.py` 58/58,
  `test_ask_local_chat.py` 40/40), release smoke 28/28, and compose config exit 0.
- **Ask Your Guide — backend local chat API (BACKEND ONLY)** (branch
  `ask-local-chat-api`). Adds `POST /api/ask/jobs/{job_id}/sessions`,
  `GET /api/ask/sessions/{session_id}`, and
  `POST /api/ask/sessions/{session_id}/message`. Sessions live under
  `jobs/<job_id>/ask/sessions/<session_id>/` with `session.json` (atomic) and
  `history.jsonl` (append-only). Unknown job → 404; guide-less job → safe
  `not_ready`; load returns safe metadata + bounded history. Message validates
  non-empty/max-length input, checks LMM/local status first, and if local is offline
  returns structured `local_offline` without model/config calls. If local is ready,
  it synchronously prepares/reuses the Slice 3 context cache, performs pure lexical
  retrieval over cached term frequencies + `doc_freq` (top 8, approx 3k-token pool,
  `chars/4`), assembles hard answer rules + citation-labelled chunks + small recent
  history, and calls only `build_provider_config("local", selected_model, ...)` +
  `generate_chat_completion`. Responses include answer text, allowed citation labels,
  safe retrieved-chunk metadata (no chunk text), session id, and safe local model
  status. **No frontend/UI changes, no extra uploads, no cloud fallback, no
  DeepSeek/Qwen fallback, no streaming, no rolling summary, no generation jobs, no
  dependency, no artifact mutation.** Obvious raw keys/Authorization bearer headers/
  full URLs are masked before Ask cache/session persistence and responses. Verified:
  `test_ask_local_chat.py` 40/40, inventory 50/50, prepare 58/58, compileall pass,
  compose config exit 0, release smoke 28/28.
- **Ask Your Guide — inserted workspace shell slice (FRONTEND ONLY)** (branch
  `ask-workspace-shell`). Adds a first-class `Ask Guide` sidebar workspace with the
  design-doc three-region shape: guide picker (left), disabled chat/readiness panel
  (center), and selected-guide/context/local-model rail (right). It consumes existing
  summary-only endpoints: `GET /api/ask/jobs`, `GET /api/ask/jobs/{job_id}/context`,
  `POST /api/ask/jobs/{job_id}/prepare`, plus existing LMM `GET
  /api/local-model/status` and `GET /api/local-model/command-profile`. It shows eligible
  guides, safe metadata, readiness reasons, guide/source counts, attachment/page
  summaries, prepare cache status + chunk counts + citation samples, and local model
  offline/reachable state with the manual command helper. **No backend chat route, no
  sessions, no `/api/ask/sessions`, no model/local-model call, no DeepSeek/Qwen/cloud
  fallback, no extra uploads, no chat persistence, no artifact mutation, no dependency.**
  The composer is disabled with "chat lands next" copy. New pure helper
  `frontend/src/askGuide.js` basenames attachment/page-selection names and renders only
  safe summaries (no guide/source body, chunk text, raw key, full URL, or host path).
  Verified: `npm run test:ask-guide`, `npm run test:local-model-command`,
  `npm run test:local-model-status`, `npm run build`.
- **Ask Your Guide — Slice 3: backend context preparation / chunking (BACKEND ONLY)**
  (branch `ask-context-prepare`). New stdlib-only `pipeline/ask_context.py` chunks
  `clean.md` (guide) + optional `extracted.txt` (source) deterministically on heading /
  `## Page N` boundaries (~650-token target, ~800 ceiling via `chars/4`, no overlap),
  preserving each chunk's **citation label** (nearest guide heading / `Page N` + page
  number) and building a **dependency-free lexical index** (per-chunk term frequencies +
  `doc_freq`). `POST /api/ask/jobs/{id}/prepare` (before the SPA mount) builds OR reuses
  a cache at `jobs/<id>/ask/cache/context_index.json`, keyed by a **content hash** over
  guide+source bytes — **idempotent** (`hit` rewrites nothing; `clean.md`/`extracted.txt`
  change → `rebuilt`; corrupt/stale cache → safe rebuild), **atomic** (temp +
  `os.replace`), **fenced** to the job dir. Unknown job → 404; guide-less existing job →
  200 `ready:false`. Response is an explicit whitelist (`job_id`, `ready`, `cache_status`,
  `content_hash`, guide/source/total chunk counts, bounded `citation_summary`,
  job-relative `cache_relpath`) — **no guide/source body, chunk text, key, full URL, or
  host path**; the cache holds chunk text for Slice 4 but only whitelisted top-level keys
  (never the manifest). **No chat, no retrieval endpoint, no model/local-model call, no
  cloud key read, no sessions, no extra uploads, no UI, no new dependency; original
  artifacts untouched (no `save_clean_md`, no manifest write).** Verified: `compileall`
  OK, `docker compose config` exit 0, container healthy,
  `test_scripts/test_ask_context_prepare.py` **58/58 in Docker**, Slice 2
  `test_ask_context_inventory.py` **50/50** unchanged, live prepare→hit on a real job +
  clean response/cache secret scan, read-only sha256 of `clean.md`/`extracted.txt`/
  `job.json` unchanged. See `CURRENT_TASK.md` #52. Historical NEXT here is superseded:
  backend local chat API, frontend chat UI wiring, chat/citation polish, and session
  management and math/source visual polish are now done; current NEXT is manual
  browser validation/polish of the Ask chat UI slice, or extra session uploads only
  as a separate explicit Ask slice.
- **Ask Your Guide — Slice 2: backend context inventory endpoint (BACKEND ONLY)**
  (branch `ask-context-inventory`). Two **read-only** endpoints over generated-guide
  artifacts: `GET /api/ask/jobs` lists **only Ask-eligible jobs** (those with a
  generated `clean.md`; guide-less / failed / incomplete jobs filtered out) with curated
  redacted picker fields (id/title/status/created+updated/style/preset/provider/model/
  favorite/attachment_summary/guide+source availability); `GET /api/ask/jobs/{id}/context`
  returns a per-job **readiness + source inventory** (guide `clean_md` present + char +
  heading counts; source `extracted.txt` present + char + `## Page N` anchor count;
  redacted attachment names/modes/extracted_chars/warnings; page selections; a
  `readiness{status,ready,reasons}` object; unknown job → 404, guide-less existing job →
  200 `not_ready`). New thin reader `pipeline/ask_inventory.py` (counts only — **never a
  guide/source body**); routes reuse the existing `_safe_manifest` /
  `_safe_attachment_metadata` / `_attachment_summary` / `_safe_page_selections`
  redaction + an explicit field whitelist, registered before the SPA mount. **No chat,
  no chunking, no retrieval/indexing, no model call, no local-model call, no cloud
  fallback, no session storage, no extra uploads, no UI; original job artifacts
  untouched (no `save_clean_md`, no manifest write).** Verified: `compileall` OK,
  `docker compose config` exit 0, image rebuilt + container healthy,
  `test_scripts/test_ask_context_inventory.py` **50/50 in Docker**, live seeded-job
  proof + clean raw-response secret scan (planted `sk-live-…`/base-URL/host-path did not
  leak), read-only sha256 of `clean.md`/`extracted.txt`/`job.json` unchanged. See
  `CURRENT_TASK.md` #51. **NEXT = Ask Slice 3 (context preparation / chunking).**
- **Ask Your Guide — Slice 1: design (docs-only)** (branch `ask-your-guide-design`).
  A design-first definition of a dedicated **Ask Your Guide** workspace
  (`docs/ASK_YOUR_GUIDE_DESIGN.md`): the user selects a generated guide/job and chats
  with it using a **local model only**. First-class page/tab (guide+session picker /
  chat / sources+citations panel), **local-only** and **status-gated** on LMM Phase 1
  (offline → first-class offline state + command helper; **no DeepSeek/Qwen/cloud
  fallback**), a **mandatory context manager** (chunk `clean.md`/`extracted.txt` with
  `## Page N`/heading citation anchors → dependency-free lexical index cached per
  `(job_id, content_hash)` → budgeted retrieval reserving answer/system-rules/recent
  chat → rolling chat summary), a hard **accuracy/citation contract**, conservative
  **session-scoped** storage (never auto-exported, no secrets), 8 proposed local-only
  endpoints (`/api/ask/*`, all read-only over job artifacts), and a 10-slice build
  plan. **No code changed.** NEXT = Ask Slice 2 (backend context inventory endpoint).
- **Local Model Manager — Phase 1 COMPLETE + VALIDATED** (Slices 1→4 +
  Slice 5 validation). Detection-only status (`GET /api/local-model/status` +
  `POST /api/local-model/check`), the read-only **Local Models** panel, and the
  manual **command helper** (`GET /api/local-model/command-profile`) are all on trunk
  (`94003bc`→`e399f09`). The **Slice 5 validation pass** (branch
  `docs-validate-local-model-manager-phase1`, docs-only, no code changed) confirmed
  every Phase-1 guarantee: static suites green, Docker container healthy, smoke 28/28,
  live `/status`+`/command-profile` 200 (offline → safe `local_offline`, placeholder
  command, host-only URL), **no-process-execution proof** (only comments assert
  absence; the command helper returns strings/argv via `shlex.quote`), and a **clean
  secret scan** (the lone JS hit was a 4-char `LOCAL_LLM_API_KEY=none` placeholder
  coinciding with `display:"none"`, not a real key). No bugs found. See
  `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md` + `CURRENT_TASK.md` #49.
- **Local Model Manager — Slice 4: command-helper profiles / Copy start command**
  (branch `local-model-command-helper`). Read-only
  `GET /api/local-model/command-profile` → `get_local_model_command_profiles()` in
  `pipeline/provider_config.py`: static, whitelisted `llama-server` start commands
  (`llama_server_default` GPU + `llama_server_cpu`) with a `/path/to/model.gguf`
  **placeholder**, `--host 0.0.0.0 --port 8080`, and safety warnings. Command built
  from a fixed flag whitelist + `argv` (rendered via `shlex.quote`); the only
  substitution is the model placeholder. Frontend: `getLocalModelCommandProfile()`
  client helper + pure `frontend/src/localModelCommand.js` + a `CommandHelper` block
  in `LocalModelsPanel.jsx` (profile chips, selectable code block, **Copy command**
  with clipboard + manual fallback, prominent when offline / collapsed when
  reachable). The deferred `copy_start_command` "Planned" chip is suppressed; the
  Slice 2 status DTO is unchanged. **Command helper only — the app NEVER executes
  it: no subprocess/spawn, no start/stop, no host companion, no GGUF scan, no
  arbitrary shell, no raw key, host-only URL.** Tests:
  `test_scripts/test_local_model_command_profile.py` 13/13;
  `frontend/scripts/verify-local-model-command.mjs` (`npm run
  test:local-model-command`); Slice 2/3 + provider suites unchanged; `npm run build`
  OK. See `CURRENT_TASK.md` #48 + `LOCAL_MODEL_MANAGER_DESIGN.md` §11 (Slice 4 note).
- **Local Model Manager — Slice 3: Local Models status panel (FRONTEND)** (branch
  `local-model-status-ui`, frontend + API client + docs/tests only). A read-only
  **Local Models** panel mounted inside the Providers (Models) page, consuming the
  Slice 2 endpoints. New API client helpers `getLocalModelStatus()` (`GET
  /api/local-model/status`) + `checkLocalModelStatus()` (`POST /api/local-model/check`);
  pure `frontend/src/localModelStatus.js` helpers (mirrors `shortcutStatus.js`) that
  normalize the DTO into `reachable | offline | not_configured | error | unknown`
  (tolerating missing fields / an old backend) with badge, model-chip
  (`limit=12` + overflow), latency/error/notes, action enabled/disabled, and a
  `hasEnabledProcessControl` invariant guard; `LocalModelsPanel.jsx` rendering a
  status pill, host-only base URL + in-Docker flag, a metrics strip, bounded model
  chips, a first-class offline/troubleshooting state (incl. the `--host 0.0.0.0`
  note), a **Refresh status** button (calls `/check`, never saves/starts), an "Edit
  local provider settings" link that scrolls to `#provider-card-local` (single
  writer), and the **disabled** "Copy start command — Planned" chip. **No process
  control, no inline base-URL editing, no raw key/URL.** Tests:
  `frontend/scripts/verify-local-model-status.mjs` 47/47 (`npm run
  test:local-model-status`); `npm run build` OK; backend suites unchanged
  (`test_local_model_status.py` 17/17, fetch-models 16/16, settings-store 26/26);
  smoke 28/28; live offline proof + clean secret scan. See `CURRENT_TASK.md` #47 +
  `LOCAL_MODEL_MANAGER_DESIGN.md` §11 (Slice 3 note).
- **Local Model Manager — Slice 2: detection-only backend status endpoint**
  (branch `local-model-status-api`, backend-only, on trunk as `e27c674`). Read-only
  `GET /api/local-model/status` + a thin `POST /api/local-model/check` alias, backed
  by `get_local_model_status()` in `pipeline/provider_config.py`. Returns a safe DTO
  (`{ok, provider, configured, base_url_host, base_url_configured, in_docker,
  reachable, models, model_count, default_model, selected_model, latency_ms, error,
  actions, notes}`). **`ok` ≠ reachable.** Connection failures normalize to a single
  `local_offline`. **No process spawn, no writes, no file browsing, no raw key,
  host-only URL.** See `CURRENT_TASK.md` #46 + `LOCAL_MODEL_MANAGER_DESIGN.md` §11.
- **Shortcut Inspector — degraded-activation confirm + "Repair instead"**
  (branch `shortcut-inspector-degraded-activation`, frontend-only). Home card
  launches now route through a pure `activationDecision` (`shortcutStatus.js` →
  `launch`/`confirm`/`blocked`): a **valid** shortcut launches immediately; a
  **degraded-yet-launchable** one (`validity.status === "degraded"` while legacy
  `valid === true`) raises a confirm dialog — **Continue anyway** (unchanged
  launch path, no mutation) / **Repair instead** (opens the existing Inspector
  drawer, no preview/apply until the user acts) / **Cancel**; a **broken** one
  (`valid === false`) stays blocked and shows a "This shortcut is broken."
  Inspect/Repair dialog instead of silently routing. Legacy `valid` is still the
  hard guard. New node harness `verify-shortcut-activation.mjs` (wired into
  `test:shortcuts`). No backend change. See `CURRENT_TASK.md` #43 +
  `SHORTCUT_INSPECTOR_REPAIR_DESIGN.md` §5.5 + `DECISIONS.md`.
- **Shortcut Inspector / Repair Loop — COMPLETE through Slice 3B**
  (`a0f96d1`→`4458c9a`, DONE #39→#42): a read-only inspector with an additive
  `validity` object (3-tier `valid`/`degraded`/`broken` status, the **full**
  findings list, and the previously-missing saved-`model` check) + `GET
  /api/shortcuts/{id}/inspect`, with the legacy `valid`/`reason` preserved
  byte-for-byte; 3-tier Home/Customize badges + a read-only Inspector drawer;
  repair endpoints `POST /api/shortcuts/{id}/repair/preview` (read-only) +
  `…/repair/apply` (the only write — explicit whitelisted patch, in-place or
  clone); and the repair UI (Keep/Replace/Remove controls, in-place vs clone,
  **Preview required before Apply**, editing the draft re-disables Apply,
  explicit confirm). No migration-on-read; preview never mutates `shortcuts.json`;
  clone mints a new id and leaves the original untouched; **card activation is
  unchanged** (still gated on legacy `valid`). Validated docs-only in
  `docs/VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md`. See `CURRENT_TASK.md` #39→#42 +
  `DECISIONS.md` (shortcut inspector/repair entries).
- **In-app provider settings feature group — COMPLETE through Slice 5**
  (`978516e`→`61fb423`): a two-file server-side store
  (`config/provider_settings.json` non-secret `0644` + `config/secrets.json`
  raw-keys-only `0600`), safe endpoints (`GET /api/provider-settings`,
  `PATCH /api/provider-settings/{provider}`, `…/clear-key`, `…/test`,
  `…/fetch-models`), a frontend Providers page (routed from the Models sidebar
  item) with a per-card **Refresh models** button, and **runtime** wiring so the
  stored `timeout_seconds`/`retry_count`/`thinking_default` reach the live model
  call. The read-only `POST …/{provider}/fetch-models` endpoint (`6da944a`) lists
  provider models without auto-persisting; the Refresh Models UI (`61fb423`) shows
  fetched ids **review-only**, stages new ids into the draft `custom_models` via
  **Add** / **Add all new**, and requires an **explicit Save** to persist (after
  which `/api/options` includes the saved custom models — Builder dropdowns keep
  reading `/api/options`). Fetching never auto-saves and never auto-switches the
  provider/default model. **Security:** raw keys stay **server-side only**;
  `/api/options`, `/api/provider-settings`, and the fetch-models response are
  **redacted** (no key field by construction — only `configured`/`key_source`/
  last-4 `key_hint`/`base_url_host`); the API key is write-only. **Precedence:**
  provider/model = **per-job request > provider-settings default > `.env` >
  built-in**; generator presets **never hard-pin** provider/model (`model_hint`
  advisory), and an **explicit** preset sampling/thinking value overrides the
  stored runtime default. No store files ⇒ byte-identical to the prior env path.
  See `CURRENT_TASK.md` #32→#36 + `DECISIONS.md` (provider-settings entries).
- **Large-PDF core workflow — COMPLETE end-to-end** (`841d3f9`→`60c3e78`): a
  read-only `POST /api/preflight/pdf` verdict (`ok`/`warn`/`blocked`), a Builder
  preflight warning card, `page_selections` (`{filename: [[start,end],…]}`,
  1-based inclusive) plumbed through the request + persisted in the manifest, the
  extractor restricting matching PDFs to the selected ORIGINAL pages (anchors
  preserved, OCR only on selected pages), and a live first-N / manual page-range
  UI. **Usable end-to-end:** preflight warns → user picks first N or a range →
  the request carries `page_selections` → extraction uses the original page
  anchors. **Automatic split/chunk processing and hybrid embedded-text + OCR
  dedup remain deferred.** See `CURRENT_TASK.md` #27→#31.
- **Cooperative server-side cancel** (`901d44b`): a `jobs/<id>/cancel.requested` marker
  checked at safe stage boundaries, a new `cancelled` terminal status,
  `POST /api/jobs/{id}/cancel`, and a Builder Cancel button. **Checkpoint-based,
  cooperative only** — it does **not** kill processes/threads; a cancel during an
  uninterruptible LLM call or Chromium render takes effect at the **next safe
  checkpoint**, not instantly. Partial artifacts and the user's uploads / Builder
  inputs / settings are **preserved** (nothing deleted; re-generate from the Builder).
  Retry-from-cancelled is deferred. See `CURRENT_TASK.md` #22.
- **B4 "Export selected"** (`65b9b8f`): the Library bulk bar gained an "Export selected"
  action reusing the existing `POST /api/exports/bundle` ZIP endpoint (no new primitive,
  no backend change). See `CURRENT_TASK.md` #21.
- **Rerender preserves `generator_preset`** (`2716995`): `retry_failed_job` now reads the
  preset from the manifest and rebuilds through it (tuned sampling params + system prompt
  reapplied), instead of dropping to the default path. A since-removed preset id degrades
  gracefully; the user's saved provider/model still wins. Backend-only.
- **Group C fully integrated** onto `chrome-renderer-v1` (squash `6f888b2`): generator
  presets + cards, output-section toggles (`include_sections`), depth/difficulty axes,
  shortcut options bridge, Builder options UI, `qwen3.7-plus`, Home/nav cleanup.
- **OCR + PDF fixes** on the trunk: re-applied `_preprocess_ocr_image` (`5bde798`), MCQ
  answer + page-reference prompt fixes (`75ec24f`), and **page-level mixed scanned/text
  PDF OCR fallback** (`72dab90` / `773209a`).
- **Docker compose hardening** (`1d51b36`): `mem_limit: 2g`, `pids_limit: 256`,
  `cpus: 2.0`, `security_opt: no-new-privileges:true` (additive, `docker compose config`
  validated). Salvaged from local-only `863f5b7`; its non-root/gosu hardening was already
  in at `6f888b2`.

## ⚠️ Old branches — do NOT re-merge
The whole Group C feature stack (`style-output-toggles`, `style-axes`,
`shortcut-options-bridge`, `builder-options-ui`, `preset-*`, `qwen37-plus-model`,
`home-nav-cleanup`, `library-*`, plus `integ-group-c` and `salvage-compose-limits`) is
**consumed/archival**. Its content already lives in the trunk. **Do not merge or rebase
any of them again** — it would reintroduce superseded code and resurrect resolved
conflicts. They are kept (not deleted) only as reference. See `DECISIONS.md`.

Local-only `61c134c` and `863f5b7` stay **parked on the `hardening` branch** — useful
pieces already salvaged; the rest is deferred (below).

## RULE for new work
**Branch from `chrome-renderer-v1` @ `e399f09` (or later) — never from an old stacked
branch.** One small slice per branch; verify (build + compile + docker + smoke) and
commit before moving on. Surgical edits, not rewrites. The PDF/Chromium pipeline is
load-bearing — do not rewrite casually.

## Next recommended slice
**Ask Your Guide — extra session uploads** are a separate optional slice only if the
operator explicitly chooses to continue Ask features. Do not start extra uploads
automatically.
- **Broader manual Ask UI validation / polish** should stay narrow and bug-driven;
  the empty local-model response regression found during manual validation is now
  guarded and covered.
- **Still deferred:** streaming, hosted/cloud Ask, rolling summary, multimodal, and
  local model process control.
- **Focused manual validation / polish of the Shortcut Inspector UI.** The
  inspect→repair loop + degraded-activation confirm are complete and validated at
  the API + harness level; the remaining gap is a human click-through of the live
  Home/Customize 3-tier badges, the Inspector drawer, the Preview→Apply / clone
  flow (incl. the stale-preview re-disable), and the new degraded/broken
  activation dialogs. Validation / polish only — no code unless a concrete UI bug
  surfaces.
- **Math/PDF font-size rationalization (cause C, CSS-only).** Optional remaining
  fidelity slice; CSS-only investigation before any change.
- **Large-PDF preflight size-limit polish — optional, later.** Raising the upload
  ceiling + preflight size thresholds is a possible later slice; **not part of any
  current slice** and not started.

(The previously-recommended **in-app provider settings** (COMPLETE through
**Slice 5** — fetch-models endpoint + Refresh Models UI), the **shortcut inspector
/ repair loop** (now COMPLETE through **Slice 3B**, `a0f96d1`→`4458c9a`),
**Math/PDF fidelity investigation**, and **Large-PDF preflight design** are **all
DONE** — provider settings shipped as #32→#36 (`978516e`→`61fb423`), the shortcut
inspector shipped as #39→#42, the preflight design shipped as Slices 1–5
(`841d3f9`→`60c3e78`), and the math/PDF fidelity Slices 1–3 shipped (#23–#25). The
provider-settings real-world validation pass also ran
(`docs/VALIDATION_PROVIDER_SETTINGS_LARGE_PDF.md`, two now-fixed findings). The
rerender `generator_preset` fix, B4 "Export selected", and server-side cancel are
also DONE and on trunk — see "What just landed". The only remaining math/PDF slice
is the optional **font-size rationalization** (cause C, CSS-only).)

## Open / deferred items
- **rerender drops `generator_preset`** — DONE (`2716995`, on trunk). Rerender now
  reproduces the preset.
- **B4 "Export selected"** — DONE (`65b9b8f`, on trunk). Reuses the existing bundle endpoint.
- **Real server-side cancel button** — DONE (`901d44b`, on trunk; cooperative,
  checkpoint-based, marker file, `cancelled` status; does not kill processes; preserves
  uploads/inputs/settings). Retry-from-cancelled still deferred (re-generate from the
  Builder instead).
- **Large-PDF core (preflight + page-range selection)** — DONE end-to-end
  (`841d3f9`→`60c3e78`, #27→#31): preflight verdict endpoint, Builder warning card,
  `page_selections` plumbing + manifest persistence, extraction honoring selected
  ORIGINAL pages (OCR only on selected pages), and the first-N / manual page-range UI.
- **Math / PDF fidelity Slices 1–3** — DONE (#23–#25). Remaining optional slice:
  **font-size rationalization** (cause C, CSS-only).
- **Large-PDF — still deferred:** automatic split/chunk processing; hybrid
  embedded-text + OCR dedup; raising the upload ceiling (`MAX_UPLOAD_MB`); persisting
  the preflight report in `job.json`; carrying page selections into drafts/shortcuts.
  None started — do not begin without an explicit slice + design.
- **In-app provider settings feature group** — DONE through Slice 5
  (`978516e`→`61fb423`, #32→#36): two-file store (non-secret
  `provider_settings.json` + `0600` `secrets.json`), redacted endpoints, Providers
  UI, runtime `timeout_seconds`/`retry_count`/`thinking_default` applied, read-only
  `fetch-models` endpoint, and the Refresh Models UI (review-only fetch → stage into
  draft `custom_models` → explicit Save). Keys stay server-side only; presets never
  hard-pin provider/model. **Still deferred:** encrypted-at-rest / OS keyring; `.env`
  import; optional Builder "Provider default" thinking UI polish.
- **Local Model Manager** — **Phase 1 COMPLETE + VALIDATED** (Slices 1→4 on trunk
  `94003bc`→`e399f09`; Slice 5 validation docs-only,
  `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`). Slice 2 =
  the detection-only backend status endpoint (`GET /api/local-model/status` + `POST
  /api/local-model/check`, `get_local_model_status()`) shipping safe fields only.
  Slice 3 = the read-only **Local Models status panel** in the Providers (Models)
  page (`LocalModelsPanel.jsx` + pure `localModelStatus.js` + the
  `getLocalModelStatus`/`checkLocalModelStatus` client helpers): status pill,
  host-only base URL, latency, model count + chips, first-class offline
  troubleshooting, **Refresh status**, and an "Edit local provider settings" link to
  the Local card — **no** process control, inline editing, or raw key/URL. Slice 4 =
  the **command helper** (`GET /api/local-model/command-profile` +
  `localModelCommand.js` + a `CommandHelper` block): a copyable, static, whitelisted
  `llama-server` start command (placeholder model path, `--host 0.0.0.0`) the
  operator runs **manually** — the app never executes it. **Phase 1 is feature-complete
  and validated** (Slice 5, DONE #49). **Next major choice = Ask Your Guide local-only
  chat (recommended)** or the sign-off-gated host-companion DESIGN (Phase 2). Remains a
  **separate** feature from the in-app provider settings; provider config writes stay on
  `PATCH /api/provider-settings/local`.
- **Library archive / tag model** — DESIGN-FIRST (bulk archive needs an archive state +
  `DECISIONS.md` entry; bulk tag needs a tag model; neither started).
- **GHCR publish workflow / prebuilt image** — deferred distribution decision (parked on `hardening`).
- **Pinned dependency lockfile** — deferred; regenerate from this tree, don't lift from `hardening`.
- **Provider-aware truncation caps** — deferred (Option B in `DECISIONS.md`).
- **Shortcut inspector / repair loop** — DONE through Slice 3B
  (`a0f96d1`→`4458c9a`, #39→#42): additive `validity` (3-tier status, full
  findings, saved-model check; legacy `valid`/`reason` preserved), `GET
  …/inspect`, 3-tier badges + read-only Inspector drawer, repair preview
  (read-only) / apply (the only write; in-place + clone) + repair UI
  (Preview-before-Apply, stale-preview re-disable, explicit confirm). Validated
  docs-only (`docs/VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md`). The
  **degraded-activation confirm / "Repair instead" Home path (§5.5) is now DONE**
  (branch `shortcut-inspector-degraded-activation`, #43 — see "What just landed").
  **Still deferred:** "Repair all" batch, a Home "N need attention" banner, model
  auto-suggest/fuzzy match, imported preview-row repair before import, tool/view
  repair (repair is scoped to `builder_setup`).
- **Branch retirement** — deferred housekeeping (do not delete branches).
- **Group D** — not started; do not begin without an explicit slice request.

## Verification commands
```fish
npm --prefix frontend run build          # builds frontend/dist (served by backend)
python -m compileall api pipeline        # compile-check backend + pipeline
docker compose config                    # validate compose (expands .env in plaintext — do not share output)
docker compose build
docker compose up
curl http://localhost:8000/api/health    # {"ok":true}
curl http://localhost:8000/api/options   # themes / styles / providers / models / generator_presets (redacted)
curl http://localhost:8000/api/provider-settings  # provider settings, redacted (no raw keys; only configured/key_source/key_hint/base_url_host)
python test_scripts/smoke_release.py     # end-to-end release smoke (~28 checks; outline-ordering check is known-flaky)
```
