# Guide Quality Baseline Harness (Slice 149)

Concise operator notes for the measured guide-quality baseline. The baseline
**reuses existing wired artifacts** — it reruns no checks, reads no
PDFs/guides/`clean.md`/source/OCR text, and calls no provider/model/cloud/local
LLM. It is advisory and non-blocking.

Module: `pipeline/guide_quality_baseline.py` ·
Golden spec: `test_scripts/fixtures/guide_quality_baseline/nn_iris_local_golden_spec.json`

## What may be committed

- **Committed:** the closed **golden spec** (closed facts/labels/expectations,
  not copied source text) and **closed aggregate metrics / trend snapshots**.
- **Never committed:** source/reference PDFs, generated guides, `clean.md`,
  source/OCR/table/caption text, screenshots, raw job artifact JSON from private
  runs, private paths/filenames, provider payloads, prompts/responses.

## Running a real local baseline

1. Generate a guide **locally** from the fixture material (e.g. NN/Iris). Keep
   the source/reference PDFs and the generated guide **out of git** (local /
   gitignored).
2. Locate that job's artifact directory (it holds the existing wired artifacts:
   `math_verification.json`, `guide_quality_contract_lint.json`,
   `guide_quality_qa_gate.json`, and, where produced, `guide_quality_report_v2.json`,
   `source_coverage_report.json`, `guide_quality_rubric_score.json`).
3. Run the harness in **local mode** against that directory (it reads only the
   exact-name artifacts and prints a **closed aggregate summary only** — the
   directory path is never echoed):

   ```
   python test_scripts/validate_guide_quality_baseline_harness.py \
     --golden-spec test_scripts/fixtures/guide_quality_baseline/nn_iris_local_golden_spec.json \
     --artifact-dir <local_gitignored_job_artifact_dir> \
     --run-label app_run_1
   ```

   (Equivalently, call `collect_guide_quality_baseline_artifacts(...)` then
   `build_guide_quality_baseline_record(golden_spec, artifacts)` directly.)
4. The output / record contains **closed aggregate metrics only** (closed status
   tokens + closed warning labels). Headline metric: `reasoning_leak_status`.
   Local mode exits nonzero only on a harness error (unreadable golden spec /
   missing `--artifact-dir`), never because a metric is honestly `not_available`,
   `needs_future_metric`, or `fail`. Only the closed summary (not raw artifact
   JSON) may be committed if you choose to snapshot a baseline.

## Verification (no real fixture required)

```
python test_scripts/test_guide_quality_baseline.py
python test_scripts/validate_guide_quality_baseline_harness.py
```

Both run on synthetic artifact JSON in temp dirs only and write nothing to the
repo. With no `--artifact-dir`, the validator runs the synthetic self-test and
reports `local_operator_baseline_run=not_run`. A real local baseline is recorded
as `local_operator_baseline_run=closed_summary_only` (closed aggregate metrics
only). Keep the local source/reference/generated files and copied app job
artifacts out of git (e.g. under a gitignored `local_operator_baselines/` tree).
