# VISUAL_PILOT_E2E_VALIDATION.md — Slice 58 stitched single-figure validation

> **This is a validation/harness slice, not a production-behavior slice.** It adds
> NO production code. It proves the already-shipped single-figure visual pilot
> (Slices 52–57) works as one connected chain *before* any visual expansion is
> considered. If a future change breaks the stitch, this harness fails loudly.

Harness: `test_scripts/test_visual_pilot_e2e_validation.py`.

---

## Why this slice exists

The visual pilot grew across many small slices — planner core (52), off-by-default
insertion (54), per-job opt-in (55), export ride-along (56), readiness guard (57).
Each slice has its own focused test, but nothing yet proved the **whole chain**
holds end-to-end: a safe job-local PNG → manifest/plan shape → both gates on →
exactly one markdown image → HTML/PDF/DOCX render → portable export ZIP.

This harness stitches those stages so the output of each feeds the next. We validate
the single-figure path is clean **before** spending any effort on multi-figure,
Chandra, or other expansion — see `DECISIONS.md`.

---

## What the harness proves

Run host-side for the always-on stages; run inside the container for full coverage.
All thirteen checks below pass in-container (**29 passed, 0 failed, 0 skipped**); on
a bare host the DOCX and export stages SKIP cleanly when `python-docx` / FastAPI are
absent.

1. **Gate + insertion** — with the global master env flag ON and a per-job opt-in
   set, one safe `fitz_local` `extracted_figure` candidate inserts **exactly one**
   markdown image.
2. **Safe ref shape** — the inserted ref is exactly the relative form
   `assets/<slug>.png` (never absolute, never a URL/`file://`).
3. **Generic caption** — the caption is the generic page-derived caption
   (`Extracted figure from source page N`), taken from the real production path
   where manifest captions are `None`; never raw OCR/source text.
4. **Unsafe refs rejected** — an otherwise-eligible figure carrying an unsafe
   `image_ref` inserts nothing; the pure `validate_visual_asset_ref` still rejects
   absolute / `..` / backslash / URL / data-URI / non-png / nested-subdir refs and
   accepts the one safe shape.
5. **Inputs immutable** — the source manifest JSON, replacement-plan JSON, and
   source PNG bytes are byte-identical after the pilot runs.
6. **HTML render** — the pilot's `clean.md` renders to HTML containing a safe
   relative `<img src="assets/...png">` and **no** absolute host path.
7. **PDF render** — completes and produces a non-empty PDF (SKIP only if Chromium
   is unavailable on the host).
8. **DOCX render** — embeds/degrades without raising and produces a non-empty file
   (SKIP only if `python-docx` is unavailable on the host).
9. **Export ride-along** — the export bundle includes exactly the **single**
   referenced PNG, under the job's `assets/` folder, as a safe relative entry, with
   the real image bytes.
10. **No over-export** — an unreferenced extra crop is **not** bundled; the whole
    `assets/` directory is **not** swept in.
11. **Requested-artifact gate** — `files_included` counts the requested artifacts
    only (pdf+markdown = 2); the ride-along PNG does not inflate it, and a
    pilot-PNG-only job with the requested artifact absent still `404`s (the PNG can
    never satisfy the gate by itself).
12. **Bundle index safety** — the manifest records only the safe relative
    `visual_pilot_asset` ref, never image bytes or absolute paths.
13. **No-leak sweep** — every serialized output the harness produced (inserted
    markdown, info dicts, HTML, bundle manifest) is swept for host paths, keys,
    tokens, `Authorization`/`Bearer`, sockets, data-URIs/base64, model / mmproj /
    executable / `.gguf` / `llama-server` markers, raw argv, and full URLs. None
    appear.

The chain is genuinely stitched: the export stage regenerates `clean.md` by running
the real `apply_visual_markdown_pilot` against a real `JobManager.Job` (opted in via
its persisted manifest) and writes it through `save_clean_md`, then exports that.

---

## What it does NOT prove

- It does **not** validate multi-figure behavior — there is none, by design.
- It does **not** exercise Chandra / Mistral / Gemini / any cloud or local OCR, any
  model/provider call, or any `llama-server` lifecycle. None are invoked.
- It does **not** test real-document figure extraction quality; the manifest/plan
  and PNG are synthetic, so it proves the *plumbing*, not extraction fidelity.
- It does **not** replace manual operator PDF review of a real guide.

---

## Data discipline

- **Synthetic, non-private data only.** Every PNG/PDF/DOCX/HTML/ZIP is written under
  a temp directory at runtime and removed when the test ends.
- **No committed binary / image / PDF / DOCX / ZIP fixture.** The test PNG is built
  at runtime by a tiny stdlib generator (`zlib` + `struct`) — not a committed file,
  not base64, not a data URI.
- **No provider / model / cloud calls.** The harness imports only existing pipeline
  helpers and (for the export stage) `api.server.export_bundle` driven against
  temp-dir jobs with `_get_job` monkeypatched.
- **No raw bytes / secrets in output.** Image bytes, host paths, tokens, headers,
  argv, model/mmproj/executable paths, provider payloads, OCR dumps, data-URIs, and
  full URLs never appear in printed output or assertions; a final sweep enforces it.

---

## Status of manual operator PDF validation

- `manual_operator_pdf_validation: not_run`
- Reason: `non_private_operator_sample_not_supplied` — no non-private real-document
  operator sample was provided for this slice, so a real-guide PDF was not produced
  or reviewed here. The synthetic render checks (PDF/HTML/DOCX non-empty + safe
  relative ref) stand in for plumbing correctness only.
- **Chandra extraction integration remains blocked by Slice 45 `status:not_run`.**

---

## Running it

```bash
# Always-on stages on the host (DOCX + export SKIP without python-docx / FastAPI):
python test_scripts/test_visual_pilot_e2e_validation.py

# Full coverage inside the running container (lean image, copy to /tmp, remove after):
CID="$(docker compose ps -q app)"
docker cp test_scripts/test_visual_pilot_e2e_validation.py "$CID":/tmp/test_visual_pilot_e2e_validation.py
docker compose exec -T app sh -lc 'PYTHONPATH=/app python /tmp/test_visual_pilot_e2e_validation.py'
docker compose exec -T app rm -f /tmp/test_visual_pilot_e2e_validation.py
```
