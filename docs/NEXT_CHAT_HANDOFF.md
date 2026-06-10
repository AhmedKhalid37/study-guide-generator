# NEXT_CHAT_HANDOFF.md — Start here

> One-page handoff so a fresh chat (Claude / ChatGPT / Codex) can continue safely
> from the repo alone. The repo is the source of truth. For the full per-slice log
> see `CURRENT_TASK.md`; for the "why" behind choices see `DECISIONS.md`; for the
> stable overview see `PROJECT_CONTEXT.md`; canonical brief is `../CLAUDE.md`.

## Current position
- **Branch in progress:** `slice23a-page-anchor-reachability`, created from
  `chrome-renderer-v1`. Slice 23A is implemented as a measurement/proof slice and
  intentionally uncommitted. Do not commit unless explicitly asked; do not
  force-push.
- **Branch (trunk / PR target):** `chrome-renderer-v1` (all reskin slices land here).
- **Phase:** the **GuideForge reskin + UX phase is COMPLETE** (Slices 1–15
  reskinned every workspace to semantic GuideForge CSS — Tailwind utilities are
  inert in this app, live UI uses real `.sg-*` / element-cascade rules). Slice 16
  was the post-reskin **release audit + checkpoint**; Slice 17 is the follow-on
  **hygiene checkpoint** (dead-file sweep + `npm test` chain repair). With Slice 17
  the reskin/UX phase is closed and the codebase is clean — **the correctness /
  measurement phase has now begun with Slice 18 (deterministic math verification).**
- **HEAD:** Slice 18 (deterministic math-correctness verifier, **pure core only**)
  is **committed** on `chrome-renderer-v1` as `2c47d03` (immediately after Slice 17
  `ff214fd`). Slice 18 added a standalone module + tests only — **no**
  job/artifact/API/prompt/frontend/UI integration.
- **Slice 19 (deterministic guide-lint core, pure advisory only) is committed** on
  `chrome-renderer-v1` (immediately after Slice 18 `2c47d03`) — see the commit log
  for the hash. **Pure advisory core only:** no job integration, no artifact, no
  API, no `validation.json`, no prompt, no frontend/UI.
- **Slice 20 (eval harness Phase 1 — deterministic scoring framework) is
  implemented + verified, PENDING REVIEW before commit** — once committed, update
  this line with the hash.
- **Slice 22 implemented + verified:** frontend-only, read-only JobDetails UI for
  Slice 21's per-job `math_verification.json`. The artifact is still intentionally
  excluded from generic artifact lists. `JobDetailsDrawer` has a new
  `Verification` tab that fetches `/api/jobs/{id}/artifacts/math_verification.json`
  on demand via a small API helper, then `MathVerificationPanel` renders
  completed/skipped/404/malformed/fetch-error states. Completed reports show
  summary counts and a bounded compact claim list. No backend, pipeline, prompt,
  provider, `/api/jobs/llm`, job mutation, artifact writing, guide-lint
  integration, or `validation.json` schema change.
- **Slice 23A result (page-anchor reachability proof):** PASS. The inspected path is
  `pipeline/extract.py` (`## Page N` PDF anchors) →
  `pipeline/run_llm_job.py::_attach_sources(...)` (attachment text appended under
  `## Attached Sources`) → `pipeline/orchestrator.py` (`build_messages(...)` or
  `build_messages_for_preset(...)`) → `generate_chat_completion(messages, config)`.
  The exact model-facing boundary is the assembled `messages` list. Focused test
  `test_scripts/test_page_anchor_reachability.py` plus fixture
  `test_scripts/fixtures/page_anchor_reachability/extracted_pages.txt` proves simple
  two-anchor source text, anchors surrounded by normal lecture text, attachment
  augmentation, and preset prompt assembly preserve `## Page 1` / `## Page 2` in
  the model-facing `user` content. It also proves no default citation directive or
  rendered citation assumption was added. Tests/docs only; no prompt behavior,
  frontend/UI, provider, OCR, extraction, retrieval, `validation.json`,
  `math_verification.json`, or `/api/jobs/llm` request-field change.
- **Slice 20 result (measurement spine only):** added `test_scripts/eval/`
  (`run_eval.py` CLI + `score_guide.py` pure core + `golden/sample.json` +
  fixtures + READMEs). It scores guide Markdown against a JSON **golden spec**
  using the Slice 18 verifier (`math`), the Slice 19 linter (`lint`), and simple
  normalized string checks (`concepts`, `must_not_claim`); live mode adds an
  `artifacts` metric. `overall` = renormalized weighted mean over the non-null
  metrics. **Offline mode is required and dependency-free** (no keys/Docker/LLM):
  `python test_scripts/eval/run_eval.py --offline --all`. Optional `--live` POSTs
  to the existing **no-provider** `/api/jobs/paste` only. Results are JSON +
  `summary.csv` under `test_scripts/eval/results/` (**git-ignored**; only fixtures/
  specs/READMEs are tracked); every result is **secret-scanned before write**.
  Regression comparison is keyed on `(spec_id, mode, guide)` and is **non-blocking**.
  **No** prompt/provider/`/api/jobs/llm`/Builder/JobDetails/artifact/OCR/retrieval/
  embedding/LanceDB/LLM-judge change; **no new dependency** (JSON specs, stdlib).
  Tests `test_scripts/test_eval_harness.py` (59/59); build, `npm test`,
  `compileall`, `test_math_verifier` (74/74), `test_guide_lint` (64/64),
  `--offline --all`, and diff check all green. `smoke_release.py` = 26/2/0; the 2
  failures are **environmental** (host thread limit → Chromium can't fork to
  render PDFs: `pthread_create: Resource temporarily unavailable (11)`), **not a
  regression** — Slice 20 adds no server/pipeline/frontend code.
- **Slice 19 result (pure advisory core only):** added `pipeline/guide_lint.py`,
  `lint_guide_markdown(markdown, *, source_name=None, expected_sections=None,
  run_katex=True) -> GuideLintReport` — a JSON-serializable findings report
  (`summary{total,error,warning,info}` + `findings[{id,rule,severity,line,message,
  excerpt}]`). Rules: `empty_heading` (nested-aware), broken-table family
  (`separator_without_header`/`header_separator_mismatch`/`malformed_separator`/
  `body_row_mismatch`, all warnings — conservative), `unbalanced_math` (`$$`/`\(`/
  `\[` = error, single `$` = warning for currency ambiguity), KaTeX bridge
  (`katex_render` error / `katex_skipped` info — **reuses** `scripts/validate_math.js`
  via `pipeline.math_validator.validate`, degrades gracefully when Node/KaTeX is
  missing), and `missing_section` (normalized, order not enforced). Fenced code +
  inline code are excluded; input is never mutated; no HTML/`dangerouslySetInnerHTML`.
  **NOT wired into jobs / artifacts / API / frontend / `validation.json`**;
  `math_validator.py` is reused unchanged and `math_verifier.py` is untouched; **no
  new dependency**. Tests `test_scripts/test_guide_lint.py` (64/64) + fixtures under
  `test_scripts/fixtures/guide_lint/`; build, `npm test`, `compileall`,
  `test_math_verifier` (74/74), diff check, and `smoke_release.py` (28/0/0) all
  green. Optional CLI: `python -m pipeline.guide_lint <file>`.
- **Slice 18 result (pure core only):** added `pipeline/math_verifier.py`, a safe,
  deterministic numeric-correctness verifier (`verify_math_claims(text, *,
  source_name=None)` → JSON-serializable report with per-claim `ok` / `mismatch` /
  `unparseable`). Conservative Tier-A, line-based extraction of `expression
  <relation> number` claims (`=`, `≈`, `~=`, `->`, `→`); skips fenced/inline code;
  unwraps `$…$` / `$$…$$` / `\(…\)` / `\[…\]`; small safe normalizer (unicode minus,
  `×·\times\cdot`→`*`, `÷`→`/`, `^`→`**`, `√`/`\sqrt`/`\frac`, `π`, `e`/`exp`).
  Evaluation is a stdlib `ast`-walk whitelist (no `eval`, no attribute access, no
  names beyond `pi`/`e`/`tau`, bounded length/tokens/nodes/exponent) — every
  verifier error downgrades to `unparseable`, never `mismatch`. **NOT wired into
  jobs / artifacts / API / frontend / `validation.json`** — it is **separate from
  `math_validator.py`** (which validates KaTeX rendering, not numeric values).
  **No new dependency** — SymPy is installed in the host env but unused/not added;
  a stdlib AST evaluator is safer and dependency-free. Tests
  `test_scripts/test_math_verifier.py` (74/74) + fixtures under
  `test_scripts/fixtures/math_verifier/`; build, `npm test`, `compileall`, diff
  check, and `smoke_release.py` (28/0/0) all green. Optional CLI:
  `python -m pipeline.math_verifier <file>`.
- **Slice 17 result:** carried out the dead-code sweep Slice 16 had deferred —
  `git rm` of the proven-unreachable mockup/legacy presentational set (`BrandMark`,
  `Chip`, `ClaudeIcons`, `DesktopMockup`, `FallbackImage`, `Field`, `GlowBackground`,
  `ImplementationNote`, `MobileScreenPicker`, `PasteGenerationPanel`, `PhoneMockup`,
  `StatCard`, `TopBar`, `data/mockups.js`, the 5 `public/mockups/*.png`, and the
  obsolete `verify-assets.mjs`); repaired `npm test` to chain the 9 maintained
  harnesses; updated the `App.jsx` comment and the deep report. Live render path
  stays clean — **0 undefined `sg-*`**; the only old-palette tokens left (2 lines in
  `RecentJobsPanel.jsx`) are inside the **unreachable** non-embedded `PreviewPanel`
  branch (sole caller `HomeShortcuts` always passes `embedded`), intentionally left
  rather than churned in a hygiene slice. Build, full `npm test` (9 harnesses),
  `compileall`, and `smoke_release.py` (28/0/0) all green; container confirmed
  serving the post-deletion build (deleted mockup PNG → 404, SPA → 200); security
  scan clean (no keys/tokens/socket/paths in any served API or the JS bundle).
  **Frontend + docs only; no behaviour/endpoint/payload/data changes, no new deps.**
- **`npm test` is now a real release check** — the former stale `verify-assets`
  mockup harness is gone; `npm test` chains the maintained shortcut/local-model/
  ask/style-compare harnesses, so its failures are now release-relevant. (The old
  "treat `npm test` failures as pre-existing" caveat no longer applies.)
- **Screenshots / visual review are operator-owned** — Claude Code does not produce
  them; the operator does visual inspection and supplies screenshots if needed.
- **NEXT after Slice 19 = decide on integration of the correctness modules** —
  the math verifier (Slice 18) and the guide linter (Slice 19) are both pure cores;
  a future designed slice decides how/whether to surface them (optional job-stage
  advisory report / `validation.json` field / JobDetails surfacing). That
  integration is intentionally **out of scope** for both slices, and neither the
  verifier nor the linter may ever make guide generation fail. LMM
  Phase 2 remains **paused** —
  resume only with a separately designed approve-root or packaging slice;
  app-suggested settings remain deferred.

