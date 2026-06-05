# ASK_YOUR_GUIDE_DESIGN.md — Chat with a generated guide (local-only, design-first)

> **Status: DESIGN ONLY (Ask Slice 1).** No backend endpoint, no frontend UI, no
> pipeline change ships in this slice. This document defines a safe contract and a
> sliceable build plan for a dedicated **Ask Your Guide** workspace where a user
> selects a generated guide/job and chats with it using a **local** model.
>
> **Scope guards honoured by this design.** It does **not** implement endpoints or
> UI; it does **not** change Provider Settings, the Local Model Manager (LMM), the
> generation pipeline, or extraction/OCR; it adds **no dependencies**; and **raw
> API keys never appear** in docs, logs, examples, served JS, exports, or frontend
> state. Ask Your Guide is **local-only in v1** — no DeepSeek/Qwen/cloud fallback.
>
> **Source of truth for current behaviour:** `pipeline/job_manager.py`
> (`clean_md`/`extracted_txt`, `save_clean_md` chokepoint), `pipeline/run_llm_job.py`
> (manifest `attachments[]`, `mode`, `extracted_chars`, `page_selections`),
> `api/server.py` (`/api/jobs*`, `/api/jobs/{id}/artifacts/{name}`),
> `pipeline/provider_config.py` (`get_local_model_status()`, `local` provider
> resolution, `_discover_openai_models`, redaction helpers), and
> `docs/LOCAL_MODEL_MANAGER_DESIGN.md` §4 (status DTO) / §10 (Ask Your Guide note).

---

## 1. Goal and product direction

**Ask Your Guide** lets a stressed student select one generated guide and *ask it
questions*, getting answers **grounded in that guide + its source + any extra docs
they add for the session**, with **citations** (page / section) wherever possible.

- **First-class page/tab.** Ask Your Guide is a top-level workspace alongside
  Builder, Library, Styles, and Providers/Models — **not** a button buried inside
  Library or Job Details. Library/Job Details may *later* gain an "Open in Ask Your
  Guide" shortcut, but the dedicated workspace is the main experience.
- **Local-only in v1.** It uses the **`local` provider only** and **consumes** LMM
  Phase-1 status (it never starts/stops `llama-server` — no process control). If the
  local model is offline, the feature shows a first-class offline state + the LMM
  command helper and is unavailable until the server is up. **No silent cloud use.**
- **Accuracy first.** The audience is exam-stressed students; a confident wrong
  answer is worse than "that isn't in your guide." Grounding, citation, and honest
  "not in the material" behaviour are hard requirements, not polish.

### 1.1 Core user flow

1. User opens the **Ask Your Guide** page.
2. User picks a guide/job from recent / library jobs (eligible = has a generated
   guide).
3. App loads that job's context: generated guide (`clean.md`), job metadata,
   extracted source text (`extracted.txt`, with `## Page N` anchors), attachment
   metadata.
4. User may *optionally* upload extra documents **for this chat session only**.
5. App checks local model status via LMM Phase 1 (`GET /api/local-model/status`).
6. If local model is **offline** → offline state + command helper; chat disabled.
7. If local model is **online** → user chats with the guide.
8. Answers are grounded in guide/source/extra uploads and **cite page/section**
   where possible; if the answer is not in the material, the model says so.

---

## 2. What already exists that this reuses (no new primitives)

