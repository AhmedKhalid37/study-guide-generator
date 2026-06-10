# Roadmap Input Summary — GuideForge / Study Guide Generator

> Short companion to `docs/PROJECT_FULL_INSPECTION_REPORT.md`. Built to hand to an
> independent session to choose the next ~10 slices. The **running code is
> authoritative**; this is a 2–4 page orientation, not a substitute for the code.

## Exact current position

- **Branch / PR target:** `chrome-renderer-v1`.
- **HEAD:** `eaa1263` — "Slice 16: Post-reskin release audit + checkpoint".
- **Working tree:** clean (`git status --short` empty; runtime `jobs/`, `config/`,
  `user_prompts/`, `library/`, `.env*` are gitignored).
- **Validation status:** `smoke_release.py` **28 passed / 0 failed / 0 skipped**;
  frontend build green; `compileall api pipeline` green; Slice-16 security scan clean
  (no keys/tokens/socket/paths in any served API or the JS bundle). The default
  `npm run test` (`verify-assets.mjs`) is **stale/known-bad** (old mockup tree) and is
  **not** a release blocker.

## Current app state

A Dockerized, **same-origin React (Vite + Tailwind) + FastAPI** app for a single
operator / small group. It converts pasted text, uploaded Markdown, or uploaded
attachments (PDF/DOCX/PPTX/TXT/CSV, Tesseract OCR for image-only PDF pages) into
exam-focused **study guides** rendered to **PDF** (headless Chromium) + **HTML / DOCX /
Markdown**, plus **quizzes/flashcards** (CSV/Anki/Quizlet) and a **local-model-only Ask
Your Guide** grounded chat. Seven nav workspaces (Home, Builder, Library, Ask, Styles,
Models, Exports) + a Help workspace. ~80 backend routes; secrets are server-side and
write-only by construction.

**Maturity:** a mature, feature-complete v1 for its scope. The last phase (Slices 1–16)
was a full **GuideForge reskin + UX redesign** to a 773-class semantic `.sg-*` CSS
system, now declared complete. The natural next direction (per the project's own
handoff) is a **correctness / measurement layer**, not more UI.

## Completed major features

- Three input transports (paste / upload-markdown / LLM) + attachments with **per-page
  text/OCR fallback** and **large-PDF preflight + page selection**.
- Deterministic prompt assembly (sections + depth/difficulty axes + always-last math
  system block); multi-provider routing (DeepSeek + Qwen verified) with strict
  resolution precedence.
- **Provider Settings** — in-app config, two-file store (`provider_settings.json` +
  `0600 secrets.json`), write-only keys, fetch-models, test-connection. Complete +
  validated.
- Rendering: PDF (tuned Chromium), HTML (KaTeX), DOCX (lazy from `clean.md`), Markdown.
- Job lifecycle: staged progress, cooperative cancel (sidecar marker), retry, rerender,
  **version snapshots + revert** (via the `save_clean_md` chokepoint), manual markdown
  edit, **section regeneration** + outline compliance.
- **Quizzes / flashcards** with CSV / Anki / Quizlet export.
- **Library / Trash / Exports** — folders, batch move, **trash-before-purge** safety,
  multi-job ZIP bundles.
- **Home shortcuts + Shortcut Inspector / Repair Loop** (3-tier validity, whitelist-
  patch repair, activation gating).
- **Ask Your Guide** — local-only grounded chat, deterministic chunking, **lexical
  retrieval**, enforced citation contract, sessions.