## What just landed
- **Slice 22 — JobDetails math verification artifact UI** (branch
  `slice22-jobdetails-math-verification-ui`, implemented + verified, uncommitted).
  Added
  `frontend/src/mathVerification.js`, `frontend/src/components/MathVerificationPanel.jsx`,
  a generic read-only `getJobArtifact()` helper, a `Verification` JobDetails tab,
  compact semantic CSS for claim rows, and
  `frontend/scripts/verify-math-verification.mjs` wired into `npm test`.
  UI fetches `math_verification.json` only when the tab is opened and handles
  completed, skipped, missing/404, malformed/unexpected, invalid JSON, and
  fetch/network error states. Read-only only: no rerun verifier action, no job
  mutation, no artifact writes, and no backend/pipeline behavior changes.
  Validation green: build, full `npm test`, helper harness, `compileall`,
  math-verifier tests, guide-lint tests, eval-harness tests, offline eval all,
  `git diff --check`, and `smoke_release.py` (29/0/0).
- **Slice 17 — hygiene checkpoint: dead-file sweep + `npm test` repair** (this
  branch, `chrome-renderer-v1`, PENDING REVIEW). Deleted the proven-unreachable
  mockup/legacy presentational set + 5 mockup PNGs + obsolete `verify-assets.mjs`
  via `git rm`; rewired `npm test` from the stale single mockup harness to the 9
  maintained harnesses; updated the `App.jsx` comment and the deep report's §6
  component/harness lists. Build + full `npm test` + `compileall` + `git diff
  --check` + `smoke_release.py` (28/0/0) green; container serving the post-deletion
  build; 0 undefined `sg-*`; only-remaining old-palette is in the unreachable
  `PreviewPanel` branch (left, not churned); security scan clean. **Frontend +
  docs only; no behaviour/endpoint/payload/data changes, no new deps.** See
  `CURRENT_TASK.md` for the per-audit detail.
- **Slice 16 — post-reskin release audit + checkpoint** (this branch,
  `chrome-renderer-v1`). Full validation pass after Slices 1–15: build + 4 pure
  frontend harnesses + `compileall` + Docker build/up + `smoke_release.py`
  (28 passed / 0 failed / 0 skipped) all green. Semantic-CSS audit (773 defined
  `.sg-*`, 0 undefined in the live path), inert-utility/old-palette audit (live
  path clean after a 1-file surgical strip of inert tokens in
  `RecentJobsPanel.jsx`; dead-branch/dead-file leftovers reported, not churned),
  and a security quick-scan (no raw secrets in `/api/options`, `/api/styles`,
  `/api/provider-settings`, `/api/local-model/status`, JobDetails, or the served
  bundle). **Frontend-only, 1 file changed, no behaviour/endpoint/payload/data
  changes.** See `CURRENT_TASK.md` for the per-audit detail. Status: awaiting
  review before commit.
- **Local Model Manager Phase 2G11 — final hardening/regression pass** (branch
  `lmm-phase2g11-final-hardening`). Added the pure/offline final harness
  `test_scripts/test_lmm_phase2_final_regression.py`. It validates the
- **Local Model Manager Phase 2G11 — final hardening/regression pass** (branch
  `lmm-phase2g11-final-hardening`). Added the pure/offline final harness
  `test_scripts/test_lmm_phase2_final_regression.py`. It validates the
  runtime-service examples and placeholders, example JSON parsing, `.ini` preset
  parsing through the companion loader, safe Compose/systemd template boundaries,
  backend/server/profile DTO redaction, CPU-safe/balanced/low-memory manual
  defaults, risky-only `gpu_layers=999` scope, no LMM Provider Settings writes,
  no Ask coupling, no direct frontend companion calls, no production Compose
  companion mount/env, companion-config-only approved roots, no browser folder
  picker, and safe selected-model persistence. No production backend behavior,
  frontend UI, Ask, Provider Settings, Docker Compose, installer/autostart,
  model download, or settings-recommendation behavior changed. **The current
  safe LMM Phase 2 milestone is complete/paused after 2G11.** Real validation
  facts remain: CPU-safe validation passed with `/usr/bin/llama-server`,
  `LMM_REAL_MODEL_ROOT=/mnt/ai/llm-models`,
  `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`, `port=18080`, `ctx_size=4096`,
  `gpu_layers=0`, and `threads=8`; full offload `gpu_layers=999` failed safely
  with CUDA OOM / `model_may_be_too_large` on the 26B model and is not a
  default. Deferred: approve-root flow design/implementation, app-suggested
  settings/recommendations, Ollama/simple-local-model path, Windows/macOS
  support/packaging, and model downloads.
- **Local Model Manager Phase 2G10 — companion runtime-service/operator
  packaging docs** (branch `lmm-phase2g10-runtime-service-docs`). Added
  `docs/LOCAL_MODEL_MANAGER_RUNTIME_SERVICE.md` plus safe templates under
  `docs/examples/`: companion JSON config, `.ini` profile presets, a systemd
  user-service example, and a temporary Docker Compose override example. The
  guide is Linux-first and covers operator-owned config/runtime/log/model-root
  paths, token generation and non-commit rules, manual companion startup and
  `/health`/`/profiles`/`/models/scan` checks, Docker socket-directory mounting,
  user-service enable/status/log/stop commands, the Phase 2G8 real-profile E2E
  validation env, troubleshooting, and a security checklist. Templates use
  placeholders only (`/mnt/ai/llm-models`, `/usr/bin/llama-server`,
  `replace-with-local-token`) and avoid whole-home mounts, Docker socket,
  privileged mode, host PID namespace, host networking, host-gateway TCP, and
  committed secrets. Scope preserved: docs/templates only; no production
  backend behavior changes, frontend UI changes, Ask changes, Provider Settings
  writes, permanent Docker Compose changes, app-installed service, actual
  installer, model download manager, or app-suggested settings.
- **Local Model Manager Phase 2G9 — approved-folder setup UX + safe manual
  helper defaults** (branch `lmm-phase2g9-runtime-setup-polish`). Manual command
  helper defaults are now CPU-safe first (`-c 4096 -ngl 0 --threads 8`), with
  GPU balanced (`-c 4096 -ngl 20 --threads 8`) and low-memory
  (`-c 2048 -ngl 0 --threads 8`) presets. Full offload `-ngl 999` remains only
  as an advanced profile labeled risky / may OOM and is not default. The Local
  Models UI now explains that approved GGUF folders come from host companion
  config, the web app cannot safely browse the whole PC or pick host folders
  directly, operators must configure `approved_roots`, restart the companion,
  then scan, and manual server mode still works without the companion. The setup
  template uses placeholder values only. Saved-selection copy distinguishes an
  unconfigured companion (saved model from a previous validation/session, not
  confirmed by live scan) from a configured scan where the file is missing.
  Companion/backend library payloads may include path-free root summaries
  (`id`, `recursive`, `model_count`), which the UI displays without root paths.
  Managed Server copy now states controls require a configured host companion,
  affect only companion-managed processes, do not stop manual servers, and do
  not change Provider Settings; missing profiles point to companion config or
  preset files. Scope preserved: no true browser folder picker, no companion
  config writes, no frontend-provided host path, no Provider Settings writes, no
  Ask changes, no permanent Docker changes, no model download manager, no
  app-suggested settings, no browser storage, no token/socket/absolute host
  path/raw argv exposure, no free-form flags UI, and no whole-PC scan.
- **Local Model Manager Phase 2G8 — real configured-profile E2E validation**
  (branch `lmm-phase2g8-real-profile-e2e-validation`). Added
  `test_scripts/validate_lmm_real_profile_e2e.py`, a live/manual harness for
  the actual configured-profile path: temporary explicit companion config,
  temporary companion runtime/socket, host companion, temporary Compose override
  mounting only that runtime/socket directory into the Docker app, and backend
  calls through `http://127.0.0.1:8000`. The harness requires explicit
  `LMM_REAL_LLAMA_SERVER_BIN`, `LMM_REAL_MODEL_ROOT`, model id/pattern,
  `LMM_REAL_PORT`, `LMM_REAL_CTX_SIZE`, `LMM_REAL_GPU_LAYERS`, and
  `LMM_REAL_THREADS`; missing env exits 0 with a clear skip before Docker work.
  It calls companion status, library scan, server profiles, library selection,
  server start, server status polling, server stop, verifies port release, and
  checks redaction/root-relative paths. It skips `/api/local-model/status`
  rather than writing Provider Settings to repoint the local provider, snapshots
  and restores the app-side local-model selection file, and restores/stops Docker
  with committed Compose only. Operator-run real E2E passed with
  `/usr/bin/llama-server`, `LMM_REAL_MODEL_ROOT=/mnt/ai/llm-models`,
  `LMM_REAL_MODEL_PATTERN=gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`,
  `LMM_REAL_PORT=18080`, `LMM_REAL_CTX_SIZE=4096`,
  `LMM_REAL_GPU_LAYERS=0`, and `LMM_REAL_THREADS=8`: the backend/companion path
  selected the real profile/model, reached `running` readiness via `/v1/models`,
  stopped cleanly, and released the port. Redaction passed: no token, socket
  path, absolute model root/executable path, Authorization header, full URL, or
  raw argv in backend responses; model paths were root-relative only. GPU
  validation remains separate: the earlier `gpu_layers=999` run failed safely as
  `model_may_be_too_large` / CUDA OOM and is not a passed GPU validation. Scope
  preserved: no Provider Settings writes, Ask changes, permanent Docker changes,
  host-gateway TCP, Docker socket, privileged container, host PID namespace,
  model download manager, direct companion frontend call, or settings
  recommendations.
- **Local Model Manager Phase 2G7 — operator setup docs + safe preset import**
  (branch `lmm-phase2g7-profile-presets-docs`). Added
  `docs/LOCAL_MODEL_MANAGER_OPERATOR_SETUP.md`, a Linux-first setup guide for
  finding `llama-server`, choosing approved model roots, companion JSON config,
  safe CPU / low-memory GPU / balanced GPU profile examples, Unix socket Docker
  mount concept, backend env vars (`LMM_COMPANION_SOCKET`,
  `LMM_COMPANION_TOKEN`, `LMM_COMPANION_TIMEOUT_SECONDS`), the real validation
  harness, troubleshooting, and platform scope. Implemented optional `.ini`
  profile-default import in `tools/local_model_companion/config.py` using stdlib
  `configparser` with interpolation disabled. Preset file paths are explicit
  companion JSON only via `profile_preset_files`; imported presets require
  `llama_server_executable` in JSON and cannot supply executable paths. Imported
  sections become normal `llama_server` profiles through the same whitelist path
  used by JSON profiles. Unknown keys are rejected; duplicate ids, `DEFAULT`
  values, invalid ints/bools/enums/ranges, env expansion, shell/path-like text,
  and command/args/shell/model_path/executable/free-form flag keys are rejected.
  CPU safe and GPU balanced preset defaults avoid `gpu_layers=999`; the Phase
  2G5 record remains CPU validation passed, full offload `gpu_layers=999`
  failed safely as `model_may_be_too_large` / CUDA OOM. Scope preserved: no
  app-suggested settings, Provider Settings writes, Ask changes, permanent
  Docker Compose changes, frontend UI changes, free-form flags, raw shell
  command execution, model downloads, host-gateway TCP, Docker socket,
  privileged container, host PID namespace, or token/socket/absolute path/raw
  argv exposure.
