# LARGE_PDF_PREFLIGHT_DESIGN.md — Large-PDF upload preflight (DESIGN ONLY)

> **Status: design only. No code in this slice.** This document proposes a safe
> large-PDF *preflight* system. It does **not** change upload limits, the
> extraction/OCR pipeline, the renderer, or any existing behavior. It exists so a
> future implementation slice starts from an agreed shape. See §10 for the
> recommended first (small) implementation slice and §11 for explicit non-goals.

---

## 0. Why this exists

Large or scanned PDFs are slow, expensive, or risky to process. Today the only
guards are size/count caps that **reject** a file with a flat error, and a
character-truncation cap that **silently drops the tail** of a long deck mid-job.
There is no step that *inspects* a PDF and lets the user make an informed choice
*before* the expensive work begins.

The goal is to let the app eventually say:

> "This PDF is 64 MB and appears image-based. OCR may take a long time. Choose:
> [Process first 20 pages] [Choose page range] [Split automatically] [Continue anyway]"

The crucial design stance (per the task): **the first implementation must not try
to "support huge PDFs fully."** It should add the *inspection + warning* layer
only, and reuse the existing page-level extraction unchanged.

---

## 1. Current behavior summary

Verified by reading `api/server.py`, `pipeline/extract.py`,
`pipeline/run_llm_job.py`, and `frontend/src/components/BuilderWorkspace.jsx`.

### 1.1 Upload / job-creation paths
- `POST /api/jobs/paste` — pasted text (no files; **not capped**).
- `POST /api/jobs/upload-markdown` — a single `.md`/`.markdown` file only
  (`api/server.py:1231`). PDFs are rejected here.
- `POST /api/jobs/llm` — multipart form; this is the **only path that accepts
  PDFs**, as LLM *attachments* (`api/server.py:1264`, parsed in
  `_parse_llm_request` at `:2680`, saved in `_save_llm_attachments` at `:2757`).

There is **no preflight / inspect step**. A PDF goes straight from upload into
job creation and full extraction.

### 1.2 Existing limits (the current "guards")
- `MAX_LLM_ATTACHMENTS = 5` (`api/server.py:81`).
- `MAX_LLM_ATTACHMENT_BYTES = 15 * 1024 * 1024` (15 MB) (`api/server.py:82`),
  enforced *while streaming* the upload in `_save_llm_attachments`
  (`api/server.py:2772`) — over-limit raises a flat `400`.
- `MAX_ATTACHMENT_CHARS` (default `200000`) and `MAX_TOTAL_ATTACHMENT_CHARS`
  (default `600000`) — **already `os.getenv`-configurable** in
  `pipeline/run_llm_job.py:18-19`. These clip/skip extracted text *after*
  extraction (`_attach_sources`, `:191-214`), emitting a per-file truncation
  warning. (Note: an older memory cites 40k/120k defaults — the code now uses
  200k/600k via env; treat the code as authoritative.)

So the *byte* cap is a hard reject; the *char* caps are a silent-ish truncation
with a warning. Neither inspects page count or scanned-ness, and neither offers a
choice.

### 1.3 PDF extraction & OCR (do not rewrite — see §11)
`pipeline/extract.py` `_extract_pdf` (`:105`):
- Opens with **PyMuPDF (`fitz`)**; PyMuPDF is **Docker-only** in this project
  (not in the host venv — see the generator-presets follow-up memory).
- **Page-level** text-vs-OCR fallback: each page uses embedded text *or* OCR,
  never both. `_is_meaningful_page_text` (`:197`) gates a page as "real text"
  when it has `>= 40` chars **or** `>= 5` word tokens; otherwise the page is
  OCR'd individually.
- Each kept page is prefixed with a `## Page {N}` anchor; blank pages are dropped
  without shifting numbering.
- OCR availability is probed once via `_ocr_available()` (`:212`): needs the
  `tesseract` binary + `pytesseract` + `Pillow`. When unavailable it adds a
  single user-facing warning and skips OCR.