- **Local Model Manager** Phase 1 (complete+validated) and Phase 2 (complete/**paused**
  after 2G11; real CPU-safe `llama-server` E2E passed; `gpu_layers=999` failed safely
  and is not a default).
- The full reskin/UX phase (Slices 1–16), incl. Compare-styles and JobDetails reskin.

## Strongest next opportunities

1. **Deterministic math verification core** — today's "math validation" is **KaTeX
   parse/render only** (does the LaTeX compile), **not** whether the math is *correct*.
   This is the single biggest trust gap. (P0)
2. **Surface verification into `validation.json` + JobDetails** — make correctness
   visible per job. (P0, depends on #1)
3. **Eval harness Phase 1** — golden inputs, scored outputs, regression detection;
   currently quality is entirely unmeasured. (P0/P1)
4. **Deterministic structure / KaTeX / outline lint** — advisory gate on headings,
   KaTeX validity, outline coverage. (P1)
5. **Ask retrieval upgrade** — replace the dependency-free lexical index with a vector
   store (e.g. LanceDB) + optional hybrid/reranker, preserving local-only. (P1)
6. **Study system** — FSRS spaced repetition, active-recall/cloze, true Anki `.apkg`
   (current Anki export is CSV-shaped). (P1/P2)
7. **Provider/OCR breadth** — first-class Gemini; optional Mistral OCR; hybrid OCR
   metadata. (P2)
8. Higher-risk/later: source visual extraction, VLM understanding, LMM packaging /
   approve-root. (P2/P3)

Highest-leverage cluster: **#1 → #2 → #3 (+#4)** — convert unmeasured quality into a
gated, visible correctness layer before adding more generation surface.

## Biggest risks

- **No correctness/measurement layer** — generated math/facts are unverified; no eval
  harness or golden set.
- **Oversized files** — `BuilderWorkspace.jsx` (3,429 LOC), `RecentJobsPanel.jsx`
  (2,005), `HomeShortcuts.jsx` (1,671), `LocalModelsPanel.jsx` (1,646),
  `LibraryWorkspace.jsx` (1,579); `api/server.py` (~3,800); **`design-system.css` 200 KB
  / 3,228 lines / 773 classes**.
- **Dead code left in place** (documented): non-embedded `RecentJobsPanel`/`PreviewPanel`
  branch, `Tile`, `MetaRow`, mockup components, `PasteGenerationPanel`, `data/mockups.js`.
- **Stale default `npm run test`** (`verify-assets.mjs`).
- **Doc drift** — `CLAUDE.md` route list is stale; the deep report references a
  non-existent `pipeline/section_scorer.py`.
- **Scale limits** — JSON-file stores, no pagination (UI loads all jobs; ~150 already on
  disk); Chromium PDF render is the heavy, uninterruptible step.
- **Security surface to keep guarded** — the LMM exposure list, the two-path
  `/api/jobs/llm` parsing rule, the trash purge path guard, secrets never in any
  API/log/artifact/export/JS surface. (Currently clean — must stay so.)

## Load-bearing invariants the roadmap must not break

- `/api/*` registered before the SPA mount; same-origin single container.
- All `clean.md` writes go through `JobManager.save_clean_md`.
- Trash-before-purge; cancel as a sidecar marker (never a process kill).
- Math validation degrades, never fails a job.
- `/api/jobs/llm` has two non-shared parsing paths (JSON + multipart) — wire both.
- Frontend never owns the section/axis/preset key set (backend canonical).
- LMM boundary: backend never touches host FS/processes directly; frontend never calls
  the companion; approved roots from companion config only; LMM Phase 2 stays paused
  unless a new approve-root/packaging slice is designed.
- Ask stays local-only unless explicitly redesigned. Provider Settings is the single
  config writer.

## Recommended roadmap decision points (answer before picking slices)

1. **Local-first vs cloud-first default?** (gates OCR/retrieval/VLM design)
2. **Does Ask stay local-only?** (gates retrieval upgrade + any VLM Ask)
3. **OCR cost budget** — is paid OCR (Mistral) acceptable or must it stay offline?
4. **Math-correctness first or OCR first?** (which quality pain is worse today)
5. **Packaging target** — Linux/Docker single-operator, or invest in GHCR / Win-macOS /
   LMM approve-root?
6. **Prioritized persona** — solo exam-cram student / small study group / local-GPU power
   user? (reweights study-system vs LMM vs retrieval)
7. **Dedicated tech-debt slice up front?** (dead-code sweep, component splits, default
   `test` fix, doc reconciliation) vs folding into feature slices.
8. **Eval harness depth** — lightweight golden-set scoring, or fuller LLM-judge +
   regression tracking?

See `docs/PROJECT_FULL_INSPECTION_REPORT.md` §14 for the full candidate table (title /
purpose / scope / risk / value / dependencies / priority / verification) and §15 for the
expanded question set.