- **Local Model Manager Phase 2G6 — real-profile UI/defaults + safe parameter
  controls** (branch `lmm-phase2g6-real-profile-controls`). Added companion
  `GET /profiles` and backend `GET /api/local-model/server/profiles` safe DTOs.
  Profile metadata exposes only ids, display names/descriptions, real/test
  marker, runnable boolean/reason, configured defaults, typed schema, and
  warnings; it never exposes executable paths, model paths, token/socket details,
  raw argv, or a companion config dump. Companion JSON profiles now support
  arbitrary safe `llama_server` ids such as `cpu_safe`/`gpu_balanced`,
  `display_name`, `description`, `warnings`, `default_parameters`, and optional
  `parameter_schema`. Missing/non-executable configured profiles remain visible
  as `runnable:false` with safe reasons like `executable_missing`.
  Start/restart payloads remain `{model_id, profile_id, parameters}` only.
  Backend rejects unknown top-level fields and unknown parameter names before
  forwarding; companion validates against the selected profile schema. Supported
  whitelist parameters are `port`, `ctx_size`, `gpu_layers`, `threads`,
  `parallel`, `cache_type_k`, `cache_type_v`, `flash_attention`, and `mmap`;
  argv mapping is centralized and no free-form flags/args/command/model_path/
  executable fields are accepted. The Local Models Managed Server UI now fetches
  profiles from the backend, picks the safest runnable profile in memory
  (`cpu_safe`, then first runnable non-test, then `fake_test`), renders typed
  number/checkbox/select controls from the selected schema, builds safe payloads
  only, and has a **Use profile defaults** reset. UI copy states high GPU layers
  can OOM, CPU is safer but slower, Provider Settings are not changed, and the
  controls affect only the companion-managed server. Manual command helper
  fallback remains. `.ini` preset import was deferred in G6 and implemented in
  G7 through the same whitelist schema; app-suggested settings remain deferred.
  Scope preserved: no
  Provider Settings writes, Ask changes, permanent Docker Compose changes,
  browser storage, direct companion frontend calls, token/socket/path/raw argv
  exposure, host-gateway TCP, Docker socket, privileged container, host PID
  namespace, model download manager, or Windows/macOS support.
- **Local Model Manager Phase 2G5 — real Linux llama-server validation and
  lifecycle hardening** (branch `lmm-phase2g5-real-llama-validation`). Companion/
  backend hardening plus validation harness. Added explicit-config real profiles
  `llama_cpp_gpu_default` / `llama_server_gpu_default`; no default real
  executable exists. Executable path comes only from companion config, is
  canonicalized, and must be executable. Model path resolves only from approved
  scanned model id. Requests still accept only whitelisted `profile_id`,
  `model_id`, and typed bounded params (`port`, `ctx_size`, `gpu_layers`,
  `threads`); no shell/free-form args/model_path/executable request fields.
  Real argv is centralized as
  `<exe> -m <model> --host <configured-safe-host> --port <port> -c <ctx_size>
  -ngl <gpu_layers> --threads <threads>`.
  Lifecycle now persists `starting` after spawn, promotes to `running` only after
  host-side `GET http://127.0.0.1:<port>/v1/models`, and records stable
  `error`/`crashed` states for failures. Launch failures do not auto-restart.
  Child stdout/stderr are captured to bounded companion-owned logs; safe
  categories include `executable_missing`, `permission_denied`, `port_in_use`,
  `model_load_failed`, `model_may_be_too_large`, `readiness_timeout`,
  `process_start_failed`, and `process_crashed`. Launch uses
  `start_new_session=True`; stop targets only a verified tracked process group
  after Linux `/proc` identity checks, and foreign/reused/uncertain PIDs are not
  killed. Backend DTOs whitelist new states/categories, and frontend copy
  displays them without adding advanced flags UI. Added
  `test_scripts/validate_lmm_real_llama_server.py`; it skips without explicit
  `LMM_REAL_LLAMA_SERVER_BIN`, `LMM_REAL_MODEL_ROOT`, and model id/pattern env,
  and when configured starts a temporary companion, scans, launches real
  `llama-server`, verifies `/v1/models`, stops, verifies port release/redaction,
  and cleans up. Operator-run real Linux `llama-server` lifecycle validation
  passed in CPU mode with `LMM_REAL_LLAMA_SERVER_BIN=/usr/bin/llama-server`,
  `LMM_REAL_MODEL_ROOT=/mnt/ai/llm-models`,
  `LMM_REAL_MODEL_PATTERN=gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`,
  `LMM_REAL_PORT=18080`, `LMM_REAL_CTX_SIZE=4096`,
  `LMM_REAL_GPU_LAYERS=0`, and `LMM_REAL_THREADS=8`: the harness launched real
  `llama-server`, reached `/v1/models`, and stopped cleanly. A full GPU/offload
  stress attempt with the same binary/model on port `8080`, `ctx_size=8192`,
  `gpu_layers=999`, and `threads=8` failed safely before readiness, was
  classified as `model_may_be_too_large`, and logs showed CUDA OOM / failed CUDA
  allocation. Do not describe high-GPU-offload validation as passed; the proven
  result is CPU-mode real lifecycle validation plus safe model-load-failure
  detection. Practical GPU defaults still need a follow-up because
  `gpu_layers=999` can be too aggressive for large models on 16GB VRAM.
  Scope preserved: no Provider Settings writes, no Ask changes, no permanent
  Docker Compose changes, no host-gateway TCP, Docker socket, privileged
  container, host PID namespace, browser storage, automatic restart loop, model
  download manager, multi-server pool, Windows/macOS process control, or
  Ollama/simple-local-model implementation.
- **Local Model Manager Phase 2G4 — Local Models managed-server UI controls**
  (branch `lmm-phase2g4-process-ui`). Frontend/client/tests/docs only. Added API
  helpers for the existing Phase 2G3 bridge:
  `getLocalModelServerStatus()` → `GET /api/local-model/server/status`,
  `startLocalModelServer(payload)` → `POST /api/local-model/server/start`,
  `stopLocalModelServer(payload)` → `POST /api/local-model/server/stop`, and
  `restartLocalModelServer(payload)` → `POST /api/local-model/server/restart`.
  The Local Models panel now has a **Managed Server** section that fetches server
  status on load, uses the saved selected library model for start/restart, keeps
  the selected-model preview visible, and keeps the manual command helper
  fallback visible. Start/restart payloads include only
  `{model_id, profile_id: "fake_test", parameters: {port: 18080, ctx_size: 2048,
  gpu_layers: 0, threads: 2}}`; stop sends only `{grace_seconds: 5}`. The
  `fake_test` profile is clearly labeled as validation/test only. Controls are
  disabled when the companion is unavailable or no saved selected model exists;
  stop/restart require a companion-managed running state. Copy states that this
  controls only the companion-managed test/server process, manual servers are not
  stopped, and Provider Settings are not changed. No backend route addition,
  Docker Compose change, Provider Settings write, Ask change, local provider
  base URL/model behavior change, direct companion frontend call, real
  `llama-server` validation, host-gateway TCP, Docker socket, privileged
  container, host PID namespace, browser storage, free-form command args UI,
  arbitrary JSON editor, `dangerouslySetInnerHTML`, token/socket/Authorization
  exposure, raw absolute path rendering, or raw argv exposure was added.
  `frontend/scripts/verify-local-model-library.mjs` now verifies process API
  helper paths/methods, safe payload shape, disabled/no-selection state, manual
  helper fallback, companion-managed-only stop copy, no Provider Settings/Ask
  calls, no browser storage/raw HTML, no token/socket/Authorization UI strings,
  no raw absolute path rendering, and managed status/error normalization.
  Validation passed: frontend local-model library/status/command checks,
  frontend build (existing Vite large-chunk warning only), requested backend/
  process suites, `python -m compileall api pipeline tools`, `git diff --check`,
  `docker compose config >/tmp/compose-check.txt` exit 0, and manual/live
  fake-companion direct-backend validation 22/22 with a temporary Compose
  override. Live validation saved a fake GGUF selection, started the `fake_test`
  profile, confirmed running status, stopped it, confirmed stopped status,
  passed redaction checks, and restored the app with committed Compose only.
- **Local Model Manager Phase 2G3 — backend process bridge** (branch
  `lmm-phase2g3-backend-process-bridge`). Added backend-only FastAPI routes
  `GET /api/local-model/server/status`, `POST /api/local-model/server/start`,
  `POST /api/local-model/server/stop`, and
  `POST /api/local-model/server/restart`. The bridge extends
  `pipeline/local_model_companion_client.py` to call companion Unix-socket
  endpoints `GET /server/status`, `POST /server/start`, `POST /server/stop`, and
  `POST /server/restart` with server-side `Authorization: Bearer <token>` from
  `LMM_COMPANION_TOKEN`, socket path from `LMM_COMPANION_SOCKET`, and optional
  `LMM_COMPANION_TIMEOUT_SECONDS`. Start forwards only `model_id`, `profile_id`,
  and typed bounded params (`port`, `ctx_size`, `gpu_layers`, `threads`); stop
  forwards only bounded `grace_seconds`; restart forwards either explicit start
  payload or `{reuse_last: true}`. Unknown top-level fields and unknown parameter
  fields are rejected as safe `bad_request` DTOs before any socket request.
  Responses are whitelisted to `ok`, `configured`, `reachable`, `state`,
  `managed`, `model_id`, `profile_id`, `port`, `started_at`, `error`, and
  bounded/redacted `log_tail`; pid, params, executable path, private model path,
  raw argv, token, socket path, Authorization, absolute host paths, full URLs,
  tracebacks, and low-level socket details are not returned. No frontend UI,
  Docker Compose change, Provider Settings write, Ask change, local provider
  base URL/model behavior change, direct host filesystem scan, direct host
  process control, host-gateway TCP, Docker socket, privileged container, host
  PID namespace, subprocess/shell execution in the backend bridge, real
  `llama-server` validation, or free-form command args were added. New focused
  test: `test_scripts/test_local_model_companion_process_bridge.py`. Validation
  passed across the requested backend/frontend suites, compileall, frontend
  build, `git diff --check`, and Compose config. Manual fake-companion live
  validation through `http://127.0.0.1:8000` passed with a temporary `/tmp`
  Compose override; the app was restored afterward with committed Compose only.
