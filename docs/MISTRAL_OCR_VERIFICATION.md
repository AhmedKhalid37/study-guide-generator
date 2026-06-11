# MISTRAL_OCR_VERIFICATION.md — Cloud OCR prerequisite gate (Slice 35)

> **Docs-only verification.** This document evaluates **Mistral OCR / Document AI**
> as a *potential future* cloud OCR provider for GuideForge. It implements nothing.
> No code, dependency, provider setting, key, prompt, routing, or extraction change
> is part of this slice. Treat this as the prerequisite gate that must pass *before*
> any cloud-OCR implementation slice is designed.
>
> **Status of facts:** gathered from official / primary Mistral sources (see
> §10) in **June 2026**. Mistral OCR is versioned and GA, and Mistral has shipped a
> newer revision since the original announcement — **re-confirm model id, pricing,
> and limits against the live docs at implementation time.** The repo remains the
> source of truth for *our* side; the cloud product is the source of truth for *its*.
>
> **No secrets policy:** this document records source URLs and product facts only.
> It contains **no** API keys, `Authorization` headers, tokens, account ids, socket
> paths, host paths, or document contents — and any future implementation must keep
> all of those server-side only (see §7 and §8).

---

## 1. Product / API status

- **Available?** Yes. Mistral OCR is **Generally Available** on Mistral's developer
  platform ("la Plateforme" / Mistral AI Studio) and via the API. It is also offered
  through partner clouds (e.g. Google Cloud Vertex AI as *Mistral OCR (25.05)*).
- **Stability / lifecycle:** GA, but **versioned and actively iterated.** There is
  an original Mistral OCR generation and a newer **Mistral OCR 3** (GA **2025-12-17**).
  Because it is a moving product, treat model id, pricing, and limits as
  **subject to change** and re-verify before coding.
- **Model / endpoint:**
  - **Endpoint:** `POST https://api.mistral.ai/v1/ocr`
    (official SDK surface: `client.ocr.process(...)`).
  - **Model ids seen:** `mistral-ocr-latest` (rolling alias), and the pinned
    `mistral-ocr-2512` (Mistral OCR 3, released 2025-12-17). Vertex AI exposes
    *Mistral OCR (25.05)*.
  - **Recommendation:** if we ever implement, **pin an explicit dated model id**
    (e.g. `mistral-ocr-2512`) rather than the `-latest` alias, so behaviour and
    pricing don't shift under us silently. (Mirrors how we treat LLM provider
    models — explicit, server-resolved.)

---

## 2. Request format

| Aspect | Finding |
| --- | --- |
| **Endpoint / method** | `POST /v1/ocr` (HTTPS). SDK wrapper: `client.ocr.process()`. |
| **Auth (high level)** | API-key bearer token on the request, standard Mistral API key. **Server-side only** for us — never in the browser, DTOs, logs, or artifacts. |
| **Input — public URL** | `document` = `{"type": "document_url", "document_url": "<public URL>"}` for **PDF / PPTX / DOCX**; `{"type": "image_url", "image_url": "<public URL>"}` for images (**PNG / JPEG / AVIF**). |
| **Input — base64** | Base64-encoded document/image variants supported (data URI form). This is the relevant path for us: GuideForge uploads are local, not public URLs. |
| **Input — uploaded file** | Cloud file-upload (file ids) supported via Mistral's files API. |
| **Max file size** | **50 MB** per document. |
| **Page limit** | **≤ 1,000 pages** per document. |
| **Throughput (vendor claim)** | Up to **~2,000 pages/min** on a single node. |
| **Batch support** | Yes — a **Batch API** path (asynchronous) at a **50% discount** vs the synchronous rate. |
| **Sync vs async** | `/v1/ocr` is synchronous/per-request; the **Batch API** is the asynchronous bulk path. |
| **Other request fields seen** | `table_format` (`null` \| `"markdown"` \| `"html"`), `extract_header`, `extract_footer`, `include_image_base64`, `confidence_scores_granularity` (`"page"` \| `"word"`), and a `pages` selector. |