| Need | Existing thing to reuse | Notes |
| --- | --- | --- |
| Generated guide text | `Job.clean_md` (`jobs/<id>/clean.md`) | The canonical guide markdown. |
| Extracted source text | `Job.extracted_txt` (`jobs/<id>/extracted.txt`) | Carries `## Page N` anchors from PDF extraction. |
| Job metadata / attachments | `job.json` manifest (`title`, `attachments[]` with `filename`/`mode`/`extracted_chars`/warnings, `page_selections`, `generator_preset`, `include_sections`, axes) | Read-only. |
| Job listing | `GET /api/jobs`, `GET /api/jobs/{id}` | Ask reuses these or adds a thin eligibility filter. |
| Local model status / offline category | `get_local_model_status()` + `GET /api/local-model/status` (LMM Slice 2) | `local_offline` is the single offline category; status DTO is host-only/redacted. |
| Local model call | `local` provider via `build_provider_config("local", ...)` + `generate_chat_completion` (OpenAI-compatible) | Same call boundary generation uses; **no** new model client. |
| Command helper (offline UX) | `GET /api/local-model/command-profile` + `localModelCommand.js` + `CommandHelper` (LMM Slice 4) | Reused verbatim in the offline empty state. |
| Extra-doc extraction | `pipeline/extract.py` helpers (`.txt/.md/.csv/.tsv/.docx/.pptx/.pdf`, page-level OCR) | **Reuse**, do not fork. Session-scoped only. |
| Redaction | `provider_config` redaction (`base_url_host`, `_redact_secret`, no key field) | Every Ask response inherits "no raw key / no full URL". |

**Key principle:** Ask Your Guide is an *orchestration + retrieval layer over read
artifacts*. It introduces **no** new model client, no new extractor, no new secret
surface, and **never writes** a job's `clean.md`/`extracted.txt`/manifest.

---

## 3. The hard rule: do **not** dump everything into every turn

The naive design — "send the whole guide + all attachments + all chat history every
turn" — is rejected. It (a) blows past local context windows, (b) is slow on local
hardware, (c) *degrades* accuracy (the relevant passage drowns in irrelevant text),
and (d) gets monotonically worse as the chat grows. Instead, every turn is built by
a **context manager** that selects a *budgeted* set of the most relevant chunks plus
a compact conversation state.

### 3.1 Context layers

1. **Base guide context** — guide title, guide outline/summary (headings + a rolling
   summary of `clean.md`), and **retrieved `clean.md` chunks**.
2. **Source context** — retrieved **`extracted.txt` chunks** carrying their
   `## Page N` anchors, plus attachment names/metadata (so the model can cite a
   filename + page).
3. **Extra upload context** — **session-only** extracted chunks from docs the user
   added *for this chat*. Never permanently merged into the original job's artifacts
   (a later slice could offer an explicit "save into the guide", out of scope here).
4. **Chat context** — the **recent-turn window** (last *k* turns verbatim) + a
   **rolling conversation summary** of older turns + **pinned facts/preferences**
   (e.g. "I'm preparing for the May exam", "focus on chapter 4").
5. **Retrieval** — per question, select the most relevant chunks across layers 1–3,
   attach their citations/anchors, and stop at the budget.
6. **Context budget** — a configurable token budget that **reserves** room for (a)
   the answer, (b) the system/answer-rules block, and (c) the recent conversation,
   then fills the remainder with retrieved chunks. **Never** fill the whole window
   blindly.

### 3.2 Budget model (illustrative, configurable)

```
total_context_budget         (configurable; default conservative, e.g. 8k tokens,
                              auto-raised when the local model reports a larger window)
  ├─ reserve_answer          (e.g. 25%)   — room for the model's reply
  ├─ reserve_system_rules    (fixed)      — answer rules + citation contract (§5)
  ├─ reserve_recent_chat     (e.g. 15%)   — last k turns verbatim + rolling summary
  └─ retrieval_pool          (remainder)  — top-ranked guide/source/extra chunks
```

- The budget is **derived from the local model's advertised context window when
  available** (long-context models get a bigger pool), but has a conservative
  default so a small model never overflows. Token counting is **approximate**
  (chars/4 heuristic) — **no tokenizer dependency** is added.