- **Local Model Manager Phase 2G2 — companion HTTP process API** (branch
  `lmm-phase2g2-companion-process-api`). Added host-companion-only Unix-socket
  endpoints `GET /server/status`, `POST /server/start`, `POST /server/stop`, and
  `POST /server/restart`, all behind the existing companion bearer token auth.
  The HTTP handlers parse bounded JSON, reject unknown top-level fields with
  `bad_request`, expose safe lifecycle categories, and delegate start/stop/status
  to the Phase 2G1 process manager. Handlers do not call `subprocess.Popen`.
  Start/restart explicit payloads accept only `model_id`, whitelisted
  `profile_id`, and typed `parameters`; stop accepts only `grace_seconds`;
  `reuse_last` restart is allowed only when prior launch metadata exists. The
  companion config may now include `process_runtime_dir` and
  `profiles.fake_test.executable`; no default real executable is configured.
  HTTP DTOs expose only `ok`, `state`, `managed`, `model_id`, `profile_id`,
  `port`, `started_at`, `error`, and bounded/redacted `log_tail`; token, socket
  path, absolute host paths, executable path, raw argv, Authorization, and full
  URLs are not returned. Tests use a temp fake executable and fake `.gguf` files
  only; this sandbox denies Unix/TCP socket creation, so the new process API test
  uses an in-memory handler fallback and monkeypatches only the test manager port
  probe. No backend FastAPI server routes, frontend start/stop UI, Docker changes,
  Provider Settings writes, Ask changes, backend bridge start/stop, real
  `llama-server` validation, host-gateway TCP, Docker socket, privileged
  container, host PID namespace, shell execution, or free-form command args were
  added.
- **Local Model Manager Phase 2G1 — companion process-control internals**
  (branch `lmm-phase2g1-companion-process-internals`). Added companion-private
  lifecycle code only: `tools/local_model_companion/profiles.py` defines typed,
  bounded launch profiles plus the explicit `fake_test` profile constructor, and
  `tools/local_model_companion/process_manager.py` defines
  `ManagedServerProcessManager`, `start_managed_server`,
  `stop_managed_server`, and `get_managed_server_status`. Start resolves selected
  model ids against approved-root GGUF records, re-canonicalizes model paths
  inside configured roots, validates profile ids and typed params, validates a
  companion/test-configured executable path, checks port availability, builds argv
  arrays only, and launches with `subprocess.Popen(..., shell=False)`. Status and
  stop use Linux `/proc` PID identity checks; stale/reused/foreign PIDs are never
  killed. Active process state is written atomically to
  `managed_server_state.json` in a companion-owned runtime dir and includes pid,
  model/root/profile ids, port, params, started_at, executable metadata,
  redacted argv metadata, private model path, status, last error, and log path; it
  stores no token. Logs go to `managed_server.log`; safe DTOs expose only bounded
  redacted tails. The focused test creates a temporary fake Python executable
  that stays alive, prints predictable output/redaction bait, handles SIGTERM, and
  is cleaned up. No FastAPI backend route, frontend UI, Docker Compose change,
  Provider Settings write, Ask change, backend bridge start/stop, companion
  `/server/start`/`stop`/`restart` HTTP endpoint, real `llama-server` launch,
  shell execution, free-form args, host-gateway TCP, Docker socket, privileged
  container, or host PID namespace was added.
- **Local Model Manager Phase 2F — start/stop design review** (branch
  `lmm-phase2f-start-stop-design`). Docs-only safety review before implementing
  any `llama-server` process control. Updated
  `docs/LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md` with the future companion API
  contract for `GET /server/status`, `POST /server/start`,
  `POST /server/stop`, and `POST /server/restart`; backend bridge targets
  `GET /api/local-model/server/status`, `POST /api/local-model/server/start`,
  `POST /api/local-model/server/stop`, and
  `POST /api/local-model/server/restart`; and the future Local Models UI
  contract. The process-control boundary is reaffirmed: Docker FastAPI never
  directly starts/stops host processes; only the host companion may spawn
  `llama-server`; the companion may stop only a tracked process it started; no
  Docker socket, privileged container, host PID namespace, or direct
  Docker-to-host spawn; Linux Docker control remains Unix-socket-first with token
  auth; frontend never receives token/socket/Authorization/raw host paths. Start
  accepts only selected `model_id`, whitelisted `profile_id`, and typed bounded
  params (`port`, `ctx_size`, `gpu_layers`, `threads`, optional `batch_size`) with
  no shell command, no free-form args, no arbitrary executable path, and no
  frontend/backend model path. Stop refuses to kill stale/reused/foreign PIDs.
  Restart requires a fresh validated start payload or `reuse_last: true` only
  when last launch metadata still validates. Added threat model, allowed states,
  whitelisted profiles (`gpu_default`, `cpu`, later `low_memory`), process state
  file rules, Linux `/proc` stale-PID checks, port conflict handling, bounded and
  redacted logs, host-side health checks, backend/UI safety rules, future tests,
  rollout slices Phase 2G1-G5, and a lasting `DECISIONS.md` entry. No code,
  companion implementation, backend endpoint, frontend UI, Docker change,
  Provider Settings write, Ask change, dependency, subprocess launch, or
  `llama-server` start/stop/restart implementation was added. Validation:
  `python -m compileall api pipeline tools`, `git diff --check`, and docs-only
  `git diff --name-only`.
- **Local Model Manager Phase 2E — selected library model handoff** (branch
  `lmm-phase2e-selected-model-handoff`). Backend/frontend/docs/tests slice. Added
  app-side persistence for a chosen discovered GGUF model without starting
  anything. New backend endpoints:
  `GET /api/local-model/library/selection`,
  `POST /api/local-model/library/selection`, and
  `DELETE /api/local-model/library/selection`. Storage is
  `config/local_model_library_selection.json` with schema
  `{version: 1, selected: null | safe_model}`; only safe selected-model metadata is
  stored: `id`, `display_name`, `filename`, root-relative `relative_path`,
  `root_id`, `size_bytes`, `modified_at`, `family_hint`, `quant_hint`,
  `server_compatible`, and `selected_at`. Writes are atomic temp-file +
  `os.replace`. POST prefers validating `model_id` against the cached companion
  library when available and otherwise accepts a sanitized safe snapshot. Absolute
  `relative_path` values are dropped; unknown fields are dropped; path/token/auth/
  full-URL-like strings are redacted. `GET /api/local-model/command-profile` now
  also includes `selected_library_model` and a non-runnable
  `future_launch_preview` (`model_id`, filename, root-relative path, root id,
  `gpu_default` profile placeholder, companion-model-id resolver). The Local
  Models panel fetches saved selection on load, lets a clicked model be persisted
  via **Remember selected model**, shows the saved **Chosen library model**, marks
  saved selections stale when absent from the current library, shows **Clear
  selection**, and keeps the existing manual command helper available. No Provider
  Settings write, Ask change, Docker change, local provider base URL/model change,
  browser storage, raw companion token/socket/Authorization exposure, absolute
  host path exposure, start/stop/restart route/UI, subprocess/shell execution, or
  `llama-server` process launch was added. Validation passed: new backend
  selection 14/14, companion bridge 14/14 (FastAPI route inspection skipped in host
  Python), companion scan 21/21, local-model status 17/17, command profile 13/13,
  compileall, frontend local-model library/status/command checks, and frontend
  build with the existing Vite large-chunk warning only.
- **Local Model Manager Phase 2D — Local Models UI model-library picker** (branch
  `lmm-phase2d-model-library-ui`). Frontend/client/tests/docs only. Added a compact
  **Model Library** section inside the existing Local Models panel. New frontend
  API helpers: `getLocalModelCompanionStatus()` →
  `GET /api/local-model/companion/status`, `getLocalModelLibrary()` →
  `GET /api/local-model/library`, and `scanLocalModelLibrary()` →
  `POST /api/local-model/library/scan`. The panel fetches companion status and
  cached library on open, shows safe states for unconfigured/offline/auth
  failed/reachable/endpoint-unavailable/no-roots/no-models/warnings, and renders
  discovered GGUF models using only whitelisted fields: `display_name`, `filename`,
  `relative_path`, `root_id`, formatted `size_bytes`, formatted `modified_at`,
  `family_hint`, `quant_hint`, and `server_compatible`. Clicking a model only sets
  React UI state for visual selection; it does not write Provider Settings, change
  the default local model/base URL, persist to browser storage, affect Ask, or run
  any process. Existing Phase 1 manual command helper remains visible/usable when
  companion discovery is unavailable. No backend endpoint, Docker change,
  dependency, token/socket/Authorization exposure, absolute host path rendering,
  `dangerouslySetInnerHTML`, localStorage/sessionStorage, start/stop/restart route,
  or `llama-server` process control was added. Added pure helper
  `frontend/src/localModelLibrary.js` and verifier
  `frontend/scripts/verify-local-model-library.mjs` wired as
  `npm --prefix frontend run test:local-model-library`.
- **Local Model Manager Phase 2C socket-mount validation harness** (branch
  `lmm-phase2c-socket-mount-validation`). Added
  `test_scripts/validate_lmm_companion_socket_mount.py`, a manual/live validation
  harness for the deployed Docker app container reaching a host companion through
  a mounted Unix domain socket. The harness creates a temporary `/tmp`
  validation workspace, fake approved model root, fake `.gguf` files plus one
  non-GGUF file, explicit companion config, and a temporary Compose override. The
  override mounts only the temp runtime directory into service `app` and sets
  server-side `LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`, and
  `LMM_COMPANION_TIMEOUT_SECONDS`; it is removed during cleanup and no committed
  Compose or `.env` file is changed. It starts the host companion with
  `python -m tools.local_model_companion.companion --config <config> serve
  --socket <socket>`, waits for companion `/health`, starts/restores the Docker
  app through Compose, waits for `http://127.0.0.1:8000/api/health`, then calls
  `GET /api/local-model/companion/status`, `GET /api/local-model/library`,
  `POST /api/local-model/library/scan`, and `GET /api/local-model/library`. It
  asserts configured/reachable status, `scan` capability, safe pre-scan library,
  fake GGUF models returned, non-GGUF excluded, root-relative `relative_path`, and
  no token/socket/temp absolute host path leaks in backend responses. It also
  asserts `POST /api/local-model/server/start`, `/stop`, and `/restart` are
  unavailable. No frontend UI, production Docker Compose change, Provider
  Settings write, Ask change, host-gateway TCP, Docker socket, privileged
  container, host PID namespace, `llama-server` launch, or model process control
  was added. Live validation passed 17/17: status configured/reachable with
  `scan`, pre-scan library safe/empty, scan returned two fake GGUF models and
  excluded `notes.txt`, post-scan cache returned both models, redaction checks
  passed, process-control probes were unavailable (`405`), and the app service was
  restored healthy with committed Compose only.
