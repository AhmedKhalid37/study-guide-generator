# Eval results (git-ignored)

Generated result files land here:

- `<spec_id>__<mode>__<guide>__<run_id>.json` — one per scored guide.
- `summary.csv` — appended one row per run.

These are **git-ignored** (see the repo `.gitignore`): they are reproducible run
artifacts, not source. Only this README is tracked so the directory exists in a
fresh checkout. Override the location with `--output-dir` if you prefer to write
results elsewhere.

Regression comparison reads the most recent prior result for the same
`(spec_id, mode, guide)` from this directory (or whichever `--output-dir` you
pass).
