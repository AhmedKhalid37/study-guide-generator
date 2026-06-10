# GuideForge Eval Harness — Phase 1 (Slice 20)

A **deterministic** evaluation harness that scores generated study-guide quality
*before* we start optimizing prompts, OCR, retrieval, or styles. It is the
**measurement spine** — it measures, it does not improve generation.

Everything here is built on the pure correctness modules from earlier slices and
adds no new heavy dependency:

- `pipeline.math_verifier.verify_math_claims` (Slice 18 — numeric math)
- `pipeline.guide_lint.lint_guide_markdown` (Slice 19 — structure / render lint)
- two simple normalized string checks defined in `score_guide.py`
  (concept coverage and must-not-claim)

## What it measures

Each metric is in `[0.0, 1.0]`, higher is better:

| Metric | What it checks | How it scores |
| --- | --- | --- |
| `concepts` | `required_concepts` appear in the guide | `found / total` (normalized substring match) |
| `must_not_claim` | forbidden phrases do **not** appear | `(total − violations) / total` |
| `math` | numeric claims are correct (Slice 18) | `(ok + 0.75·unparseable) / total` — mismatches earn **no** credit, unparseable claims earn partial credit |
| `lint` | structural / render risks (Slice 19) | `clamp(1 − (0.20·errors + 0.05·warnings))` — `info` ignored |
| `artifacts` | expected artifacts exist (**live only**) | `present / expected`; `null` (not applicable) offline |
| `overall` | weighted mean of the above | weights `concepts .30 / math .25 / lint .20 / must_not_claim .15 / artifacts .10`, **renormalized** over whichever components are non-null |

When a metric has nothing to check (no required concepts, no forbidden phrases, no
math claims) it scores `1.0` — the harness never fails a guide for *lacking*
checkable content, and never fails on unparseable math.

## What it does NOT measure yet (deferred)

This phase is deliberately narrow. The following are **out of scope** and left to
later, separately-designed slices:

- **LLM-judge metrics** (rubric grading, faithfulness, helpfulness).
- **Embeddings / semantic similarity / LanceDB** — concept matching here is plain
  normalized substring matching only.
- **Retrieval / citation-quality evaluation** (Ask-Your-Guide).
- **OCR / extraction-quality evaluation.**
- **Generation changes** — the harness never touches prompts, provider behavior,
  `/api/jobs/llm` fields, the Builder/JobDetails UI, or job artifacts.

These are deferred because they need either a model call (LLM judge), a vector
index (embeddings/retrieval), or design decisions about ground-truth datasets —
none of which belong in a deterministic, dependency-free measurement baseline.
Establishing the deterministic spine first gives every later, fuzzier metric a
stable reference to compare against.

## Spec format — JSON (not YAML)

Golden specs are **JSON** (`golden/*.json`). JSON is in the standard library, so
offline scoring needs no extra dependency and runs identically on the host and
inside the non-root Docker image — matching the project's dependency-free stance
(Slice 18 likewise avoided SymPy though it was installed). A `.yaml`/`.yml` loader
is used *only* if PyYAML happens to be importable; the committed specs stay JSON.

See `golden/README.md` for the field reference.

## How to run

### Offline mode (required; no provider keys, no Docker, no LLM)

Score one guide against one spec:

```bash
python test_scripts/eval/run_eval.py --offline \
    --spec  test_scripts/eval/golden/sample.json \
    --guide test_scripts/eval/fixtures/sample_good_guide.md
```

Score every golden spec against its `offline_guides`:

```bash
python test_scripts/eval/run_eval.py --offline --all
python test_scripts/eval/run_eval.py --offline --all --output-dir test_scripts/eval/results
```

### Live mode (optional; uses the local API, never required for tests)

Submits the spec's `source_path` to the **no-provider** `/api/jobs/paste`
endpoint on a running local app, fetches the resulting `clean.md`, and scores it
(plus an artifact-presence probe). It uses only existing API behavior, times out
cleanly, prints no secrets, and records only the API **host** — never the full URL.

```bash
python test_scripts/eval/run_eval.py --live \
    --spec test_scripts/eval/golden/sample.json \
    --base-url http://localhost:8000
```

## Result files

Each scored guide writes a JSON result and appends a row to `summary.csv`, both
under the output directory (default `test_scripts/eval/results/`):

```
<spec_id>__<mode>__<guide>__<run_id>.json
```

Result shape (abbreviated):

```json
{
  "version": 1,
  "run_id": "2026-06-10T11-57-14Z",
  "mode": "offline",
  "spec_id": "sample_nn_part3",
  "guide_path": "test_scripts/eval/fixtures/sample_good_guide.md",
  "scores": { "overall": 0.9722, "concepts": 1.0, "math": 0.9, "lint": 1.0,
              "must_not_claim": 1.0, "artifacts": null },
  "details": { "missing_concepts": [], "must_not_claim_violations": [],
               "math_summary": {...}, "lint_summary": {...},
               "lint_top_findings": [...], "artifacts": null }
}
```

Generated result JSON/CSV are **git-ignored** (see the repo `.gitignore`); only
the small committed fixtures and golden specs are tracked. Large lecture
PDFs/inputs belong under `test_scripts/eval/inputs/` (also git-ignored) — never
commit them.

Before any result is written, it is scanned for credential-looking field names
and values; a suspected secret **blocks** the write rather than persisting it.

## Regression comparison

After scoring, the harness compares the result to the most recent prior result
for the **same `(spec_id, mode, guide)`** and prints the previous overall, the
current overall, the delta, and per-metric deltas. This is **non-blocking** in
this slice — a regression never fails the run. Different guides for the same spec
are never compared against each other.

## Tests

```bash
python test_scripts/test_eval_harness.py
```

Plain-Python assertions (no test framework), matching the rest of `test_scripts/`.