- **Local Model Manager Phase 2C — read-only backend bridge to the host companion
  model library** (branch `lmm-phase2c-backend-companion-bridge`). Added
  `pipeline/local_model_companion_client.py`, wired `api/server.py`, and added
  `test_scripts/test_local_model_companion_bridge.py`. New backend endpoints:
  `GET /api/local-model/companion/status`, `GET /api/local-model/library`, and
  `POST /api/local-model/library/scan`. Config is server-side env only:
  `LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`, optional
  `LMM_COMPANION_TIMEOUT_SECONDS`. The bridge is a small stdlib Unix-socket HTTP
  client that sends `Authorization: Bearer <token>`, parses JSON with bounded
  timeout/body size, and normalizes failures to safe categories:
  `companion_config`, `companion_offline`, `companion_auth`,
  `companion_timeout`, `companion_error`. It whitelists model records to safe
  fields only, rejects absolute `relative_path` values, redacts tokens/auth text,
  raw socket paths, URLs, and absolute paths from responses/warnings, bounds
  warnings, and never exposes the raw token or socket path. `GET /library` reads
  cached companion models only; `POST /library/scan` delegates scanning to the
  companion. No frontend UI, Docker Compose mount, Provider Settings write, Ask
  change, local provider base-URL change, host-gateway TCP, direct host filesystem
  scan, process control, model launch, start/stop/restart route, shell execution,
  subprocess usage in the bridge, or new dependency was added. Validation passed:
  companion bridge 14/14 (FastAPI route introspection skipped in host Python
  because FastAPI is unavailable), companion scan 21/21 with the known sandbox
  AF_UNIX bind skip, local-model status 17/17, command profile 13/13, compileall,
  frontend local-model status/command checks, frontend build with the existing Vite
  large-chunk warning only, `git diff --check`, and Compose config exit 0.
- **Local Model Manager Phase 2B — companion approved-folder GGUF scanning
  prototype** (branch `lmm-phase2b-companion-scan`). Added stdlib-only host
  companion code under `tools/local_model_companion/`: explicit config loading,
  bounded approved-root `.gguf` scanner, safe model metadata, CLI, and a minimal
  Unix-domain-socket HTTP API. Config shape:
  `{"approved_roots":[{"id":"default","path":"/home/user/models","recursive":true}],"token":"optional-local-companion-token"}`.
  The config path must be supplied via `--config` or `LMM_COMPANION_CONFIG`; no
  default home scan, no implicit `~/models`, and no silent approved-root creation.
  Missing config returns no models plus a bounded `no_approved_roots` warning. The
  scanner canonicalizes roots/candidates, accepts `.gguf` case-insensitively,
  resolves symlink files and requires the resolved target to remain inside the
  approved root, rejects symlink escapes/traversal, skips symlinked directories,
  supports optional recursion, bounds files/models/time/warnings, and returns only
  safe records with stable opaque ids, root-relative paths, size, modified time,
  family/quant hints, and `server_compatible: true`. Implemented socket endpoints:
  `GET /health`, `GET /models` cached read, `POST /models/scan` explicit scan, all
  requiring `Authorization: Bearer <token>` from `LMM_COMPANION_TOKEN` or config.
  No backend bridge, frontend UI, Docker change, Provider Settings change, Ask
  change, dependency, model execution, whole-PC/home scan, arbitrary host path scan,
  shell execution, subprocess use, or `llama-server` process control was added.
  Focused test `python test_scripts/test_local_model_companion_scan.py` passed
  21/21; the sandbox denies AF_UNIX bind, so the socket runtime bind section is
  reported as implementation-shape checked/skipped by sandbox.
- **Local Model Manager Phase 2A — host companion + approved GGUF model library
  DESIGN** (branch `lmm-phase2-host-companion-design`). New doc:
  `docs/LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md`; reconciled
  `CURRENT_TASK.md`, `PROJECT_CONTEXT.md`, `LOCAL_MODEL_MANAGER_DESIGN.md`, and
  `DECISIONS.md`. The future architecture is React UI → Docker FastAPI backend →
  Unix-socket-first token-authenticated host companion → approved model directory
  scan → host `llama-server` process lifecycle. For Linux Docker, Phase 2B assumes
  a Unix domain socket mounted into the backend container; a host `127.0.0.1`-only
  companion is not assumed reachable from Docker. Host-gateway TCP is only an
  explicit alternative with operator sign-off, Docker-bridge firewall restriction,
  and token auth. Host networking/native packaging can use loopback, but is not the
  default Docker design. The React UI never talks directly to the companion; the
  backend reads the companion token/connection config server-side only and redacts
  host paths; Provider Settings remains the config writer unless a later accepted
  design deliberately changes that. Model scanning is explicit and limited to one
  or more user-approved roots, with canonicalized paths, safe symlink policy,
  `.gguf` only, and no whole-PC/home-default scan. Start requests use a model id
  plus whitelisted profile id and typed parameters only; no free-form args or shell
  strings. The companion may stop only the tracked process it started. If the
  companion is absent, the UI should fall back to the Phase 1 manual command helper.
  `llama-server` may still bind `--host 0.0.0.0` for the model `/v1` API so Docker
  can reach it; that is separate from the companion control API, which must never
  be public. **No
  companion implementation, backend endpoint, frontend UI, Docker change, process
  spawn, model scanning implementation, Provider Settings change, Ask behavior
  change, upload, dependency, or code edit was made.**
- **Compatibility fix — Ask local direct-answer guard** (branch
  `ask-local-direct-answer-guard`). Manual local llama-server testing with
  `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf` showed `/v1/chat/completions` can return HTTP
  200 with `choices[0].message.content == ""`, visible reasoning only in
  `reasoning_content`, and `finish_reason == "length"` unless explicitly instructed
  to put the answer in normal assistant content. The system-only guard helped tiny
  prompts but failed in the full Ask prompt, while adding `/no_think` in the
  model-facing user message produced visible content. `pipeline/ask_sessions.py`
  now keeps the concise direct-answer system rules and also inserts a standalone
  `/no_think` local thinking-model control immediately before the final `User
  question:` block assembled for `generate_chat_completion`. The marker is not user
  content: it is never appended to `history.jsonl`, returned by session load/list
  endpoints, included in session summaries, or rendered by the frontend. Citation
  and grounding rules are unchanged. `test_scripts/test_ask_local_chat.py` asserts
  the marker is present in model prompts, absent from stored/frontend-visible
  messages and summaries, citation rules remain present, empty-response handling
  still works, successful answers still work, and raw prompts/chunk text/secrets/full
  URLs/paths stay hidden. Verified: Ask local chat 45/45 pure checks passed with
  endpoint skip because FastAPI is unavailable in the host Python; inventory 11/11
  and prepare 28/28 passed with the same endpoint skips; `python -m compileall api
  pipeline`, frontend Ask checks, frontend build, and release smoke all passed;
  `docker compose config >/tmp/compose-check.txt` exit 0. Docker app was
  rebuilt/restarted healthy. Live Ask against reachable local Gemma returned
  `status: answered` with visible assistant content instead of
  `provider_empty_response`; session load/list/history did not expose `/no_think`.
  Headless Chromium verified the rebuilt browser shell is served; full browser
  click/send replay was not automated in this repo.
- **Bugfix — Ask empty local-model response guard** (branch
  `ask-empty-response-guard`). During manual Ask UI validation after the
  math/source polish slice, a browser Ask message returned
  `POST /api/ask/sessions/{session_id}/message` → 500. The traceback showed
  `generate_chat_completion` raised
  `RuntimeError("LLM returned an empty response.")`; Ask did not catch it, so
  FastAPI returned raw 500 text. `pipeline/ask_sessions.py` now catches that narrow
  empty local-model RuntimeError response case and returns a safe structured
  `provider_error` response with `error.category: provider_empty_response` and a
  retryable user-safe message. The failed turn does not append a successful
  user/assistant message to history. Local-only behavior is unchanged: no retrieval,
  prompt assembly, model fallback, citation validation, session management,
  clear/delete, provider settings, streaming, uploads, rolling summary, multimodal,
  or process-control behavior changed. `test_scripts/test_ask_local_chat.py` has
  focused coverage. Verified: `python test_scripts/test_ask_local_chat.py` 38/38
  passed with endpoint section skipped because plain Python lacks FastAPI; inventory
  11/11 and prepare 28/28 passed with endpoint skips for missing FastAPI;
  `.venv/bin/python -m compileall api pipeline` passed; `npm --prefix frontend run
  test:ask-guide` passed; `npm --prefix frontend run build` passed; `docker compose
  config >/tmp/compose-check.txt` exit 0; `.venv/bin/python
  test_scripts/smoke_release.py` ran 27/28 with one existing-looking non-Ask
  outline-ordering failure. Docker app was rebuilt/restarted and healthy. The
  original empty local-model behavior was not reproducible, but the simulated
  regression is now covered.
- **Ask Your Guide — chat math/source visual polish** (branch
  `ask-chat-math-source-polish`). Frontend-only polish in
  `frontend/src/askGuide.js`, `frontend/src/components/AskGuideWorkspace.jsx`, and
  `frontend/scripts/verify-ask-guide.mjs`. Added inert math-aware answer parsing for
  `$$...$$`, `\[...\]`, `\(...\)`, and escaped-dollar inline math. Display math now
  renders as readable monospace blocks preserving line breaks; inline math renders as
  small monospace chips. No `dangerouslySetInnerHTML`, no markdown dependency, no
  KaTeX/MathJax, and no new dependency. Trusted backend-used citations now appear in
  a clearer **Sources used** section; unsupported citations remain warning-only and
  are not trusted chips. Retrieved chunk metadata stays collapsed and shows cleaner
  label/type/page/score/token rows; chunk text is still never rendered. Local-only
  Ask behavior and session management are unchanged: no backend retrieval, prompt
  assembly, model-call, citation-validation, session, clear/delete, or lazy session
  creation logic changed. **No extra uploads, streaming, hosted/cloud Ask mode,
  DeepSeek/Qwen fallback, rolling summary, multimodal, local model process control,
  provider settings writes, browser storage, or new dependency.** Validation: root
  `npm run test:ask-guide` failed because the root package has no such script;
  `frontend` `npm run test:ask-guide` passed; `frontend` `npm run build` passed with
  the existing Vite chunk-size warning; `frontend` local-model command/status checks
  passed; `python -m compileall api pipeline` passed; Ask local-chat, inventory, and
  prepare scripts passed pure checks with host endpoint sections skipped because
  FastAPI is unavailable; release smoke passed **28/28**; compose config exit 0.
  Manual UI validation after this slice found the empty local-model response guard
  bug recorded above; keep any further manual Ask polish narrow and bug-driven.
- **Ask Your Guide — session management UI/API** (branch `ask-session-management`).
  Adds `GET /api/ask/jobs/{job_id}/sessions`,
  `DELETE /api/ask/sessions/{session_id}/history`, and
  `DELETE /api/ask/sessions/{session_id}`. Session listing returns safe summaries
  only: id/job/title, created/updated times, cheap message count, and a redacted
  bounded last-message snippet. Clear history empties `history.jsonl`, keeps the
  session id/metadata and prepared context cache, and updates metadata. Delete removes
  only the fenced session directory under the parent job and never touches guide,
  source, manifest, other sessions, or `ask/cache`. The Ask workspace now lists chats
  for the selected guide in a compact rail panel, can switch sessions, start a new
  chat without re-preparing context, clear the active chat, and delete the active
  session while selecting the next newest session when available. Lazy session creation
  on first send still works. **No extra uploads, chat export, streaming, cloud
  fallback, hosted selector, DeepSeek/Qwen fallback, rolling summary, multimodal,
  process control, provider settings writes, browser storage, or new dependency.**
  Verified: `npm run test:ask-guide`, `npm run build`, `python
  test_scripts/test_ask_local_chat.py` pure checks, Ask inventory/prepare pure checks,
  `python -m compileall api pipeline`, local-model frontend checks, release smoke
  28/28, and compose config exit 0. Host endpoint portions skipped because FastAPI is
  not installed; the running Docker image was healthy but did not include
  `test_scripts/`.