**GuideForge-relevant note:** our documents are operator uploads on a non-public
backend. The natural integration path is **base64 / file-upload**, *not* public
`document_url` (we must not expose a public URL to a student's notes). This matters
for §7.

---

## 3. Response / output format

Per the OCR processor docs, the response is structured roughly as:

```jsonc
{
  "pages": [
    {
      "index":  /* int, page index */,
      "markdown": /* str — page content as Markdown */,
      "images": /* list — embedded figures (base64 only if include_image_base64) */,
      "tables": /* list — extracted tables */,
      "hyperlinks": /* list */,
      "header": /* str | null */,
      "footer": /* str | null */,
      "dimensions": /* dict — page width/height/dpi */,
      "confidence_scores": /* dict | null — granularity page|word */
    }
  ],
  "model": "str",
  "document_annotation": /* dict | null — structured-output / annotations */,
  "usage_info": /* dict — page/usage accounting */
}
```

- **Text output:** **Markdown per page** (interleaved text + image references).
  This is a *good* structural fit for GuideForge, which already thinks in
  Markdown + `## Page N` anchors.
- **Tables:** reconstructed; `table_format` can request Markdown or **HTML** (Mistral
  OCR 3 uses HTML table tags incl. `colspan`/`rowspan` for merged cells/hierarchies).
- **Images / figures:** extractable; base64 returned only when
  `include_image_base64` is set.
- **Layout coordinates / bounding boxes:** page **dimensions** are returned; richer
  layout/annotation data is available via the annotations/structured-output path.
- **Confidence scores:** available, with **page** or **word** granularity (`null`
  unless requested).
- **Per-page output:** yes — `pages[]` indexed, which maps cleanly to our existing
  per-page extraction model.
- **Error payload:** standard Mistral API JSON error envelope (HTTP status + error
  body). **Exact field shape not pinned here** — see §9 unknowns; must be confirmed
  and **sanitised to safe category tokens** before surfacing (never raw to UI/logs).

---

## 4. Pricing / cost

| Generation | Standard | Batch API (−50%) |
| --- | --- | --- |
| Original Mistral OCR (`-latest` historically) | **~$1 / 1,000 pages** (≈1,000 pages per $1) | ~$0.50 / 1,000 pages |
| **Mistral OCR 3** (`mistral-ocr-2512`) | **~$2 / 1,000 pages** | ~$1 / 1,000 pages |

- **Billing unit:** **per page** (not per token / per request). Predictable and easy
  to estimate from a PDF's page count — a real advantage for budgeting.
- **Free tier:** Mistral offers a limited free/experimentation tier; production OCR
  realistically needs the paid **Scale** plan. **Free-tier OCR quotas for this exact
  endpoint are not pinned here** (see §9).
- **Practical implication for study PDFs:** even a large 1,000-page document is on
  the order of **$1–$2** (standard) — cheap in absolute terms. The risk is **not**
  unit price but **volume × automation**: routing every page of every upload to cloud
  by default would accumulate cost and send every document off-box. This is exactly
  why our Slice 33/34 policy is **local-first, cloud-off by default, page-budgeted**.
- **Uncertainty requiring operator confirmation:** which generation the `-latest`
  alias bills as at implementation time, and whether OCR 3's **$2/1,000** is the rate
  we'd actually incur. **Operator must confirm the live price before enabling.**

---

## 5. Rate limits & reliability

- **Limit model:** Mistral enforces **requests/second (RPS)**, **tokens/minute**, and
  **tokens/month**, **per API key** (not per workspace); RPS and TPM enforced
  independently.
- **Tiers:** Free mode (testing) with low caps; **Scale** plan unlocks Tier 1+ which
  upgrade automatically with cumulative spend (third-party figures suggest free ≈ 5
  RPS burst ~10, paid starting ≈ 50 RPS — **treat as indicative, confirm in
  dashboard**). Tier 4 (≥ ~$2,000 billed) can request higher limits via support.
- **Throughput:** vendor claims ~2,000 pages/min/node; large docs should use the
  **Batch API** to stay within sync limits and get the discount.
- **Retries / timeouts:** standard HTTP semantics; **429 (rate limit)** and
  **5xx** require client-side backoff/retry. Specific server timeout values are
  **not pinned here** (see §9) — any client must set its own request timeout and a
  bounded retry policy.
- **Common error cases to design for:** 401/403 (bad/absent key), 413 / limit
  exceeded (> 50 MB or > 1,000 pages), 422 (bad input/unsupported type), 429 (rate),
  5xx (transient). All must map to **safe category tokens** and **fall back to local
  OCR** rather than failing a generation.

---

## 6. Privacy / data handling

- **Training:** Mistral states **API input/output is not used for model training**
  (paid API is opted out by default; even free *API* usage is excluded — the
  training opt-in default applies to free *Le Chat*, not the API). Good.
- **Retention:** API inputs/outputs are retained for the time needed to serve the
  request **plus a rolling 30-day abuse-monitoring window**, unless **Zero Data
  Retention (ZDR)** is active.
- **ZDR:** available **only on the Scale plan** and **only for stateless API calls**
  (not for stateful products — batch files, agents, conversations, libraries, etc.).
  `/v1/ocr` synchronous calls are stateless and could qualify; the **Batch API path
  stores files and would not get ZDR** — a meaningful trade-off (batch is cheaper but
  retains).
- **Self-hosting:** Mistral offers **selective self-hosting of OCR** for organisations
  with highly sensitive/classified data — not relevant to our single-operator scale,
  but worth noting as the maximal-privacy option.
- **Compliance:** Mistral publishes a Privacy Policy and a Data Processing Addendum
  (DPA).
- **Acceptable for student notes?** **Conditionally.** Sending student notes to a
  third party is a real privacy posture change from today's fully-local OCR. It is
  defensible **only** if: (a) it is **explicit opt-in**, off by default; (b) the
  operator has read/accepted Mistral's retention/DPA terms; (c) ideally ZDR is on
  (Scale, stateless `/v1/ocr`); and (d) we never expose the document via a public
  URL. **Red flag:** the default 30-day retention without ZDR, and the batch path's
  file storage. **Unresolved:** whether this specific operator is comfortable with
  any third-party processing of student material at all (see §9).

---

## 7. Fit with GuideForge architecture

The good news: **Slices 32–34 already built the seams.** No architectural surprises.

- **Slice 32 OCR provider boundary (`pipeline/ocr_provider.py`):** defines
  `OcrProvider` (stable `provider_id`, availability probe `(ready, reason)`,
  per-page `ocr_page → OcrResult`) and the JSON-safe `OcrResult` (text, provider id,
  optional confidence, **safe warning/error *category* tokens only** — never bytes,
  paths, URLs, keys, or raw provider error strings). A future
  `MistralCloudOcrProvider` would implement this same contract. The doc's
  degrade-not-fail / cloud→local-fallback shape is **already part of the boundary
  design** for exactly this.
- **Slice 33 routing policy (`pipeline/ocr_routing.py`):** already has the
  `cloud_ocr_candidate` action and `allow_cloud_ocr` config (hard-`False` today).
  It emits a cloud *candidate* **only** when `allow_cloud_ocr` is true **and** local
  OCR cannot serve the page, and it **never** sets a cloud provider id (`provider`
  stays `None` because no cloud provider exists yet). It also enforces a **shared
  page budget** across OCR work. A cloud OCR slice flips this from "advisory
  candidate" to "actually dispatch to the Mistral provider" — gated by the same flag
  and budget.
- **Slice 34 extraction wiring (`pipeline/extract.py`):** records the advisory route
  per page (`ocr_route_*` fields) with `allow_cloud_ocr=False` and local-only
  provider ids. Cloud would extend this from *recorder* to *router* **only** under an
  explicit opt-in, preserving local-first default and page budgets.

**Desired behaviour for any future cloud OCR slice:**
- **Local-first default; cloud only when explicitly allowed** (`allow_cloud_ocr`
  driven by a server-side, opt-in OCR provider setting).
- **Page-budget limited** (reuse the Slice 33 shared budget — never "every page to
  cloud").
- **Always fall back to local Tesseract** on any cloud error / limit / timeout — a
  generation must never fail because cloud OCR was unavailable.
- **Base64 / file-upload input**, never public `document_url` for operator documents.

**Metadata fields that *might* be added later** (additive, JSON-safe, closed-vocab —
consistent with the Slice 30/31/34 "additive page fields, no version bump unless
first new field" rule):
- `ocr_route_provider` extended to allow a **cloud provider id** (e.g.
  `"mistral_cloud"`) — currently only `"tesseract_local"` / `null`.
- `ocr_provider_status` (e.g. `ok` / `fell_back_local` / `cloud_disabled`).
- `ocr_cloud_cost_estimate` (pages × rate, **estimate only**, no billing secrets).
- `ocr_confidence` (if we request confidence scores).
- `ocr_route_warnings` extended with safe cloud categories
  (`cloud_rate_limited`, `cloud_timeout`, `cloud_file_too_large`, etc.).

**Must remain server-side only (never in DTOs/UI/logs/artifacts/exports):** the API
key, `Authorization` header, raw provider error strings/bodies, full request URLs
with parameters, any public/temporary document URL, uploaded-document paths, and
account/billing identifiers. The public surface gets only **derived, non-secret**
info — mirroring the existing provider-settings DTO posture (`configured`,
`key_source`, last-4 `key_hint`, host-only) and the LMM whitelisting rules.

---

## 8. Implementation risks

| Risk | Notes / mitigation |
| --- | --- |
| **Cost surprises** | Per-page billing is predictable, but auto-routing volume isn't. Mitigate with cloud-off default, explicit opt-in, page budget, and a pre-flight page-count cost estimate shown to the operator. Confirm OCR-3 `$2/1,000` vs original `$1/1,000` at implementation. |
| **Privacy** | Third-party processing of student notes is a posture change. Mitigate with opt-in, operator acceptance of DPA, prefer ZDR (Scale + stateless `/v1/ocr`), avoid the retaining batch path for sensitive docs, and never use public document URLs. |
| **File / page limits** | 50 MB / 1,000 pages per doc. Our large-PDF preflight already exists; cloud OCR must respect these and fall back/split rather than error. |
| **Output mismatch** | Mistral returns per-page Markdown — close to our model — but we must map its `pages[]`/tables/images into our `## Page N` + sanitiser pipeline without breaking byte-stable local behaviour or the render pipeline. Table HTML vs Markdown choice needs a decision. |
| **Rate-limit / timeout handling** | Per-key RPS/TPM; must add bounded retry/backoff + request timeout + local fallback. Batch API for bulk. |
| **Dependency / client choice** | Official `mistralai` Python SDK vs a thin `httpx`/`requests` call. **Adding a heavy SDK conflicts with our "no casual dependency" posture** — a minimal direct HTTPS client may be preferable. Decide in the implementation-design slice. |
| **Offline / local-first expectation** | The app is explicitly local-first (Ask is local-only; OCR is local today). Cloud OCR must be **opt-in and clearly off by default**, never silently routing data off-box. |
| **Model drift** | `-latest` alias can change behaviour/price. Pin a dated model id. |

---

## 9. Unknowns / unresolved risks

To confirm against live docs **before** any implementation slice:

1. **Exact billing for `-latest`** at implementation time (original `$1/1,000` vs
   OCR-3 `$2/1,000`) — **operator must confirm price.**
2. **Free-tier quota** specifically for `/v1/ocr` (pages/day or RPS).
3. **Exact error-payload schema** and the full set of error codes/messages.
4. **Server-side timeout values** and recommended retry/backoff guidance.
5. **ZDR eligibility for `/v1/ocr`** confirmed in the operator's own account/plan
   (and confirmation that the **batch path retains** files).
6. **Whether the operator accepts any third-party processing** of student notes at
   all — a product/policy decision, not a technical one.
7. **Base64 size overhead** vs the 50 MB limit (base64 inflates ~33%).
8. Whether annotations/structured-output (extra cost?) are needed or plain OCR
   Markdown suffices for our pipeline.

---

## 10. Sources consulted (official / primary first)

Official Mistral:
- OCR / Document AI overview — https://docs.mistral.ai/studio-api/document-processing/overview
- OCR processor (request/response, fields) — https://docs.mistral.ai/studio-api/document-processing/basic_ocr
- OCR API endpoint — https://docs.mistral.ai/api/endpoint/ocr
- Batch OCR cookbook — https://docs.mistral.ai/cookbooks/mistral-ocr-batch_ocr
- Mistral OCR announcement (GA, pricing, self-host) — https://mistral.ai/news/mistral-ocr/
- Mistral OCR 3 announcement (`mistral-ocr-2512`, 2025-12-17) — https://mistral.ai/news/mistral-ocr-3/
- Pricing — https://mistral.ai/pricing/
- Rate limits & usage tiers — https://docs.mistral.ai/deployment/ai-studio/tier
- Known limitations — https://docs.mistral.ai/resources/known-limitations
- Privacy Policy — https://legal.mistral.ai/terms/privacy-policy
- Data Processing Addendum — https://legal.mistral.ai/terms/data-processing-addendum
- ZDR help article — https://help.mistral.ai/en/articles/347612-can-i-activate-zero-data-retention-zdr
- Training opt-out help article — https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training
- Uploaded-docs-for-training help article — https://help.mistral.ai/en/articles/347576-are-my-uploaded-documents-used-for-training

Partner / secondary (corroboration only — not authoritative for pricing/limits):
- Mistral OCR (25.05) on Google Cloud Vertex AI — https://docs.cloud.google.com/vertex-ai/generative-ai/docs/partner-models/mistral/mistral-ocr

> Where official and secondary sources disagree, **trust the official Mistral docs
> and re-verify live** — pricing and limits above were cross-checked against
> secondary write-ups but the official pages govern.

---

## 11. Recommendation

**Proceed only after the operator confirms pricing and privacy** (then, if approved,
implement strictly behind an explicit, off-by-default opt-in).

Rationale: the product is **GA, well-documented, page-priced (cheap per unit), and a
clean structural fit** for our existing Slice 32 boundary + Slice 33/34 routing —
there are **no architectural blockers.** The gating concerns are **not technical**;
they are **policy**: (a) confirming the live per-page price (original `$1/1,000` vs
OCR-3 `$2/1,000`) so cost is understood, and (b) accepting that student notes would
be processed by a third party with a default 30-day retention window (mitigable via
opt-in + ZDR on Scale + avoiding public URLs and the retaining batch path). Until the
operator explicitly confirms **both**, do not write cloud-OCR code.

This is a **conditional go**, not a blanket green light — and emphatically **not** a
green light to route real documents through Mistral yet.

---

## 12. Proposed next slice

**Slice 36 — Mistral OCR provider *skeleton / config design* (disabled by default).**
Docs + design only (or a no-network, off-by-default scaffold) covering:
- a `MistralCloudOcrProvider` implementing the **Slice 32 `OcrProvider` contract**
  (no network calls wired to generation; cloud-off);
- **server-side-only** OCR provider settings + key storage **design** (mirroring the
  existing provider-settings DTO posture — write-only key, no secret in any DTO);
- how `allow_cloud_ocr` would be driven from that setting and remain `False` by
  default; budget + local-fallback contract; metadata-field additions (§7).

**Do not** route real documents through Mistral until pricing, privacy/ZDR, and the
output→Markdown mapping are confirmed and the operator has explicitly opted in.
