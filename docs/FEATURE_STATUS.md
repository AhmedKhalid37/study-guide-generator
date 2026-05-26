# Feature Status

Inventory of the Study Guide Generator as of the release-readiness checkpoint.
End-to-end coverage lives in `test_scripts/smoke_release.py`.

## Completed (verified)

| Area | Feature | Notes |
| --- | --- | --- |
| Core | Health / options | `GET /api/health`, `GET /api/options` (no secrets) |
| Generate | Paste text → guide | `POST /api/jobs/paste` |
| Generate | Upload Markdown → guide | `POST /api/jobs/upload-markdown` (`.md`/`.markdown`) |
| Generate | AI / LLM generation | `POST /api/jobs/llm`; default New Guide mode |
| Generate | Attachments + OCR | `.txt/.md/.csv/.tsv/.docx/.pptx/.pdf`; Tesseract OCR for image PDFs |
| Providers | DeepSeek + Qwen | configured via `.env`; local llama.cpp via discovery |
| Styles | Built-in presets | 7 built-ins in `prompts/` |
| Styles | Custom + AI-generated | `/api/styles*`, `/api/styles/generate`; persisted in `user_prompts/` |
| Outline | Editable Builder outline | templates, add/rename/delete/reorder, instructions |
| Outline | AI outline draft | `POST /api/outline/generate` |
| Outline | Injection + metadata | "Required Outline" directive; summary in Job Details |
| Library | Folders | create/rename/delete; `library/folders.json` |
| Library | Search / filter / sort | client-side over `GET /api/library` |
| Library | Single + batch move | `POST /api/library/jobs/move` and `/{id}/move` |
| Library | Save-to-folder on generate | folder picker + inline create in Builder |
| Exports | Artifact center | filters, per-job downloads, availability pills |
| Exports | ZIP bundle | `POST /api/exports/bundle` + in-zip `manifest.json` |
| Artifacts | PDF / HTML / Markdown | `final.pdf`, `final.html`, `clean.md` |
| Artifacts | DOCX | `final.docx`, generated lazily from `clean.md` (old jobs too) |
| Artifacts | Re-render | `POST /api/jobs/{id}/rerender` (PDF/HTML; keeps DOCX in sync) |
| UX | Job Details drawer | metadata, style/folder/outline summary, downloads |
| Math | Sanitizer + KaTeX validation | load-bearing; do not edit casually |
| Security | Keys stay server-side | `/api/options` exposes only `configured` flags |

## Partially completed

- **Filtering/sorting is client-side** in Library and Exports (server params
  exist and are used by smoke tests, but the UI fetches all jobs once).
- **Outline ordering** relies on model compliance — the directive is strong but
  not enforced/repaired after generation.
- **DOCX fidelity** is practical, not pixel-perfect (see limitations).

## Intentionally deferred (not started)

- Saved/reusable outline **templates** as presets.
- **Drag-and-drop** reordering (outline / library).
- **Server-side pagination** shared by Library/Exports.
- A **second PDF theme** / theme-picker system.
- Wiring the cosmetic **"Save draft"** button (currently inert).
- Streaming LLM responses; multimodal/image understanding.

## Known limitations

- DOCX: math is preserved as literal LaTeX **text** (not rendered equations);
  images become a `[image: alt]` placeholder; deeply nested lists collapse to the
  deepest Word list level; raw HTML renders as text.
- A successful job always has all artifacts, so "skipped artifact" in a ZIP only
  occurs for unknown/failed jobs.
- The Builder "Save draft" button and the sidebar storage meter are decorative.
- OCR quality depends on scan quality.

## Command checklist

```bash
npm --prefix frontend run build        # build the React UI
python -m compileall api pipeline      # compile-check backend + pipeline
docker compose config                  # validate compose (expands secrets!)
docker compose build                   # build the image
docker compose up                      # run on :8000
python test_scripts/smoke_release.py   # end-to-end smoke (skips provider tests if unconfigured)
```