- Returns `ExtractionResult(text, mode, warnings)` where `mode` ∈
  `{pdf_text, pdf_ocr, pdf_mixed}`.

### 1.4 What lands in `job.json` today
`_attach_sources` records per-file: `filename`, `original_filename`, `path`,
`status` (`extracted`/`warning`/`skipped`/`failed`/`pending`), `mode`,
`extracted_chars`, `truncated`, `warnings`; plus job-level `extraction_warnings`
and `total_extracted_chars`. The API sanitizes these via
`_safe_attachment_metadata` / `_attachment_summary` (`api/server.py:2538`,
`:2592`) for the UI.

### 1.5 Frontend upload controls
`BuilderWorkspace.jsx`: `AttachmentsPicker` (`:2316`) — a file input with
`accept=".txt,.md,.markdown,.csv,.tsv,.docx,.pptx,.pdf"`, "max 5 files"
(`:2336/2341`), `addFiles` / `removeFile`, holding an `attachments` array in
component state, submitted as multipart by `api/client.js`. There is **no
size/page warning, no inspection, no page-range control** anywhere in the UI.

### 1.6 Config pattern in use
Two established patterns, both fine to reuse (§5 picks one):
- Module-level constants in `api/server.py` (e.g. `MAX_LLM_ATTACHMENTS`).
- `os.getenv("NAME", "default")` read at import in pipeline modules
  (`run_llm_job.py:18-19`). **This is the precedent for tunable limits** and is
  what the preflight thresholds should follow.

---

## 2. Proposed user flow

The preflight is a **lightweight, read-only inspection** that runs *before* the
user commits to a full generation job. It does **not** create a job.

```
User adds a PDF in the Builder AttachmentsPicker
          │
          ▼
Frontend calls POST /api/preflight/pdf  (the file bytes, no job created)
          │
          ▼
Backend inspects (open with fitz, page count, per-page quick text probe,
file size) and returns a verdict + warnings + allowed actions
          │
   ┌──────┴───────────────────────────────────────────────┐
   │ verdict = ok            │ verdict = warn / blocked      │
   ▼                          ▼
No banner; attachment      Show a warning banner with the choices:
behaves exactly as today.  [Process first N] [Choose range]
                           [Split automatically*] [Continue anyway]
                           [Remove file]
          │
          ▼
User picks an action → the choice is stored on the attachment in Builder state
          │
          ▼
On Generate, the existing POST /api/jobs/llm carries the chosen page-range
(or "all") alongside the file. Extraction later honors it (§6).
```

`*` "Split automatically" is shown but **deferred** in early slices (see §8/§10);
until implemented it can be hidden or disabled with a "coming soon" affordance.

Key properties:
- **Preflight never blocks small/ordinary PDFs.** If verdict is `ok`, the user
  sees nothing new — zero behavior change for the common case.
- **Preflight is advisory for `warn`.** "Continue anyway" is always available
  unless the file is genuinely unprocessable (encrypted/corrupt) or exceeds a
  hard ceiling.
- **Preflight is cheap.** It must not run full OCR; it samples (§3.4).

---

## 3. Proposed backend API shape

### 3.1 Endpoint
`POST /api/preflight/pdf` — multipart form, field `file` (a single PDF).
- New route, registered with the other explicit `/api/*` routes **before** the
  static mount (per CLAUDE.md ordering rule).
- Read-only: **creates no job, writes nothing persistent**, deletes its temp file
  in a `finally` (mirrors `_save_llm_attachments` / upload-markdown temp handling).
- Reuses the existing streaming size guard so it cannot be used to smuggle a file
  bigger than the upload ceiling.

> Single-file by design: the picker allows up to 5 attachments, but preflight
> targets the *one* file the user just added. The frontend calls it per added PDF.

