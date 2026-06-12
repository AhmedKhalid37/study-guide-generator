# CHANDRA_LIVE_HARNESS_VALIDATION.md — operator runbook + validation record (Slice 45)

> Docs-only gate/report slice. This document records **how to safely run** the
> Slice 44 Chandra live validation harness
> (`test_scripts/validate_chandra_local_provider_live.py`) and, if an operator
> has a local Chandra-capable `llama-server` available, records a **sanitized**
> live validation result. It is **not** integration: nothing here wires Chandra
> into production, and running the harness changes no app behavior.
>
> Companion docs: `docs/CHANDRA_GGUF_SPIKE_REPORT.md` (Slice 41, hands-on GGUF
> feasibility), `docs/CHANDRA_OCR_VERIFICATION.md` (Slice 39, paper feasibility),
> `docs/DECISIONS.md` → the Slice 42/43/44/45 Chandra entries.

---

## 1. Purpose

- Provide a **manual, opt-in** way for an operator to prove — *outside the
  production app flow* — that a local Chandra-capable, OpenAI-compatible
  `llama-server` **they started themselves** can accept one page image and return
  output that flows cleanly through the Slice 43 boundary:

  ```
  operator's local llama-server response
    → parse_chandra_chat_response(...)        (Slice 43)
    → normalize_chandra_chat_response(...)     (Slice 43 → Slice 42 normalizer)
    → safe, closed-vocabulary summary only
  ```

- It proves **only** the request / response / normalizer boundary. It is
  explicitly **NOT**:
  - production wiring (nothing in the app constructs or calls the provider),
  - extraction integration (`pipeline/extract.py` / OCR routing are untouched),
  - a release-smoke step (`smoke_release.py` does not run it).

- The harness reports a **closed-vocabulary summary only**. All model-*content*
  scrubbing is delegated to the Slice 42 normalizer; the harness additionally
  guarantees that none of its summary fields can carry raw content (source text
  is reported only as a character count).

---

## 2. Preconditions (operator-owned)

The harness performs a real HTTP request **only** when an operator runs the CLI
with their own `--endpoint` and `--image`. Before that:

- The operator **manually** starts a local, OpenAI-compatible, Chandra-capable
  `llama-server` (e.g. the GGUF + `--mmproj` setup from the Slice 41 spike). The
  app does **not** start, stop, or manage that server — see
  `docs/CHANDRA_GGUF_SPIKE_REPORT.md` for the spike setup that was used.
- The operator supplies **one non-private test image** of a single page
  (`png` / `jpg` / `jpeg` / `webp`). **Do not** use a private/student document
  for a recorded validation run.
- **Nothing operator-specific may be written into this doc.** Do **not** record a
  model path, `mmproj` path, executable path, raw launch command, full endpoint
  URL, port, query string, token, socket path, or the test image path/basename.
- The harness sends **no** auth header and accepts none; do not embed a token in
  the endpoint.

---

## 3. Safe run command template (placeholders only)

Run from the repo root. Use **placeholders** — never paste a real path, real
endpoint, real port, or a token into a doc or into chat:

```
python test_scripts/validate_chandra_local_provider_live.py \
  --endpoint "<local-openai-compatible-endpoint>" \
  --image "<non-private-test-image>"
```

Optional flags (still leak-safe): `--timeout <seconds>` (default 60),
`--verbose` (adds `elapsed_ms` only).

The CLI accepts either a base URL or a full chat-completions URL; it resolves the
concrete URL **internally** and never prints it. On stdout it emits only the
whitelisted summary described in §4.

---

## 4. Safe output policy

Only the closed-vocabulary summary may ever be recorded or pasted. The harness is
built so that the following can **never** appear in its summary or printed output;
do not add them by hand either:

- raw OCR text or any normalized `source_text` content,
- the raw provider response / payload,
- the test image path, basename, bytes, or any base64 / `data:` URI,
- a full URL, port digits, or query string (only a redacted
  `scheme://<host>:<port>/...` label is shown),
- request/response headers, `Authorization` / `Bearer` fragments, or tokens,
- a socket path, model path, `mmproj` path, or executable path / raw argv,
- any private document content.

The endpoint label is redacted via `urlsplit().hostname`, so a token embedded in
userinfo, path, or query cannot survive; unparseable/non-http(s) endpoints
collapse to `local_endpoint_supplied`.

---

## 5. Validation result

### 5.1 Recordable summary fields (when a live run is performed)

If a live server **and** a non-private image are available, run the harness by
hand and record **only** these sanitized fields:

- `reachable` / `request_ok` (true / false)
- `parse_status` (`none` / `ok` / `empty` / `malformed`)
- `normalized_kind` (expected `chandra_normalized_output`, else `null`)
- `normalized_status` (expected `completed`, else `null`)
- `source_text_char_count` (an integer count — **never** the text)
- `asset_count` (an integer count)
- closed-vocabulary `parse_warnings` / `normalize_warnings` tokens
- `failure_category` if any (`connection_failed` / `request_failed` /
  `response_malformed` / `provider_empty_content` / `normalization_failed` /
  `image_read_failed` / `invalid_endpoint`)
- `elapsed_ms` only if `--verbose` was used and it is safe to report.

Never paste the raw provider response or OCR text. Never fabricate fields.

### 5.2 This slice's recorded result

```
status: not_run
reason: operator_input_not_supplied
```

No live Chandra-capable `llama-server` endpoint and no non-private test image were
supplied during this docs-only slice, so **no live validation was performed** and
**no live HTTP request was made**. The Slice 44 harness was exercised only by its
automated fake-transport test suite (`test_scripts/test_chandra_live_harness.py`,
**96/0**), which injects handcrafted responses and never contacts a real server.
This is recorded honestly as `not_run`; no result was invented.

When an operator later runs the harness on real hardware with a non-private image,
append a dated sub-entry here with the §5.1 fields only.

---

## 6. Gate decision

This is a **gate** slice. The decision rule for the next Chandra step:

- **If a live validation run passes** (`request_ok: true`, `failure_category:
  null`, `normalized_kind: chandra_normalized_output`,
  `normalized_status: completed`, plausible `source_text_char_count` /
  `asset_count`): the recommendation is to **proceed to a still-disabled,
  off-by-default extraction-side adapter design slice** (see §7) — not to wire
  Chandra into production.
- **If live validation is not run or fails** (current state — `not_run`): **do
  not proceed** to the extraction adapter. Fix the harness / provider boundary or
  rerun validation first.

**Current gate state:** `not_run` → **the extraction-adapter slice remains
blocked** until a live run passes.

---

## 7. Future slice notes (not built here)

- **Next, only after a pass:** a **disabled / unwired** Chandra **extraction-side
  adapter** that consumes operator-provided page images and returns normalized
  output, still **not active in production** and off-by-default.
- **Fallback contract (unchanged):** Chandra unavailable / bad output / timeout →
  fall back to the existing local Tesseract / `fitz` path. **Degrade, not fail** —
  a Chandra problem must never fail a generation.
- **Later and higher-risk (separate slices):** asset-aware prompt assembly,
  visual embedding, and any render-pipeline change. None of these are in scope for
  the adapter slice.
