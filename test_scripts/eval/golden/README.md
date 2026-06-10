# Golden specs

A *golden spec* describes what a good guide for a given topic should contain. It
drives the deterministic scoring in `../run_eval.py`. Specs are **JSON** (see the
parent README for why JSON, not YAML).

## Fields

| Field | Required | Type | Meaning |
| --- | --- | --- | --- |
| `id` | **yes** | string | Stable identifier; used in result filenames and regression keys. |
| `title` | no | string | Human-readable title (also used as the live paste title). |
| `source_kind` | no | string | Provenance label, e.g. `markdown_fixture`. Informational. |
| `source_path` | no* | string | Repo-relative path to the source input. **Required for `--live`.** |
| `expected_sections` | no | string[] | Section headings expected in the guide (drives the lint `missing_section` rule and is normalized). |
| `required_concepts` | no | string[] | Concepts that must appear (normalized substring match). |
| `must_not_claim` | no | string[] | Phrases that must **not** appear. |
| `known_numbers` | no | object[] | Advisory `{label, claim}` records of known-correct numbers. **Reserved** — informational only this slice; math scoring runs the verifier over the guide text itself, not over these. |
| `offline_guides` | no | string[] | Guides scored against this spec by `--offline --all`. If omitted, `--all` falls back to scoring `source_path`. |

All list fields must be lists of strings (`offline_guides` lists paths); anything
else is rejected with a clear `SpecError`.

## Example

See `sample.json`.