- **Ask Your Guide — chat polish + emitted-citation validation** (branch
  `ask-chat-polish-citations`). The local-only Ask message endpoint now validates
  bracket-style citations emitted by the model against the exact citation labels
  retrieved for the turn. Unsupported Ask-looking citations are stripped from the
  returned/stored answer and reported via `citations_unsupported` +
  `citation_validation`; normal bracketed prose is preserved. Responses also include
  `citations_allowed` and `citations_used`, with trusted `citations` mirroring used
  citations. The prompt still requires grounding/exact labels but now asks for fewer,
  clearer citations at paragraph ends or in a short sources line. Frontend polish:
  safe attachment-summary formatting fixes `Guide only · [object Object]`, full
  `ask_...` session ids are hidden behind a friendly status label, assistant answers
  render through a tiny inert heading/bold/list/preformatted subset renderer (no
  `dangerouslySetInnerHTML`, no markdown dependency), unsupported citations show a
  subtle warning and are not trusted chips, and retrieved chunk metadata is collapsed
  by default behind `Sources used` / `Show retrieved chunks`. **No chunk text, raw
  prompts, keys, full URLs, browser storage, extra uploads, streaming, cloud fallback,
  hosted selector, DeepSeek/Qwen fallback, local model process control, provider
  settings writes, or new dependency.** Verified: `npm run test:ask-guide`,
  `npm run build`, `npm run test:local-model-command`,
  `npm run test:local-model-status`, pure portions of the three Ask Python scripts on
  the host, `python -m compileall api pipeline`, and compose config exit 0. Host
  endpoint portions skipped because FastAPI is not installed; the running Docker image
  was healthy but did not include `test_scripts/`.
- **Ask Your Guide — frontend chat UI wiring (FRONTEND)** (branch `ask-chat-ui`).
  The existing `Ask Guide` workspace now consumes the backend local chat API:
  guide/context inventory and explicit prepare still use
  `GET /api/ask/jobs`, `GET /api/ask/jobs/{id}/context`, and
  `POST /api/ask/jobs/{id}/prepare`; chat uses lazy
  `POST /api/ask/jobs/{id}/sessions`, then `GET /api/ask/sessions/{session_id}`,
  then non-streaming `POST /api/ask/sessions/{session_id}/message`. The composer is
  enabled only when a guide is selected, context inventory is ready, prepare has
  succeeded, local model status is reachable, and no message is sending. It renders
  bounded history, answer text as plain text, backend-returned citation chips, safe
  retrieved chunk metadata only (id/source/page/tokens/score, **no chunk text**),
  and safe local model info. Offline/unconfigured local keeps the composer disabled
  and reuses the LMM command helper; failures keep the draft available for retry.
  Frontend normalizers redact obvious `sk-*` keys, Authorization bearer headers, full
  URLs, and host paths before storing/rendering; there is no browser storage
  persistence and no `dangerouslySetInnerHTML`. **No backend chat behavior change, no
  extra uploads, no export, no citation-validation backend slice, no rolling-summary
  UI, no streaming, no cloud fallback, no hosted selector, no DeepSeek/Qwen fallback,
  no process control, no provider writes, no dependency.** Verified:
  `npm run test:ask-guide`, `npm run build`, `npm run test:local-model-command`,
  `npm run test:local-model-status`, Ask backend regressions in Docker
  (`test_ask_context_inventory.py` 50/50, `test_ask_context_prepare.py` 58/58,
  `test_ask_local_chat.py` 40/40), release smoke 28/28, and compose config exit 0.
- **Ask Your Guide — backend local chat API (BACKEND ONLY)** (branch
  `ask-local-chat-api`). Adds `POST /api/ask/jobs/{job_id}/sessions`,
  `GET /api/ask/sessions/{session_id}`, and
  `POST /api/ask/sessions/{session_id}/message`. Sessions live under
  `jobs/<job_id>/ask/sessions/<session_id>/` with `session.json` (atomic) and
  `history.jsonl` (append-only). Unknown job → 404; guide-less job → safe
  `not_ready`; load returns safe metadata + bounded history. Message validates
  non-empty/max-length input, checks LMM/local status first, and if local is offline
  returns structured `local_offline` without model/config calls. If local is ready,
  it synchronously prepares/reuses the Slice 3 context cache, performs pure lexical
  retrieval over cached term frequencies + `doc_freq` (top 8, approx 3k-token pool,
  `chars/4`), assembles hard answer rules + citation-labelled chunks + small recent
  history, and calls only `build_provider_config("local", selected_model, ...)` +
  `generate_chat_completion`. Responses include answer text, allowed citation labels,
  safe retrieved-chunk metadata (no chunk text), session id, and safe local model
  status. **No frontend/UI changes, no extra uploads, no cloud fallback, no
  DeepSeek/Qwen fallback, no streaming, no rolling summary, no generation jobs, no
  dependency, no artifact mutation.** Obvious raw keys/Authorization bearer headers/
  full URLs are masked before Ask cache/session persistence and responses. Verified:
  `test_ask_local_chat.py` 40/40, inventory 50/50, prepare 58/58, compileall pass,
  compose config exit 0, release smoke 28/28.
- **Ask Your Guide — inserted workspace shell slice (FRONTEND ONLY)** (branch
  `ask-workspace-shell`). Adds a first-class `Ask Guide` sidebar workspace with the
  design-doc three-region shape: guide picker (left), disabled chat/readiness panel
  (center), and selected-guide/context/local-model rail (right). It consumes existing
  summary-only endpoints: `GET /api/ask/jobs`, `GET /api/ask/jobs/{job_id}/context`,
  `POST /api/ask/jobs/{job_id}/prepare`, plus existing LMM `GET
  /api/local-model/status` and `GET /api/local-model/command-profile`. It shows eligible
  guides, safe metadata, readiness reasons, guide/source counts, attachment/page
  summaries, prepare cache status + chunk counts + citation samples, and local model
  offline/reachable state with the manual command helper. **No backend chat route, no
  sessions, no `/api/ask/sessions`, no model/local-model call, no DeepSeek/Qwen/cloud
  fallback, no extra uploads, no chat persistence, no artifact mutation, no dependency.**
  The composer is disabled with "chat lands next" copy. New pure helper
  `frontend/src/askGuide.js` basenames attachment/page-selection names and renders only
  safe summaries (no guide/source body, chunk text, raw key, full URL, or host path).
  Verified: `npm run test:ask-guide`, `npm run test:local-model-command`,
  `npm run test:local-model-status`, `npm run build`.
- **Ask Your Guide — Slice 3: backend context preparation / chunking (BACKEND ONLY)**
  (branch `ask-context-prepare`). New stdlib-only `pipeline/ask_context.py` chunks
  `clean.md` (guide) + optional `extracted.txt` (source) deterministically on heading /
  `## Page N` boundaries (~650-token target, ~800 ceiling via `chars/4`, no overlap),
  preserving each chunk's **citation label** (nearest guide heading / `Page N` + page
  number) and building a **dependency-free lexical index** (per-chunk term frequencies +
  `doc_freq`). `POST /api/ask/jobs/{id}/prepare` (before the SPA mount) builds OR reuses
  a cache at `jobs/<id>/ask/cache/context_index.json`, keyed by a **content hash** over
  guide+source bytes — **idempotent** (`hit` rewrites nothing; `clean.md`/`extracted.txt`
  change → `rebuilt`; corrupt/stale cache → safe rebuild), **atomic** (temp +
  `os.replace`), **fenced** to the job dir. Unknown job → 404; guide-less existing job →
  200 `ready:false`. Response is an explicit whitelist (`job_id`, `ready`, `cache_status`,
  `content_hash`, guide/source/total chunk counts, bounded `citation_summary`,
  job-relative `cache_relpath`) — **no guide/source body, chunk text, key, full URL, or
  host path**; the cache holds chunk text for Slice 4 but only whitelisted top-level keys
  (never the manifest). **No chat, no retrieval endpoint, no model/local-model call, no
  cloud key read, no sessions, no extra uploads, no UI, no new dependency; original
  artifacts untouched (no `save_clean_md`, no manifest write).** Verified: `compileall`
  OK, `docker compose config` exit 0, container healthy,
  `test_scripts/test_ask_context_prepare.py` **58/58 in Docker**, Slice 2
  `test_ask_context_inventory.py` **50/50** unchanged, live prepare→hit on a real job +
  clean response/cache secret scan, read-only sha256 of `clean.md`/`extracted.txt`/
  `job.json` unchanged. See `CURRENT_TASK.md` #52. Historical NEXT here is superseded:
  backend local chat API, frontend chat UI wiring, chat/citation polish, and session
  management and math/source visual polish are now done; current NEXT is manual
  browser validation/polish of the Ask chat UI slice, or extra session uploads only
  as a separate explicit Ask slice.
- **Ask Your Guide — Slice 2: backend context inventory endpoint (BACKEND ONLY)**
  (branch `ask-context-inventory`). Two **read-only** endpoints over generated-guide
  artifacts: `GET /api/ask/jobs` lists **only Ask-eligible jobs** (those with a
  generated `clean.md`; guide-less / failed / incomplete jobs filtered out) with curated
  redacted picker fields (id/title/status/created+updated/style/preset/provider/model/
  favorite/attachment_summary/guide+source availability); `GET /api/ask/jobs/{id}/context`
  returns a per-job **readiness + source inventory** (guide `clean_md` present + char +
  heading counts; source `extracted.txt` present + char + `## Page N` anchor count;
  redacted attachment names/modes/extracted_chars/warnings; page selections; a
  `readiness{status,ready,reasons}` object; unknown job → 404, guide-less existing job →
  200 `not_ready`). New thin reader `pipeline/ask_inventory.py` (counts only — **never a
  guide/source body**); routes reuse the existing `_safe_manifest` /
  `_safe_attachment_metadata` / `_attachment_summary` / `_safe_page_selections`
  redaction + an explicit field whitelist, registered before the SPA mount. **No chat,
  no chunking, no retrieval/indexing, no model call, no local-model call, no cloud
  fallback, no session storage, no extra uploads, no UI; original job artifacts
  untouched (no `save_clean_md`, no manifest write).** Verified: `compileall` OK,
  `docker compose config` exit 0, image rebuilt + container healthy,
  `test_scripts/test_ask_context_inventory.py` **50/50 in Docker**, live seeded-job
  proof + clean raw-response secret scan (planted `sk-live-…`/base-URL/host-path did not
  leak), read-only sha256 of `clean.md`/`extracted.txt`/`job.json` unchanged. See
  `CURRENT_TASK.md` #51. **NEXT = Ask Slice 3 (context preparation / chunking).**