### 3.2 Response shape (proposed)
```jsonc
{
  "ok": true,                       // request succeeded (not the verdict)
  "filename": "lecture-12.pdf",
  "content_type": "application/pdf",
  "file_size_bytes": 67108864,
  "file_size_mb": 64.0,
  "page_count": 412,

  // Sampled estimate (see §3.4) — explicitly approximate.
  "estimate": {
    "sampled_pages": 20,            // how many pages were probed
    "text_pages_est": 41,          // extrapolated count with usable embedded text
    "ocr_pages_est": 371,          // extrapolated count that would need OCR
    "image_ratio_est": 0.90,       // fraction of sampled pages with no real text
    "is_estimate": true
  },

  "scanned_flag": "image_heavy",    // "text" | "mixed" | "image_heavy"
  "recommended_mode": "first_n",    // see §3.3
  "ocr_available": true,            // mirrors _ocr_available()

  "verdict": "warn",                // "ok" | "warn" | "blocked"
  "warnings": [
    "This PDF is 64 MB and appears image-based (≈90% of sampled pages have no text layer).",
    "OCR would run on an estimated 371 pages and may take a long time.",
    "Large source — extracted text may be truncated to the configured limit."
  ],
  "allowed_actions": [              // drives which buttons the UI shows
    "first_n", "page_range", "continue", "remove"
    // "split" omitted until implemented (§8)
  ],
  "limits": {                       // echo of effective config (§4), for the UI copy
    "max_upload_mb": 64,
    "ocr_page_limit": 60,
    "warn_pages": 80,
    "warn_size_mb": 25,
    "default_first_n": 20
  }
}
```

Failure / unprocessable cases return `verdict: "blocked"` with `ok: true` (the
*request* worked, the *file* is the problem) and a single clear `warnings[0]`, or
a `400` for a non-PDF / oversize file (reusing the existing error style). See §7.

### 3.3 `recommended_mode` values
- `"full"` — small/text PDF; process the whole thing (no banner needed).
- `"first_n"` — large/scanned; suggest the first N pages.
- `"page_range"` — large but the user likely wants a specific section.
- `"split"` — *recommendation only*; UI may show it disabled until implemented.

### 3.4 How the estimate stays cheap (no full OCR)
The estimate **must not** OCR the document. Proposed sampling:
1. Open with `fitz`; read `page_count` (O(1)).
2. Probe a **bounded sample** of pages (e.g. first K, evenly spaced K, default
   `K = min(page_count, PREFLIGHT_SAMPLE_PAGES=20)`), calling only
   `page.get_text("text")` + the existing `_is_meaningful_page_text` gate — the
   *same* gate extraction uses, so the estimate matches real behavior.
3. `text_ratio = meaningful_sample / sampled`; extrapolate to `page_count`.
4. `scanned_flag`: `text` if `image_ratio < ~0.15`, `image_heavy` if
   `> ~0.85`, else `mixed`. (Thresholds are constants, tunable later.)

This is a few milliseconds of `get_text` calls, never a rasterize/OCR pass, so
preflight is safe to run on every added PDF.

---

## 4. Proposed config / env variables and defaults

Follow the existing `os.getenv(...)` precedent in `run_llm_job.py`. Proposed new
knobs (names indicative; all read once at import, all overridable via env):

| Variable | Default | Meaning |
|---|---|---|
| `MAX_UPLOAD_MB` | `15` (current `MAX_LLM_ATTACHMENT_BYTES` ÷ 1 MB) | **Unchanged in this design** — hard reject ceiling. Listed only so preflight can *report* it; raising it is out of scope (§11). |
| `PREFLIGHT_SAMPLE_PAGES` | `20` | Pages sampled for the text/scanned estimate. |
| `PREFLIGHT_WARN_PAGES` | `80` | Page count above which verdict ≥ `warn`. |
| `PREFLIGHT_WARN_SIZE_MB` | `25` | File size above which verdict ≥ `warn`. |
| `PREFLIGHT_OCR_PAGE_LIMIT` | `60` | Est. OCR pages above which the OCR-time warning fires (and, later, a soft cap on OCR work). |
| `PREFLIGHT_DEFAULT_FIRST_N` | `20` | Default N for the "Process first N pages" action. |
| `PREFLIGHT_IMAGE_HEAVY_RATIO` | `0.85` | image_ratio above which `scanned_flag = image_heavy`. |
| `PREFLIGHT_TEXT_RATIO` | `0.15` | image_ratio below which `scanned_flag = text`. |

