# Guide Quality Operator Validation

This document defines the safe manual-review record for GuideForge guide-quality
closeout checks. It is a report format, not an artifact generator and not semantic
grading.

## Purpose and Scope

Use this checklist when an operator manually reviews a generated guide against the
guide-quality correction phase. The report records only closed-vocabulary outcomes
and high-level artifact presence. It must not record guide content.

Out of scope: automatic pass/fail grading, regeneration, provider calls, prompt
changes, render/export changes, Ask Guide changes, OCR/PDF/image inspection, table
reconstruction, or visual insertion.

## Privacy and No-Leak Rules

Do not record any of the following in this file or in copied report entries:

- guide snippets or source text
- formulas or numeric claim text
- filenames, paths, URLs, socket paths, argv, model paths, or executable paths
- OCR text, table text, captions, image refs, or asset refs
- provider payloads, provider keys, Authorization headers, companion tokens, data
  URIs, base64, or image bytes
- uploaded quality-spec evidence quotes or uploaded quality-spec filenames
- raw artifact warnings, raw exception text, raw errors, or raw private notes

Allowed report values are the closed tokens listed below.

## Manual Review Checklist

1. Confirm the Guide Quality panel renders without exposing raw JSON or errors.
2. Confirm exact-name artifacts are present or marked not available calmly.
3. Confirm the QA gate remains advisory and non-blocking.
4. Confirm the rubric score remains deterministic/advisory and unsupported semantic
   axes remain unknown or unsupported.
5. Review the guide visually using a non-private sample only.
6. Record only closed-vocabulary outcomes in the report template.
7. Run a no-leak sweep on the recorded report before committing.

## Closed-Vocabulary Report Template

```yaml
guide_quality_operator_validation: not_run
status: not_run
sample_type: not_applicable
guide_quality_contract_visible: not_applicable
qa_gate_artifact_present: not_applicable
rubric_score_artifact_present: not_applicable
guide_quality_panel_renders: not_applicable
reasoning_leak_visible_to_reader: not_reviewed
worked_examples_completed: not_reviewed
arithmetic_steps_visible: not_reviewed
beginner_scaffolding_visible: not_reviewed
exam_alerts_visible: not_reviewed
consolidation_sections_visible: not_reviewed
failure_category: sample_unavailable
no_leak_sweep: not_applicable
warnings: []
reason: non_private_operator_sample_not_supplied
```

Allowed values:

- `status`: `ok`, `warning`, `failed`, `not_run`
- `sample_type`: `synthetic`, `non_private_operator_sample`, `not_applicable`
- artifact/panel booleans: `true`, `false`, `not_applicable`
- `reasoning_leak_visible_to_reader`: `none_observed`, `possible_issue`,
  `not_reviewed`
- review outcomes: `ok`, `possible_issue`, `not_reviewed`
- `failure_category`: `none`, `sample_unavailable`, `panel_unavailable`,
  `artifact_unavailable`, `quality_issue`, `no_leak_failure`
- `no_leak_sweep`: `clean`, `failed`, `not_applicable`
- `warnings`: closed tokens only

## Current Recorded Status

```yaml
guide_quality_operator_validation: not_run
status: not_run
sample_type: not_applicable
guide_quality_contract_visible: not_applicable
qa_gate_artifact_present: not_applicable
rubric_score_artifact_present: not_applicable
guide_quality_panel_renders: not_applicable
reasoning_leak_visible_to_reader: not_reviewed
worked_examples_completed: not_reviewed
arithmetic_steps_visible: not_reviewed
beginner_scaffolding_visible: not_reviewed
exam_alerts_visible: not_reviewed
consolidation_sections_visible: not_reviewed
failure_category: sample_unavailable
no_leak_sweep: not_applicable
warnings: []
reason: non_private_operator_sample_not_supplied
```
