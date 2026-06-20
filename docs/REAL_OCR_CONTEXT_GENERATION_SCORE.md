# Real OCR-Context Generation Score

Slice 176N is the fair measurement that Slice 176L explicitly left open. Slice
176L made the private OCR content student-readable, but its candidate was a
deterministic preview scaffold scored against a full generated baseline guide, so
the regression was a stub-vs-full-guide confound.

176N runs the existing guide generation path in an off-by-default private mode:
private OCR-extracted lecture content is packaged as source material, optional
visible assets can be included as display-only context, and the existing provider
configuration path is used to produce a real generated guide. The generated guide,
source context bundle, visible asset material, and any scoring artifacts stay only
in the private ignored artifact area.

Committed-safe summary fields:

- `artifact_name=real_ocr_context_generation_score`
- `source_label=ensemble`
- `generation_mode=existing_configured_provider`
- `guide_artifact_status=generated`
- `private_generated_guide_written=true`
- `private_generated_guide_gitignored=true`
- `score_status=scored`
- `baseline_comparison_status=unchanged`
- `coverage_signal=unchanged`
- `figure_table_signal=unchanged`
- `stub_vs_full_confounded=false`
- `generation_behavior_changed=false`
- `frontend_api_changed=false`
- `raw_ocr_committed=false`
- `raw_guide_text_committed=false`
- `raw_table_text_committed=false`
- `raw_caption_text_committed=false`
- `rendered_guide_committed=false`
- `prompts_committed=false`
- `responses_committed=false`
- `provider_payloads_committed=false`
- `source_pdf_committed=false`
- `numeric_verification_claimed=false`
- `judge_ready=false`
- `repair_ready=false`

Scope boundaries: no cloud OCR, no new judge, no Layer-2 judge, no repair, no
numeric recompute, no new provider integration, and no frontend/API wiring. The
normal guide-generation behavior is unchanged by default.

Result recording for this slice remains closed vocabulary only. If generation or
scoring is unavailable, the summary records `status=blocked` or `degraded` with
closed reason tokens; it must not fall back to `deterministic_stub_preview` and
call that a fair comparison.

176N's banked result is load-bearing negative evidence: the real generated OCR-
context guide scored `unchanged` on the existing comparison. That is not a cue to
grind packaging iterations immediately. Before spending another provider
generation run, diagnose whether the flat score is best explained by weak context
packaging, the model already knowing common StatQuest ensemble material, or the
existing scorer mostly measuring structure/format rather than deck-specific
coverage. The next slice should compare the private generated guide with the
private baseline and inspect scorer sensitivity without committing raw guide/OCR/
table/caption/prompt/response/provider payload content.