- **Ask Your Guide — Slice 1: design (docs-only)** (branch `ask-your-guide-design`).
  A design-first definition of a dedicated **Ask Your Guide** workspace
  (`docs/ASK_YOUR_GUIDE_DESIGN.md`): the user selects a generated guide/job and chats
  with it using a **local model only**. First-class page/tab (guide+session picker /
  chat / sources+citations panel), **local-only** and **status-gated** on LMM Phase 1
  (offline → first-class offline state + command helper; **no DeepSeek/Qwen/cloud
  fallback**), a **mandatory context manager** (chunk `clean.md`/`extracted.txt` with
  `## Page N`/heading citation anchors → dependency-free lexical index cached per
  `(job_id, content_hash)` → budgeted retrieval reserving answer/system-rules/recent
  chat → rolling chat summary), a hard **accuracy/citation contract**, conservative
  **session-scoped** storage (never auto-exported, no secrets), 8 proposed local-only
  endpoints (`/api/ask/*`, all read-only over job artifacts), and a 10-slice build
  plan. **No code changed.** NEXT = Ask Slice 2 (backend context inventory endpoint).
- **Local Model Manager — Phase 1 COMPLETE + VALIDATED** (Slices 1→4 +
  Slice 5 validation). Detection-only status (`GET /api/local-model/status` +
  `POST /api/local-model/check`), the read-only **Local Models** panel, and the
  manual **command helper** (`GET /api/local-model/command-profile`) are all on trunk
  (`94003bc`→`e399f09`). The **Slice 5 validation pass** (branch
  `docs-validate-local-model-manager-phase1`, docs-only, no code changed) confirmed
  every Phase-1 guarantee: static suites green, Docker container healthy, smoke 28/28,
  live `/status`+`/command-profile` 200 (offline → safe `local_offline`, placeholder
  command, host-only URL), **no-process-execution proof** (only comments assert
  absence; the command helper returns strings/argv via `shlex.quote`), and a **clean
  secret scan** (the lone JS hit was a 4-char `LOCAL_LLM_API_KEY=none` placeholder
  coinciding with `display:"none"`, not a real key). No bugs found. See
  `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md` + `CURRENT_TASK.md` #49.
- **Local Model Manager — Slice 4: command-helper profiles / Copy start command**
  (branch `local-model-command-helper`). Read-only
  `GET /api/local-model/command-profile` → `get_local_model_command_profiles()` in
  `pipeline/provider_config.py`: static, whitelisted `llama-server` start commands
  (`llama_server_default` GPU + `llama_server_cpu`) with a `/path/to/model.gguf`
  **placeholder**, `--host 0.0.0.0 --port 8080`, and safety warnings. Command built
  from a fixed flag whitelist + `argv` (rendered via `shlex.quote`); the only
  substitution is the model placeholder. Frontend: `getLocalModelCommandProfile()`
  client helper + pure `frontend/src/localModelCommand.js` + a `CommandHelper` block
  in `LocalModelsPanel.jsx` (profile chips, selectable code block, **Copy command**
  with clipboard + manual fallback, prominent when offline / collapsed when
  reachable). The deferred `copy_start_command` "Planned" chip is suppressed; the
  Slice 2 status DTO is unchanged. **Command helper only — the app NEVER executes
  it: no subprocess/spawn, no start/stop, no host companion, no GGUF scan, no
  arbitrary shell, no raw key, host-only URL.** Tests:
  `test_scripts/test_local_model_command_profile.py` 13/13;
  `frontend/scripts/verify-local-model-command.mjs` (`npm run
  test:local-model-command`); Slice 2/3 + provider suites unchanged; `npm run build`
  OK. See `CURRENT_TASK.md` #48 + `LOCAL_MODEL_MANAGER_DESIGN.md` §11 (Slice 4 note).
- **Local Model Manager — Slice 3: Local Models status panel (FRONTEND)** (branch
  `local-model-status-ui`, frontend + API client + docs/tests only). A read-only
  **Local Models** panel mounted inside the Providers (Models) page, consuming the
  Slice 2 endpoints. New API client helpers `getLocalModelStatus()` (`GET
  /api/local-model/status`) + `checkLocalModelStatus()` (`POST /api/local-model/check`);
  pure `frontend/src/localModelStatus.js` helpers (mirrors `shortcutStatus.js`) that
  normalize the DTO into `reachable | offline | not_configured | error | unknown`
  (tolerating missing fields / an old backend) with badge, model-chip
  (`limit=12` + overflow), latency/error/notes, action enabled/disabled, and a
  `hasEnabledProcessControl` invariant guard; `LocalModelsPanel.jsx` rendering a
  status pill, host-only base URL + in-Docker flag, a metrics strip, bounded model
  chips, a first-class offline/troubleshooting state (incl. the `--host 0.0.0.0`
  note), a **Refresh status** button (calls `/check`, never saves/starts), an "Edit
  local provider settings" link that scrolls to `#provider-card-local` (single
  writer), and the **disabled** "Copy start command — Planned" chip. **No process
  control, no inline base-URL editing, no raw key/URL.** Tests:
  `frontend/scripts/verify-local-model-status.mjs` 47/47 (`npm run
  test:local-model-status`); `npm run build` OK; backend suites unchanged
  (`test_local_model_status.py` 17/17, fetch-models 16/16, settings-store 26/26);
  smoke 28/28; live offline proof + clean secret scan. See `CURRENT_TASK.md` #47 +
  `LOCAL_MODEL_MANAGER_DESIGN.md` §11 (Slice 3 note).
- **Local Model Manager — Slice 2: detection-only backend status endpoint**
  (branch `local-model-status-api`, backend-only, on trunk as `e27c674`). Read-only
  `GET /api/local-model/status` + a thin `POST /api/local-model/check` alias, backed
  by `get_local_model_status()` in `pipeline/provider_config.py`. Returns a safe DTO
  (`{ok, provider, configured, base_url_host, base_url_configured, in_docker,
  reachable, models, model_count, default_model, selected_model, latency_ms, error,
  actions, notes}`). **`ok` ≠ reachable.** Connection failures normalize to a single
  `local_offline`. **No process spawn, no writes, no file browsing, no raw key,
  host-only URL.** See `CURRENT_TASK.md` #46 + `LOCAL_MODEL_MANAGER_DESIGN.md` §11.
- **Shortcut Inspector — degraded-activation confirm + "Repair instead"**
  (branch `shortcut-inspector-degraded-activation`, frontend-only). Home card
  launches now route through a pure `activationDecision` (`shortcutStatus.js` →
  `launch`/`confirm`/`blocked`): a **valid** shortcut launches immediately; a
  **degraded-yet-launchable** one (`validity.status === "degraded"` while legacy
  `valid === true`) raises a confirm dialog — **Continue anyway** (unchanged
  launch path, no mutation) / **Repair instead** (opens the existing Inspector
  drawer, no preview/apply until the user acts) / **Cancel**; a **broken** one
  (`valid === false`) stays blocked and shows a "This shortcut is broken."
  Inspect/Repair dialog instead of silently routing. Legacy `valid` is still the
  hard guard. New node harness `verify-shortcut-activation.mjs` (wired into
  `test:shortcuts`). No backend change. See `CURRENT_TASK.md` #43 +
  `SHORTCUT_INSPECTOR_REPAIR_DESIGN.md` §5.5 + `DECISIONS.md`.