Existing `MAX_ATTACHMENT_CHARS` / `MAX_TOTAL_ATTACHMENT_CHARS` stay as-is;
preflight may *reference* them to phrase the truncation warning, but does not
change them.

> Defaults are deliberately conservative for personal/small-group use. A 412-page
> 64 MB scan trips every warn threshold; a 12-page lecture handout trips none.

---

## 5. Proposed request shape for page ranges

The chosen action travels with the *generation* request, not preflight. Preflight
is stateless; the Builder remembers the choice and sends it on Generate.

### 5.1 Representation
A compact, validated **page-selection spec per attachment**:
```jsonc
{
  "mode": "first_n" | "range" | "all",
  "first_n": 20,                 // when mode = first_n
  "ranges": [[1, 20], [50, 75]]  // when mode = range; 1-based, inclusive, ordered
}
```
- `all` is the implicit default → **identical to today's behavior** (key for
  backward compatibility).
- Page numbers are **1-based and inclusive**, matching the `## Page N` anchors
  users already see in output.
- Ranges are normalized server-side: clamp to `[1, page_count]`, drop/merge
  overlaps, cap the count of ranges (e.g. ≤ 20) to bound input.

### 5.2 How it rides on `POST /api/jobs/llm`
The endpoint is already multipart and tolerant of JSON-in-form fields (see
`outline` / `include_sections` handling in `_parse_llm_request`). Add **one
optional field** the same way: `page_selections` — a JSON object keyed by
filename (or attachment index) → the spec above. Absent/empty ⇒ `all` ⇒ today's
path. No change to non-PDF attachments, paste, or markdown upload.

```
page_selections = {"lecture-12.pdf": {"mode": "first_n", "first_n": 20}}
```

---

## 6. How selected page ranges flow into extraction later

This is the part that touches the load-bearing extractor, so it is designed to be
**additive and opt-in** — when no selection is given, `_extract_pdf` runs exactly
as it does today.

Proposed (for a *later* slice, not slice 1):
1. `AttachmentSource` (or the `_attach_sources` call) carries an optional
   `page_selection` for that file.
2. `extract_file` / `_extract_pdf` gain an optional `pages: Iterable[int] | None`
   parameter. When `None` → current behavior unchanged. When provided → the
   per-page loop simply **iterates only the selected page indices** (`fitz`
   supports `document[i]` / `pages=` selection), keeping the exact same
   text-vs-OCR per-page logic and `## Page N` anchoring (anchors keep their
   *original* page numbers so citations stay correct).
3. Modes (`pdf_text`/`pdf_ocr`/`pdf_mixed`) and warnings are computed over the
   processed subset, unchanged otherwise.

No new extraction algorithm; just a page filter in front of the existing loop.
"Split automatically" would be built *on top* of this (multiple sub-jobs or a
chunked single job) and is explicitly deferred (§8).

---

## 7. Behavior per PDF kind

