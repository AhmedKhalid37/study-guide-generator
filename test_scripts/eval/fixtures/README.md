# Eval fixtures

Small, deterministic Markdown fixtures used by the offline harness and by
`test_scripts/test_eval_harness.py`. Keep them tiny and committed — large lecture
PDFs / generated inputs do **not** belong here (put those under
`test_scripts/eval/inputs/`, which is git-ignored).

| File | Purpose |
| --- | --- |
| `sample_source.md` | The raw "source notes" input for `golden/sample.json` (used by live mode). |
| `sample_good_guide.md` | A well-formed guide: all expected sections, all required concepts, correct math, no forbidden claims. Scores high. |
| `sample_bad_math_guide.md` | Same structure/concepts but with deliberately wrong arithmetic (`2 + 2 = 5`, `sqrt(16) = 5`, `10 / 2 = 6`). The `math` metric drops. |
| `sample_bad_structure_guide.md` | Missing sections, an empty heading, a broken table, and an unbalanced `$$` delimiter. The `lint` metric drops. |

These three guides intentionally isolate the metrics so the tests can assert that
the clean guide outscores each broken one.