- **Shortcut Inspector / Repair Loop — COMPLETE through Slice 3B**
  (`a0f96d1`→`4458c9a`, DONE #39→#42): a read-only inspector with an additive
  `validity` object (3-tier `valid`/`degraded`/`broken` status, the **full**
  findings list, and the previously-missing saved-`model` check) + `GET
  /api/shortcuts/{id}/inspect`, with the legacy `valid`/`reason` preserved
  byte-for-byte; 3-tier Home/Customize badges + a read-only Inspector drawer;
  repair endpoints `POST /api/shortcuts/{id}/repair/preview` (read-only) +
  `…/repair/apply` (the only write — explicit whitelisted patch, in-place or
  clone); and the repair UI (Keep/Replace/Remove controls, in-place vs clone,
  **Preview required before Apply**, editing the draft re-disables Apply,
  explicit confirm). No migration-on-read; preview never mutates `shortcuts.json`;
  clone mints a new id and leaves the original untouched; **card activation is
  unchanged** (still gated on legacy `valid`). Validated docs-only in
  `docs/VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md`. See `CURRENT_TASK.md` #39→#42 +
  `DECISIONS.md` (shortcut inspector/repair entries).
- **In-app provider settings feature group — COMPLETE through Slice 5**
  (`978516e`→`61fb423`): a two-file server-side store
  (`config/provider_settings.json` non-secret `0644` + `config/secrets.json`
  raw-keys-only `0600`), safe endpoints (`GET /api/provider-settings`,
  `PATCH /api/provider-settings/{provider}`, `…/clear-key`, `…/test`,
  `…/fetch-models`), a frontend Providers page (routed from the Models sidebar
  item) with a per-card **Refresh models** button, and **runtime** wiring so the
  stored `timeout_seconds`/`retry_count`/`thinking_default` reach the live model
  call. The read-only `POST …/{provider}/fetch-models` endpoint (`6da944a`) lists
  provider models without auto-persisting; the Refresh Models UI (`61fb423`) shows
  fetched ids **review-only**, stages new ids into the draft `custom_models` via
  **Add** / **Add all new**, and requires an **explicit Save** to persist (after
  which `/api/options` includes the saved custom models — Builder dropdowns keep
  reading `/api/options`). Fetching never auto-saves and never auto-switches the
  provider/default model. **Security:** raw keys stay **server-side only**;
  `/api/options`, `/api/provider-settings`, and the fetch-models response are
  **redacted** (no key field by construction — only `configured`/`key_source`/
  last-4 `key_hint`/`base_url_host`); the API key is write-only. **Precedence:**
  provider/model = **per-job request > provider-settings default > `.env` >
  built-in**; generator presets **never hard-pin** provider/model (`model_hint`
  advisory), and an **explicit** preset sampling/thinking value overrides the
  stored runtime default. No store files ⇒ byte-identical to the prior env path.
  See `CURRENT_TASK.md` #32→#36 + `DECISIONS.md` (provider-settings entries).
- **Large-PDF core workflow — COMPLETE end-to-end** (`841d3f9`→`60c3e78`): a
  read-only `POST /api/preflight/pdf` verdict (`ok`/`warn`/`blocked`), a Builder
  preflight warning card, `page_selections` (`{filename: [[start,end],…]}`,
  1-based inclusive) plumbed through the request + persisted in the manifest, the
  extractor restricting matching PDFs to the selected ORIGINAL pages (anchors
  preserved, OCR only on selected pages), and a live first-N / manual page-range
  UI. **Usable end-to-end:** preflight warns → user picks first N or a range →
  the request carries `page_selections` → extraction uses the original page
  anchors. **Automatic split/chunk processing and hybrid embedded-text + OCR
  dedup remain deferred.** See `CURRENT_TASK.md` #27→#31.
- **Cooperative server-side cancel** (`901d44b`): a `jobs/<id>/cancel.requested` marker
  checked at safe stage boundaries, a new `cancelled` terminal status,
  `POST /api/jobs/{id}/cancel`, and a Builder Cancel button. **Checkpoint-based,
  cooperative only** — it does **not** kill processes/threads; a cancel during an
  uninterruptible LLM call or Chromium render takes effect at the **next safe
  checkpoint**, not instantly. Partial artifacts and the user's uploads / Builder
  inputs / settings are **preserved** (nothing deleted; re-generate from the Builder).
  Retry-from-cancelled is deferred. See `CURRENT_TASK.md` #22.
- **B4 "Export selected"** (`65b9b8f`): the Library bulk bar gained an "Export selected"
  action reusing the existing `POST /api/exports/bundle` ZIP endpoint (no new primitive,
  no backend change). See `CURRENT_TASK.md` #21.
- **Rerender preserves `generator_preset`** (`2716995`): `retry_failed_job` now reads the
  preset from the manifest and rebuilds through it (tuned sampling params + system prompt
  reapplied), instead of dropping to the default path. A since-removed preset id degrades
  gracefully; the user's saved provider/model still wins. Backend-only.
- **Group C fully integrated** onto `chrome-renderer-v1` (squash `6f888b2`): generator
  presets + cards, output-section toggles (`include_sections`), depth/difficulty axes,
  shortcut options bridge, Builder options UI, `qwen3.7-plus`, Home/nav cleanup.
- **OCR + PDF fixes** on the trunk: re-applied `_preprocess_ocr_image` (`5bde798`), MCQ
  answer + page-reference prompt fixes (`75ec24f`), and **page-level mixed scanned/text
  PDF OCR fallback** (`72dab90` / `773209a`).
- **Docker compose hardening** (`1d51b36`): `mem_limit: 2g`, `pids_limit: 256`,
  `cpus: 2.0`, `security_opt: no-new-privileges:true` (additive, `docker compose config`
  validated). Salvaged from local-only `863f5b7`; its non-root/gosu hardening was already
  in at `6f888b2`.

## ⚠️ Old branches — do NOT re-merge
The whole Group C feature stack (`style-output-toggles`, `style-axes`,
`shortcut-options-bridge`, `builder-options-ui`, `preset-*`, `qwen37-plus-model`,
`home-nav-cleanup`, `library-*`, plus `integ-group-c` and `salvage-compose-limits`) is
**consumed/archival**. Its content already lives in the trunk. **Do not merge or rebase
any of them again** — it would reintroduce superseded code and resurrect resolved
conflicts. They are kept (not deleted) only as reference. See `DECISIONS.md`.

Local-only `61c134c` and `863f5b7` stay **parked on the `hardening` branch** — useful
pieces already salvaged; the rest is deferred (below).

## RULE for new work
**Branch from `chrome-renderer-v1` @ `e399f09` (or later) — never from an old stacked
branch.** One small slice per branch; verify (build + compile + docker + smoke) and
commit before moving on. Surgical edits, not rewrites. The PDF/Chromium pipeline is
load-bearing — do not rewrite casually.

## Next recommended slice
**Ask Your Guide — extra session uploads** are a separate optional slice only if the
operator explicitly chooses to continue Ask features. Do not start extra uploads
automatically.
- **Broader manual Ask UI validation / polish** should stay narrow and bug-driven;
  the empty local-model response regression found during manual validation is now
  guarded and covered.
- **Still deferred:** streaming, hosted/cloud Ask, rolling summary, multimodal, and
  local model process control.
- **Focused manual validation / polish of the Shortcut Inspector UI.** The
  inspect→repair loop + degraded-activation confirm are complete and validated at
  the API + harness level; the remaining gap is a human click-through of the live
  Home/Customize 3-tier badges, the Inspector drawer, the Preview→Apply / clone
  flow (incl. the stale-preview re-disable), and the new degraded/broken
  activation dialogs. Validation / polish only — no code unless a concrete UI bug
  surfaces.
- **Math/PDF font-size rationalization (cause C, CSS-only).** Optional remaining
  fidelity slice; CSS-only investigation before any change.
- **Large-PDF preflight size-limit polish — optional, later.** Raising the upload
  ceiling + preflight size thresholds is a possible later slice; **not part of any
  current slice** and not started.

(The previously-recommended **in-app provider settings** (COMPLETE through
**Slice 5** — fetch-models endpoint + Refresh Models UI), the **shortcut inspector
/ repair loop** (now COMPLETE through **Slice 3B**, `a0f96d1`→`4458c9a`),
**Math/PDF fidelity investigation**, and **Large-PDF preflight design** are **all
DONE** — provider settings shipped as #32→#36 (`978516e`→`61fb423`), the shortcut
inspector shipped as #39→#42, the preflight design shipped as Slices 1–5
(`841d3f9`→`60c3e78`), and the math/PDF fidelity Slices 1–3 shipped (#23–#25). The
provider-settings real-world validation pass also ran
(`docs/VALIDATION_PROVIDER_SETTINGS_LARGE_PDF.md`, two now-fixed findings). The
rerender `generator_preset` fix, B4 "Export selected", and server-side cancel are
also DONE and on trunk — see "What just landed". The only remaining math/PDF slice
is the optional **font-size rationalization** (cause C, CSS-only).)

## Open / deferred items
- **rerender drops `generator_preset`** — DONE (`2716995`, on trunk). Rerender now
  reproduces the preset.
- **B4 "Export selected"** — DONE (`65b9b8f`, on trunk). Reuses the existing bundle endpoint.
- **Real server-side cancel button** — DONE (`901d44b`, on trunk; cooperative,
  checkpoint-based, marker file, `cancelled` status; does not kill processes; preserves
  uploads/inputs/settings). Retry-from-cancelled still deferred (re-generate from the
  Builder instead).
- **Large-PDF core (preflight + page-range selection)** — DONE end-to-end
  (`841d3f9`→`60c3e78`, #27→#31): preflight verdict endpoint, Builder warning card,
  `page_selections` plumbing + manifest persistence, extraction honoring selected
  ORIGINAL pages (OCR only on selected pages), and the first-N / manual page-range UI.
- **Math / PDF fidelity Slices 1–3** — DONE (#23–#25). Remaining optional slice:
  **font-size rationalization** (cause C, CSS-only).
- **Large-PDF — still deferred:** automatic split/chunk processing; hybrid
  embedded-text + OCR dedup; raising the upload ceiling (`MAX_UPLOAD_MB`); persisting
  the preflight report in `job.json`; carrying page selections into drafts/shortcuts.
  None started — do not begin without an explicit slice + design.
- **In-app provider settings feature group** — DONE through Slice 5
  (`978516e`→`61fb423`, #32→#36): two-file store (non-secret
  `provider_settings.json` + `0600` `secrets.json`), redacted endpoints, Providers
  UI, runtime `timeout_seconds`/`retry_count`/`thinking_default` applied, read-only
  `fetch-models` endpoint, and the Refresh Models UI (review-only fetch → stage into
  draft `custom_models` → explicit Save). Keys stay server-side only; presets never
  hard-pin provider/model. **Still deferred:** encrypted-at-rest / OS keyring; `.env`
  import; optional Builder "Provider default" thinking UI polish.
- **Local Model Manager** — **Phase 1 COMPLETE + VALIDATED** (Slices 1→4 on trunk
  `94003bc`→`e399f09`; Slice 5 validation docs-only,
  `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`). Slice 2 =
  the detection-only backend status endpoint (`GET /api/local-model/status` + `POST
  /api/local-model/check`, `get_local_model_status()`) shipping safe fields only.
  Slice 3 = the read-only **Local Models status panel** in the Providers (Models)
  page (`LocalModelsPanel.jsx` + pure `localModelStatus.js` + the
  `getLocalModelStatus`/`checkLocalModelStatus` client helpers): status pill,
  host-only base URL, latency, model count + chips, first-class offline
  troubleshooting, **Refresh status**, and an "Edit local provider settings" link to
  the Local card — **no** process control, inline editing, or raw key/URL. Slice 4 =
  the **command helper** (`GET /api/local-model/command-profile` +
  `localModelCommand.js` + a `CommandHelper` block): a copyable, static, whitelisted
  `llama-server` start command (placeholder model path, `--host 0.0.0.0`) the
  operator runs **manually** — the app never executes it. **Phase 1 is feature-complete
  and validated** (Slice 5, DONE #49). **Next major choice = Ask Your Guide local-only
  chat (recommended)** or the sign-off-gated host-companion DESIGN (Phase 2). Remains a
  **separate** feature from the in-app provider settings; provider config writes stay on
  `PATCH /api/provider-settings/local`.
- **Library archive / tag model** — DESIGN-FIRST (bulk archive needs an archive state +
  `DECISIONS.md` entry; bulk tag needs a tag model; neither started).
- **GHCR publish workflow / prebuilt image** — deferred distribution decision (parked on `hardening`).
- **Pinned dependency lockfile** — deferred; regenerate from this tree, don't lift from `hardening`.
- **Provider-aware truncation caps** — deferred (Option B in `DECISIONS.md`).
- **Shortcut inspector / repair loop** — DONE through Slice 3B
  (`a0f96d1`→`4458c9a`, #39→#42): additive `validity` (3-tier status, full
  findings, saved-model check; legacy `valid`/`reason` preserved), `GET
  …/inspect`, 3-tier badges + read-only Inspector drawer, repair preview
  (read-only) / apply (the only write; in-place + clone) + repair UI
  (Preview-before-Apply, stale-preview re-disable, explicit confirm). Validated
  docs-only (`docs/VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md`). The
  **degraded-activation confirm / "Repair instead" Home path (§5.5) is now DONE**
  (branch `shortcut-inspector-degraded-activation`, #43 — see "What just landed").
  **Still deferred:** "Repair all" batch, a Home "N need attention" banner, model
  auto-suggest/fuzzy match, imported preview-row repair before import, tool/view
  repair (repair is scoped to `builder_setup`).
- **Branch retirement** — deferred housekeeping (do not delete branches).
- **Group D** — not started; do not begin without an explicit slice request.

## Verification commands
```fish
npm --prefix frontend run build          # builds frontend/dist (served by backend)
python -m compileall api pipeline        # compile-check backend + pipeline
docker compose config                    # validate compose (expands .env in plaintext — do not share output)
docker compose build
docker compose up
curl http://localhost:8000/api/health    # {"ok":true}
curl http://localhost:8000/api/options   # themes / styles / providers / models / generator_presets (redacted)
curl http://localhost:8000/api/provider-settings  # provider settings, redacted (no raw keys; only configured/key_source/key_hint/base_url_host)
python test_scripts/smoke_release.py     # end-to-end release smoke (~28 checks; outline-ordering check is known-flaky)
```
