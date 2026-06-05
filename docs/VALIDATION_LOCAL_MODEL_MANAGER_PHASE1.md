# VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md — Local Model Manager Phase 1

> **Scope:** validation + docs reconciliation only (LMM Slice 5). **No feature
> work, no refactors, no process spawning, no start/stop/restart, no host
> companion, no GGUF/model-file browsing, no Docker config change, no
> provider-settings write-behavior change, no generation/renderer/prompt change.**
> This is a verification pass over the already-landed LMM Phase 1 (Slices 1→4) to
> confirm reality matches the design + docs and to prove the hard safety
> guarantees (read-only, no execution, no secret leak).

- **Validated on:** 2026-06-05
- **Branch:** `docs-validate-local-model-manager-phase1` (cut from
  `chrome-renderer-v1` @ `e399f09`)
- **Trunk under test:** `chrome-renderer-v1` @ `e399f09` ("Add local-model
  command-helper (copy start command) (LMM Slice 4)")
- **Result:** **PASS.** Phase 1 is feature-complete and safe. No code changed.

---

## 1. What LMM Phase 1 is (as implemented on trunk)

Phase 1 is **detection-first**: the app *observes* a local OpenAI-compatible
server (llama.cpp `llama-server`) the operator runs themselves, and helps them
start it by hand. It never manages the process.

| Slice | Commit | What landed |
| --- | --- | --- |
| 1 — design | `94003bc` | `docs/LOCAL_MODEL_MANAGER_DESIGN.md`: detection-first; **direct Docker→host spawn (Option D) REJECTED**; host companion (Option B) deferred / design-only. |
| 2 — backend detection | `e27c674` | Read-only `GET /api/local-model/status` + thin `POST /api/local-model/check` alias → `get_local_model_status()`. Safe reachable/offline/configured DTO. **No process control.** |
| 3 — frontend panel | `7429f24` | Read-only **Local Models** panel in the Providers/Models page: reachable/offline/not-configured/error states, **Refresh status**, link/scroll to the Local provider card. **No start/stop.** |
| 4 — command helper | `e399f09` | Read-only `GET /api/local-model/command-profile` → static whitelisted `llama-server` profiles; copyable **manual** command, **placeholder model path only**. **No command execution.** |

---

## A. Static checks

All run on host from `main-app/`.

| Check | Result |
| --- | --- |
| `python -m compileall api pipeline` | **PASS** (exit 0) |
| `python test_scripts/test_local_model_status.py` | **PASS** — 17/17 |
| `python test_scripts/test_local_model_command_profile.py` | **PASS** — 13/13 |
| `python test_scripts/test_provider_fetch_models.py` | **PASS** — 16/16 |
| `python test_scripts/test_provider_settings_store.py` | **PASS** — 26/26 |
| `npm --prefix frontend run build` | **PASS** (built `frontend/dist`) |
| `npm --prefix frontend run test:local-model-status` | **PASS** (all checks) |
| `npm --prefix frontend run test:local-model-command` | **PASS** (all checks) |

> No combined local-model frontend test script exists in `frontend/package.json`
> (only the two per-slice scripts above) — both were run individually.

Notable assertions proven by those suites:
- status: no-key-leak (stored local key still resolvable server-side but absent
  from `/api/provider-settings` + `/api/options`), no-write (settings/secrets/
  custom_models untouched by probes), action `copy_start_command` is **disabled**.
- command: no-URL-leak (no userinfo/query token/user host:port), host-only
  `base_url_host`, no-write, **no-spawn** (source makes no
  `subprocess`/`os.system`/`Popen` call), Slice-2 status shape unchanged.

## B. Docker / smoke

| Check | Result |
| --- | --- |
| `docker compose config` | **PASS** (exit 0; output withheld — expands `.env` in plaintext) |
| `docker compose build` | **PASS** (image built) |
| `docker compose up -d` | **PASS** (container `main-app-app-1` **healthy**) |
| `curl /api/health` | **PASS** — `{"ok":true}` |
| `curl /api/local-model/status` | **PASS** — HTTP 200 (see §C) |
| `curl /api/local-model/command-profile` | **PASS** — HTTP 200 (see §C) |
| `curl /api/options` | **PASS** — HTTP 200, expected top-level keys, no key leak |
| `python test_scripts/smoke_release.py` | **PASS** — 28 passed, 0 failed, 0 skipped (incl. its own no-key-leak checks) |

## C. Live API validation (no local server running)

`/api/local-model/status` — the configured local base URL points at
`host.docker.internal` (a real local llama-server is **not** running):

- HTTP **200** ✓
- `ok: true` ✓
- `reachable: false` ✓
- `error.category: "local_offline"` ✓ (`message: "<urlopen error timed out>"`,
  redacted — no host/port/userinfo). When no base URL is configured the category
  is `provider_config` instead — both are safe, expected states.
- No crash ✓
- No raw key ✓ (no key field by construction)
- No full URL with userinfo ✓ — `base_url_host` is `host.docker.internal` only
- `notes` correctly surfaces the `--host 0.0.0.0` gotcha (host is the docker host)
- `actions`: `open_provider_settings` **enabled**, `copy_start_command`
  **disabled** with a reason ✓

`/api/local-model/command-profile`:

- HTTP **200** ✓
- Includes the static whitelisted profiles `llama_server_default` (GPU offload)
  and `llama_server_cpu` ✓
- Includes the placeholder `/path/to/model.gguf` (both `command` and `argv` and
  `placeholders.model_path`) ✓
- Includes `--host 0.0.0.0` ✓ and `--port 8080` ✓
- No real host paths ✓ (model path is the literal placeholder; only `base_url_host`
  is echoed, host-only)
- No secrets ✓
- Executes nothing ✓ (display template only)

**Optional reachable:true path:** not exercised — no local `llama-server` was
running in the validation environment. The reachable branch (model list /
`model_count`, Refresh) is covered by `test_local_model_status.py` and the
frontend `verify-local-model-status.mjs` harness.

## D. Live UI validation

The SPA is client-routed and no Puppeteer/Playwright driver is installed
(Chromium is present; the served shell renders cleanly via `--dump-dom`). The 11
UI requirements were verified against the authoritative component source
(`LocalModelsPanel.jsx`, `ProviderSettingsWorkspace.jsx`) plus the green frontend
harnesses and the in-Docker smoke. Each requirement maps to concrete code:

1. **Local Models panel appears** — `LocalModelsPanel` is mounted at the bottom of
   `ProviderSettingsWorkspace` (the Providers/Models page). ✓
2. **Offline state is safe & readable** — `Troubleshooting` block + amber error
   line + latency "—"; redacted server-side message. ✓
3. **Refresh status works** — button → `fetchStatus(true)` → `POST
   /api/local-model/check` (same read-only probe). ✓
4. **Edit local provider settings scrolls/highlights the local card** —
   `onEditLocalProvider` → `focusLocalProvider` → `getElementById("provider-card-local")`
   → `scrollIntoView` + `sg-card-flash` (CSS present in `styles.css`). ✓
5. **Command helper appears** — `CommandHelper` rendered when `canCopy`. ✓
6. **Copy command works or fallback appears** — `navigator.clipboard.writeText`
   with a `COPY_FAILED` manual "select & copy (Ctrl/Cmd+C)" fallback. ✓
7. **Command is clearly manual** — "Run this in a terminal on your host machine…
   The app never runs it for you" + static warnings. ✓
8. **No Start/Stop/Restart button exists** — the only controls are Refresh, the
   Edit-settings link, Copy command, and **disabled** "Planned" chips. ✓
9. **No file picker / GGUF browser exists** — none in source; model path is a
   placeholder string. ✓
10. **Existing provider settings still work** — `ProviderSettingsCard` save path
    untouched; `/api/provider-settings` 200 and smoke green. ✓

## E. No-process-execution proof

- `grep -n "subprocess|os.system|Popen|shell=True|os.popen|pty|spawn"` over
  `api/server.py` + `pipeline/provider_config.py`: the **only** matches in the
  LMM code are **comments asserting the absence** of execution. The single real
  `subprocess` reference (`api/server.py` `run_llm_job` offload comment) is the
  pre-existing, unrelated PDF/render pipeline — **not** added or touched here.
- No LMM endpoint starts, stops, restarts, or spawns anything. `get_local_model_status`
  only does a read-only HTTP `/models` probe (reusing `_discover_openai_models`);
  `get_local_model_command_profiles` only renders static strings/argv.
- The command helper returns **strings + argv only** (`shlex.quote` is
  display-quoting, not execution). `test_local_model_command_profile.py` proves
  no-spawn both by source inspection **and** a `subprocess.Popen` monkeypatch trip.

## F. Secret-leak scan

A scan loaded the **real** secret values from `.env` / `.env.save` (never printed)
and searched for them — plus a generic `sk-[A-Za-z0-9]{20,}` live-key pattern —
across the served surfaces:

| Surface | Real-secret hits | `sk-` pattern |
| --- | --- | --- |
| `/api/local-model/status` | 0 | 0 |
| `/api/local-model/command-profile` | 0 | 0 |
| `/api/options` | 0 | 0 |
| `/api/provider-settings` | 0 | 0 |
| served `frontend/dist/assets/*.js` | (see note) | 0 |
| container logs | 0 | 0 |
| changed docs | 0 | 0 |

**Note (false positive, investigated):** the served JS matched exactly one env
value — `LOCAL_LLM_API_KEY`, whose value is a **4-character placeholder** (llama.cpp
requires no real key; the value is `none`). It coincidentally appears inside
minified React's `display:"none"` CSS string. The real DeepSeek/Qwen `sk-` keys
appear **nowhere**. **No real secret leak.** No real secret was printed during the
scan.

---

## Findings / follow-up

- **No bugs found.** Phase 1 behaves exactly as the design + per-slice docs
  describe. No code was changed by this slice.
- **No new DECISIONS entry needed** — validation surfaced no non-obvious rule not
  already captured (the detection-first rejection of Docker→host spawn, the
  single-probe status implementation, the panel-as-Providers-sub-panel choice, and
  the never-executing whitelisted command helper are all already recorded).
- **UX note (not a bug):** full pixel-level UI polish (card spacing, copy-button
  feedback timing, troubleshooting legibility) was **not** click-through tested in
  a real browser here — it is proven structurally (source + harness + smoke) but
  remains a candidate for a human pass if desired. This does not gate Phase 1.

## Conclusion

**Local Model Manager Phase 1 is COMPLETE and validated.** All static, Docker,
smoke, live-API, no-execution, and secret-scan checks pass. Detection + manual
command helper are safe and read-only. The remaining LMM work is **deferred and
design-gated**: host companion design (Slice 5), companion implementation, model
directory browsing, start/stop/restart, log tailing, and Ask Your Guide
integration — none started.

**Recommended next slice:** *Ask Your Guide* local-only chat (consumes LMM status;
no process control) — or the **host companion DESIGN** only if the user wants
app-managed start/stop later (sign-off-gated). **Merge recommendation:** safe to
merge `docs-validate-local-model-manager-phase1` into `chrome-renderer-v1`
(docs-only; no code change).