- If even the top-1 chunk + reserves exceed the window → **fail gracefully**
  ("This guide is too large for the current local model's context; try a longer-
  context model or ask a narrower question"), never a silent truncation that drops
  the cited passage.

### 3.3 Chunking + lightweight index

- **Chunk** `clean.md` and `extracted.txt` on heading/paragraph boundaries
  (preserving the nearest `##`/`## Page N` anchor as each chunk's **citation
  label**), target ~500–800 tokens/chunk with small overlap.
- **Index = lightweight, dependency-free.** v1 retrieval is **lexical**
  (tokenized keyword / BM25-style or TF-overlap scoring in pure Python) — **no
  embedding model, no vector DB, no new dependency.** A future slice may add a local
  embedding re-rank *if a local embeddings server is available* (optional, never
  required).
- **Cache** the prepared chunk index per `(job_id, content_hash)` on disk under the
  job/session area so re-opening a guide does **not** re-extract or re-chunk. Extra
  uploads are extracted **once** per session and cached session-scoped.

---

## 4. Context preparation lifecycle + performance

Designed for long guides, large source text, extra docs, and long chats.

- **Prepare-once, reuse.** On first open of a guide, build + cache the chunk index
  (guide + source). Subsequent opens read the cache (keyed by content hash so an
  edited `clean.md` re-prepares). Extra uploads extract+chunk once per session.
- **Retrieval before generation.** Every turn: retrieve → assemble within budget →
  call the local model. The model never sees the raw full corpus.
- **Rolling chat summary + recent-turn window.** Older turns are compacted into a
  running summary (cheap local summarization call or heuristic), keeping the last
  *k* turns verbatim — so a 200-message session stays within budget and on-topic.
- **Visible progress states.** Context prep is surfaced ("Preparing guide…",
  "Indexing source…", "Extracting upload…", "Ready") so the user isn't staring at a
  dead box on slow local hardware. Generation streams or shows a thinking state.
- **Graceful failure.** Too-large guide, extraction error, or offline model each
  produce a **specific, honest** state — never a crash, never a silent wrong answer.
- **Optional re-rank later.** A second-pass re-rank (local embeddings/cross-encoder)
  is designed-for but **not v1**.

---

## 5. Accuracy + citation contract (hard requirements)

The system/answer-rules block (the `reserve_system_rules` reservation) encodes these
rules every turn:

1. **Answer from the selected guide/source/extra uploads first.** Prefer the
   provided context over the model's parametric knowledge.
2. **Cite source/page/section when possible** — e.g. *(Guide › "Backpropagation")*
   or *(source p. 42)* using the chunk's anchor label.
3. **If the answer is not in the material, say so** plainly ("This isn't covered in
   your guide/source") instead of inventing.
4. **Do not invent** facts, formulas, page references, definitions, dates, or exam
   requirements. A citation must correspond to a chunk actually in context.
5. **Distinguish "from your guide" vs "general explanation."** When the model adds
   outside context, it must label it as general knowledge, not guide content.
6. **If sources conflict, explain the conflict** (guide vs source vs extra upload)
   rather than silently picking one.
7. **If the question is ambiguous, ask a clarifying question** instead of guessing.
8. **For calculations/formulas, show steps and check the final answer.**
9. **For exam advice, mark high-confidence vs uncertain** points explicitly.

**Citation integrity.** Each retrieved chunk carries a stable, human-meaningful
label (guide heading or `## Page N`). The model is instructed to cite **only** those
labels; the backend can additionally **validate** that emitted page/section
references match labels that were actually in context (a later accuracy slice) and
flag/strip a citation that does not — turning "no hallucinated page numbers" from a
prompt request into a checked invariant.

**Quick study actions** (preset prompts that reuse the same retrieval + rules):
*Explain simply*, *Quiz me*, *Exam focus*, *Summarize selected section*, *Find weak
spots*, *Generate practice questions*. Each is a templated user turn, not a new code
path — they ride the same grounded pipeline so their output is cited too.

---

## 6. Local-only model policy

- **`local` provider only in v1.** Ask resolves the model via the existing `local`
  provider config; it does **not** read DeepSeek/Qwen keys and has **no** cloud
  fallback. If the user explicitly wants a hosted "ask any provider" mode later,
  that is a **separate, explicit opt-in toggle** (designed later) — never a silent
  default.
- **Offline = unavailable, surfaced honestly.** Before enabling chat, Ask checks
  `GET /api/local-model/status`. `reachable:false` → first-class offline empty state
  reusing the LMM `local_offline` category + the **command helper** ("Local model
  offline — start it from Local Models / copy this command"). Chat input is disabled
  until reachable.
- **Model-agnostic, capability-aware.** The design assumes users may run strong
  local long-context / thinking / multimodal models (e.g. Gemma-class), but **must
  not hardcode one model as required.** It stays compatible with **any
  OpenAI-compatible local server**, and *opportunistically* uses extra capability
  when the server advertises it:
  - **Long context** → larger retrieval pool (§3.2).
  - **Thinking-capable** → allow a thinking/reasoning pass (reusing the existing
    `thinking` plumbing) where supported; degrade silently if not.
  - **Multimodal / local OCR** → **deferred** (§9); v1 is text-only.

---

## 7. Storage design (conservative v1)

| Item | v1 decision |
| --- | --- |
| **Ask sessions per guide** | Yes — a session is `{session_id, job_id, created_at, title, pinned_facts, toggles}`. |
| **Chat history** | **Optional, persisted per session** so a user can resume; user can **clear/delete** it at any time. Conservative default may be "kept until cleared". |
| **Session extra uploads** | **Session-scoped.** Stored under the session area, never merged into the original job. Deleting the session deletes them. |
| **Extracted extra-upload text** | Cached session-scoped (extract once); removed with the session. |
| **Context index/cache** | Per `(job_id, content_hash)` guide/source index cached on disk; safe to delete/rebuild. |
| **Delete controls** | User can delete a session, clear a session's history, and remove session uploads. |
| **Exports** | Chat history is **never** auto-included in any export/ZIP bundle. A later, explicit "export this chat" is out of scope. |
| **Secrets** | **None stored, ever.** No keys in session files, caches, or logs. |

**Proposed on-disk layout (illustrative):** `jobs/<job_id>/ask/sessions/<session_id>/`
holding `session.json` (metadata), `history.jsonl` (turns), `uploads/` (session
docs), and `cache/` (extracted text + chunk index). Reuses the existing per-job dir
discipline; nothing escapes the jobs tree; the trash/purge model still governs the
parent job. (Final path is a Slice-3/8 implementation choice — recorded here so chat
data is co-located with its job and removed when the job is trashed.)

---

## 8. Backend API design (local-only; flexible + sliceable)

All routes are **additive**, registered **before** the SPA mount (so `/api/*` keeps
winning), call the **local provider only**, check LMM status, and **never** modify
the original job artifacts or create generation jobs. Every response is redacted by
construction (host-only URL, no key field).

| Route | Method | Purpose | Slice |
| --- | --- | --- | --- |
| `/api/ask/jobs` | GET | List **eligible** guides (jobs with a generated `clean.md`); thin filter over existing job listing. | 2 |
| `/api/ask/jobs/{job_id}/context` | GET | Context **readiness + source summary** — what's available (guide chars, source chars, page-anchor count, attachment names, prep/cache state). No chat. | 2 |
| `/api/ask/jobs/{job_id}/prepare` | POST | Build/refresh the chunk index for the guide+source (idempotent; cached by content hash). Returns progress/ready. | 3 |
| `/api/ask/jobs/{job_id}/sessions` | POST | Create a chat session for a guide. | 4 |
| `/api/ask/sessions/{session_id}` | GET | Load a session (metadata + history + toggles). | 4 |
| `/api/ask/sessions/{session_id}/message` | POST | Ask a question → retrieve → local-only generate → grounded, cited answer. | 4 |
| `/api/ask/sessions/{session_id}/attachments` | POST | Upload extra docs **into the session**; reuse `extract.py`; chunk + cache session-scoped. | 7 |
| `/api/ask/sessions/{session_id}` | DELETE | Delete session (and its uploads/cache). | 8 |
| `/api/ask/sessions/{session_id}/history` | DELETE | Clear history but keep the session. | 8 |

**Backend invariants (every route):**

- **Local provider only.** Resolve `local`; if not configured or `reachable:false`,
  return a safe "local offline/unavailable" result (reusing `local_offline`) — never
  fall through to a cloud provider, never read a cloud key.
- **Status-gated.** `message` checks `get_local_model_status()` first; offline → a
  structured offline response, not a model call.
- **Read-only over job artifacts.** Reads `clean.md`/`extracted.txt`/manifest;
  **never** calls `save_clean_md`, never rewrites the manifest, never creates a job.
- **Reuse extraction.** Extra uploads go through the existing `extract.py` helpers
  (no second extractor); session-scoped, bounded in count/size like the existing
  attachment caps.
- **No secret surface.** No raw key / full URL in any response, log line, cache file,
  or error; errors classified + redacted like the LMM/provider surfaces.
- **Two-path rule.** `attachments` upload is multipart; if any Ask request grows to
  carry both JSON and multipart transports, it must be wired + verified on **both**
  paths (the permanent `/api/jobs/llm` lesson in `DECISIONS.md`).

---

## 9. Frontend design — `AskGuideWorkspace`

A dedicated workspace (new top-level nav item), Claude-style baseline, three-region
layout:

- **Left — guide / session picker.** Eligible guides (from `/api/ask/jobs`) +
  per-guide session list; "New chat" / select session.
- **Center — chat.** Message list (user/assistant), grounded answers with inline
  **citation chips**, the **local offline banner** + **command helper** when
  unreachable, a **model status pill + Refresh** (consuming LMM status), the
  **quick study action** buttons (§5), the composer, and a **Clear chat** control.
- **Right (or drawer) — sources / context / citations.** A **selected-guide summary
  card**, a **local model status card**, and a **context sources panel** listing:
  generated guide, extracted source text, original attachments, and extra uploaded
  session documents — with **source chips** and an **Upload extra documents** button.
  When the user clicks a citation in an answer, this panel reveals the cited chunk.

**Toggles (optional, design-noted):** "Answer from guide only" (suppress general
knowledge) and "Include extra uploads" (scope retrieval) — both default to the safe,
grounded behaviour.

**Offline-first UX.** If LMM status is offline the workspace still loads (guide
picker, context summary, sources all visible) but the composer is disabled with the
command helper prominent — mirroring the LMM panel's offline treatment so the user
has one consistent "start your local server" story.

**Library/Job Details shortcut (later).** An "Open in Ask Your Guide" affordance can
deep-link a job into this workspace — additive, not the primary entry point.

---

## 10. Multimodal / image support (designed-for, not v1)

v1 is **text-only** (extracted text is enough). Designed for later, behind explicit
slices: original figures/diagrams/images from attachments, multimodal local models
(image input where the local server supports it), image OCR/caption extraction,
chart/diagram grounding, and per-source snapshots. None are built now; the context
manager's chunk/citation model leaves room to attach an image chunk + caption later
without reshaping the contract.

---

## 11. Implementation slices

Each slice: **scope / likely files / tests / acceptance / non-goals.**

### Ask Slice 1 — design (THIS TASK)
- **Scope:** this design doc + doc reconciliation. **No code.**
- **Files:** `docs/ASK_YOUR_GUIDE_DESIGN.md` (new); `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/PROJECT_CONTEXT.md`, `docs/DECISIONS.md`
  (updated).
- **Tests:** docs-only diff; optional `python -m compileall api pipeline` (no code
  changed).
- **Acceptance:** dedicated-workspace direction, local-only policy, context-manager
  + retrieval, accuracy/citation contract, storage, endpoints, and the slice plan are
  all recorded; `DECISIONS.md` captures the three key decisions.
- **Non-goals:** any code, any endpoint, any UI.

### Ask Slice 2 — backend context inventory endpoint (BACKEND ONLY) — **NEXT**
- **Scope:** `GET /api/ask/jobs` (eligible guides) + `GET /api/ask/jobs/{id}/context`
  (read-only summary of available guide/source/attachments + readiness). **No chat,
  no chunking, no model call.**
- **Files likely:** `api/server.py` (2 routes, before the SPA mount), a thin reader
  in `pipeline/` (reuse `Job.clean_md`/`extracted_txt` + manifest; **no** writes).
- **Tests:** `test_scripts/test_ask_context_inventory.py` — eligible vs
  guide-less job, source-summary fields (chars, page-anchor count, attachment
  names), and a **secret scan** of the response. Smoke unchanged.
- **Acceptance:** lists only jobs with a generated guide; summarizes sources;
  reads artifacts read-only; no key/full-URL leak; original job untouched.
- **Non-goals:** chunking, retrieval, sessions, any model call, any UI.

### Ask Slice 3 — context preparation / chunking (BACKEND ONLY)
- **Scope:** chunk `clean.md`/`extracted.txt` with anchor labels; build the
  lightweight lexical index; cache per `(job_id, content_hash)`. `POST
  /api/ask/jobs/{id}/prepare`.
- **Tests:** chunk boundaries + anchor preservation (`## Page N`), cache hit/skip on
  re-prepare, re-prepare on content change. **No new dependency.**
- **Acceptance:** deterministic chunks carry correct citation labels; second prepare
  is a cache hit; no artifact mutation.
- **Non-goals:** embeddings/vector DB, model call, UI.

### Ask Slice 4 — backend local chat endpoint (BACKEND ONLY)
- **Scope:** sessions (create/load) + `POST …/message`: status-gate → retrieve →
  budget-assemble → **local-only** `generate_chat_completion` → grounded, cited
  answer. Simple lexical retrieval; recent-turn window (rolling summary may defer to
  Slice 8).
- **Tests:** offline → structured offline response (no model call); a stubbed local
  server returns a cited answer; "not in material" path; **no** cloud key read;
  secret scan.
- **Acceptance:** answers cite in-context labels; offline is honest; original job
  untouched; local-only proven.
- **Non-goals:** frontend, extra uploads, rolling summary, citation validation.

### Ask Slice 5 — frontend Ask workspace shell (FRONTEND)
- **Scope:** new top-level **Ask Your Guide** nav/page: guide picker, selected-guide
  summary card, local status card, context summary (consuming Slices 2–4). No
  message send yet (or read-only).
- **Tests:** pure helper module unit-tested via a node harness (mirroring
  `localModelStatus.js`/`verify-*` pattern); `npm run build` OK.
- **Acceptance:** workspace renders, lists eligible guides, shows context + status.
- **Non-goals:** sending messages, uploads.

### Ask Slice 6 — frontend chat UI (FRONTEND)
- **Scope:** send/receive messages, render citations + source chips, offline banner +
  command-helper reuse, Clear chat.
- **Acceptance:** grounded answers render with clickable citations; offline disables
  the composer with the helper shown.
- **Non-goals:** extra uploads, quiz/exam actions polish.

### Ask Slice 7 — extra upload support (BACKEND + FRONTEND)
- **Scope:** `POST …/sessions/{id}/attachments` reusing `extract.py`; chunk + cache
  session-scoped; include in retrieval; "Include extra uploads" toggle.
- **Acceptance:** an uploaded doc's content becomes citable in answers; session
  uploads never merge into the original job; bounded count/size.
- **Non-goals:** multimodal/image, persisting uploads into the guide.

### Ask Slice 8 — long-chat memory + session management (BACKEND + FRONTEND)
- **Scope:** rolling conversation summary, clear history (`DELETE …/history`), delete
  session (`DELETE …/sessions/{id}`), session persistence/resume.
- **Acceptance:** a long session stays within budget and on-topic; clear/delete work;
  no chat data in exports.
- **Non-goals:** export-of-chat, multimodal.

### Ask Slice 9 — accuracy / polish (BACKEND + FRONTEND)
- **Scope:** citation validation (strip/flag references not in context), the quick
  study actions (Explain simply / Quiz me / Exam focus / Summarize section / Find
  weak spots / Generate practice questions), high-vs-uncertain marking.
- **Acceptance:** emitted page/section refs verified against in-context labels; study
  actions ride the grounded pipeline.
- **Non-goals:** multimodal.

### Ask Slice 10 — optional multimodal support (LATER)
- **Scope:** image/figure grounding + multimodal local models + image OCR/caption.
  Design-first, sign-off-gated. Out of v1.

---

## 12. Risk analysis

| Risk | Mitigation |
| --- | --- |
| **Hallucinations / uncited answers** | Strict answer-rules block (§5); cite only in-context labels; later **citation validation** strips refs not in context (Slice 9); "not in the material" is an explicit, rewarded behaviour. |
| **Too much context hurts accuracy** | Budgeted retrieval (§3) — top-ranked chunks only, never the whole corpus; reserves for answer/rules/recent chat. |
| **Local model offline** | Status-gated (§6); first-class offline state + LMM command helper; chat disabled, never a silent cloud fallback. |
| **Local model too slow** | Visible prep/generation progress states; small default budget; prepare-once cache; streaming/thinking states. |
| **Long chats degrade** | Rolling summary + recent-turn window + pinned facts (Slice 8); session stays within budget. |
| **Huge attachments / guides** | Chunking + bounded session-upload caps (reuse existing caps); graceful "too large for this model" failure, not silent truncation. |
| **OCR / extraction errors** | Reuse the tuned `extract.py` (page-level OCR fallback); surface attachment warnings/mode in the sources panel so the user sees imperfect source. |
| **Conflicting sources** | Answer rule #6 — explain the conflict (guide vs source vs upload) rather than silently choosing. |
| **Privacy of chat history + uploads** | Session-scoped storage; user can clear/delete; **never** auto-exported; co-located with the job and removed when the job is trashed; no secrets stored. |
| **User panic / exam-pressure UX** | Honest "not covered" over confident-wrong; high-vs-uncertain marking; clarifying questions; calm offline messaging with a clear fix. |
| **Model-specific assumptions** | No hardcoded model; any OpenAI-compatible local server works; capability (long context / thinking / multimodal) used only when advertised. |
| **Accidentally using hosted APIs** | Local-only by construction (§6/§8) — Ask resolves `local` only, reads no cloud key, has no fallback path; cloud "ask any provider" is a future explicit toggle. |
| **Prompt injection inside uploaded materials** | Source/upload text is treated as **untrusted data, not instructions**; the system rules block instructs the model to never follow instructions embedded in guide/source/upload content; uploads are session-scoped and never executed. |

---

## 13. Key decisions (also recorded in `DECISIONS.md`)

1. **Ask Your Guide is a dedicated first-class workspace**, not a Library-only
   button. Library/Job Details may later deep-link into it; the workspace is primary.
2. **Ask Your Guide v1 is local-only** — the `local` provider only, status-gated on
   LMM Phase 1, **no hosted fallback**. A hosted "ask any provider" mode is a future
   **explicit** opt-in, never a silent default.
3. **A context manager + retrieval is mandatory** — never dump the whole guide + all
   attachments + all chat history into every turn. Budgeted retrieval, chunking with
   citation anchors, a rolling chat summary, and reserved answer/rules space are part
   of the contract, not an optimization.

---

## 14. Non-goals (v1)

- No endpoints, UI, or pipeline/extraction changes in **this** slice (design only).
- No process control of `llama-server` (Ask **reads** LMM status; LMM owns control).
- No cloud/hosted provider use or fallback.
- No new dependency (no vector DB, no embedding model, no tokenizer lib).
- No multimodal/image grounding in v1 (designed-for, deferred to Slice 10).
- No mutation of the original job's `clean.md`/`extracted.txt`/manifest, and no
  generation-job creation.
- No chat history in exports.
- No raw API keys anywhere (docs, logs, examples, served JS, exports, frontend
  state).
</content>
</invoke>