| Kind | Detection | `scanned_flag` / `verdict` | What preflight says / offers |
|---|---|---|---|
| **Text PDF** (normal) | sample mostly passes `_is_meaningful_page_text`; size & pages under thresholds | `text` / `ok` | Nothing — silent pass, attachment behaves as today. |
| **Scanned PDF** (image-only) | sample mostly fails the gate | `image_heavy` / `warn` | "Appears image-based; OCR may take a long time." Offer first-N / range / continue. If `ocr_available=false`, warn that OCR is unavailable so a scan would yield little/no text. |
| **Mixed text/scanned** | sample is split | `mixed` / `warn` (only if also large) | "Mix of text and scanned pages." Offer range; note that scanned pages will be OCR'd. |
| **Encrypted / password** | `fitz` reports `needs_pass` / open fails on auth | `blocked` | "This PDF is encrypted/password-protected and can't be read. Remove it or upload an unlocked copy." No actions except Remove. |
| **Broken / corrupt** | `fitz.open` raises | `blocked` | "This file couldn't be opened — it may be corrupt or not a real PDF." (mirrors existing `_extract_pdf` corrupt message). Remove only. |
| **Huge PDF** | size > `MAX_UPLOAD_MB` | `400` at upload guard (reused) | Flat reject (today's behavior) — but the warning copy explains the ceiling and suggests splitting externally. *Within* the ceiling but over warn thresholds ⇒ `warn`, not reject. |
| **Unsupported file** (non-PDF sent to this endpoint) | suffix / magic check | `400` | "Preflight only inspects PDFs." (other types skip preflight entirely on the frontend). |

Preflight degrades gracefully: if `fitz` import fails or any inspection step
throws unexpectedly, return `verdict: "ok"` with a soft note ("couldn't inspect
this PDF; it will be processed normally") so preflight can **never block a file
that would otherwise have worked**.

---

## 8. Risk analysis

- **Touching the load-bearing extractor (R1).** Page-range support modifies
  `_extract_pdf`. *Mitigation:* additive `pages=None` default = byte-for-byte
  current behavior; ship preflight *inspection* (slice 1) with **no** extractor
  change at all, and gate the page-filter behind explicit selection in a later
  slice.
- **Cost/latency of preflight itself (R2).** Inspecting every PDF could be slow.
  *Mitigation:* sampling (§3.4), never OCR in preflight, hard cap on sampled
  pages. Reading `page_count` + ~20 `get_text` calls is cheap.
- **PyMuPDF is Docker-only (R3).** Preflight depends on `fitz`, absent on the
  host. *Mitigation:* same as extraction today; guard the import and degrade to
  `verdict: ok` if missing. Verify in Docker (where fitz exists).
- **Estimate vs reality mismatch (R4).** Sampled extrapolation can be wrong.
  *Mitigation:* label everything `is_estimate`, phrase as "appears"/"estimated",
  reuse the *same* `_is_meaningful_page_text` gate so the estimate tracks actual
  extraction, never present counts as exact.
- **Double upload bandwidth (R5).** Preflight + generation each send the file.
  *Mitigation:* acceptable for personal/small-group scale; if it matters later,
  cache the temp file by content hash for the job request (deferred, not now).
- **Security / DoS via preflight (R6).** A new file-accepting endpoint.
  *Mitigation:* reuse the existing streaming size guard and temp-file cleanup;
  single file only; read-only, persists nothing; no path the user controls.
- **Scope creep into splitting/chunking (R7).** The flashy part is automatic
  splitting. *Mitigation:* explicitly deferred (§10/§11); "Split automatically"
  is a disabled/"coming soon" affordance until its own slice.
- **UI noise / false alarms (R8).** Over-warning trains users to ignore banners.
  *Mitigation:* conservative thresholds, silent `ok` path, single concise banner,
  "Continue anyway" always one click away.

---

## 9. Deferred items (future work, not this design)

- **Automatic split / chunk processing** into multiple sub-jobs or a chunked
  single job (the heaviest piece).
- **Hybrid embedded-text + OCR dedup** on a single page (using both layers and
  de-duplicating) — explicitly out of scope per the task; the current per-page
  XOR (text *or* OCR) stays.
- **Page-range *flow into extraction*** (`pages=` filter in `_extract_pdf`) — the
  §6 mechanism is designed but not built in slice 1.
- **Raising the actual upload ceiling** (`MAX_UPLOAD_MB`) — out of scope; design
  only reports it.
- **Content-hash temp reuse** to avoid double upload (R5).
- **Preflight for non-PDF types** (huge `.docx`/`.pptx`) — PDFs first.
- **Persisted preflight verdict** in `job.json` for the chosen file (see §9.1) —
  belongs with the page-range slice, not the inspect-only slice.
- **Per-provider page/char budgets** derived from the model context window
  (relates to the existing `MAX_ATTACHMENT_CHARS` follow-up).

### 9.1 What to log later (in `job.json` / attachment metadata)
When page-range selection ships, extend the existing per-attachment entry
(§1.4) — do **not** invent a new store — with:
- `page_selection`: the normalized spec actually applied (`{mode, first_n,
  ranges}`).
- `pages_total`: the PDF's full page count.
- `pages_processed`: how many pages were actually read.
- `preflight`: `{scanned_flag, text_pages_est, ocr_pages_est, verdict}` snapshot.
- Reuse the existing `warnings[]` for any "processed only N of M pages" note.
These flow through `_safe_attachment_metadata` (add the new fields there) so the
Job Details drawer can show "Processed 20 of 412 pages (scanned)".

---

## 10. Recommended first implementation slice (Slice 1)

**Slice 1 — backend PDF preflight endpoint only. No UI, no extractor change.**

> Add `POST /api/preflight/pdf` that accepts one PDF, and returns `file_size`,
> `page_count`, a sampled text-vs-scanned **estimate**, `scanned_flag`,
> `recommended_mode`, `verdict`, `warnings`, and `allowed_actions` — using the
> existing streaming size guard and temp-file cleanup, the existing
> `_is_meaningful_page_text` gate for the sample, and the existing
> `_ocr_available()` probe. Creates no job, writes nothing, changes no limits,
> and does not touch `_extract_pdf`.

Why this is the smallest safe step:
- **Zero behavior change** to any existing path — it's a brand-new, read-only
  route. The Builder doesn't call it yet, so nothing in the product changes.
- **Independently testable**: `curl -F file=@sample.pdf
  http://localhost:8000/api/preflight/pdf` in Docker, asserting the JSON shape on
  a text PDF, a scanned PDF, and an encrypted/corrupt PDF.
- It de-risks the inspection logic (sampling, thresholds, fitz guarding) before
  any UI or extractor work depends on it.

Suggested slice order after that:
- **Slice 2** — Frontend warning banner + actions in `AttachmentsPicker`
  (`first_n` / `range` / `continue` / `remove`), wired to call slice-1 endpoint;
  store the chosen `page_selection` in Builder state. Still no extractor change
  (selection is captured but `all` is what's sent until slice 3).
- **Slice 3** — Plumb `page_selections` through `POST /api/jobs/llm` and add the
  additive `pages=` filter to `_extract_pdf` (§6); log the selection in
  attachment metadata (§9.1).
- **Slice 4+** — Automatic split/chunking (deferred, §9).

---

## 11. Explicit non-goals (this design and slice 1)

- **No code changes in this slice** — this document is docs-only.
- **Not** raising `MAX_UPLOAD_MB` / `MAX_LLM_ATTACHMENT_BYTES` or any limit.
- **Not** rewriting or restructuring `_extract_pdf` / the OCR pipeline; slice 1
  doesn't touch it at all, later slices only add an opt-in page filter.
- **Not** implementing hybrid embedded-text + OCR dedup (kept per-page XOR).
- **Not** implementing automatic splitting / chunking / OCR orchestration.
- **No** changes to the renderer, sanitizer, prompts, provider settings, Local
  Model Manager, Library/exports, shortcut store, cancel logic, or dependencies.
- **No** new storage mechanism — reuse the existing `os.getenv` config precedent
  and the existing per-attachment `job.json` metadata when logging is added.
- Preflight **must never block a PDF that would otherwise process** — on any
  inspection failure it degrades to `verdict: ok`.

---

## 12. Verification (docs-only)

This change is documentation only. No build, compile, or Docker run is required.
Confirmed with:
- `git status` — only this new doc (plus, if added, a one-line docs index link).
- `git diff --stat` — additions confined to `docs/`.

**Confirmation: this slice is docs-only. No application code was changed, no
limits were modified, no extraction/OCR/renderer code was touched, and no old
branches were merged, rebased, or cherry-picked.**
