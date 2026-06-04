# VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md — Focused validation pass

> Validation + docs-reconciliation slice run after the Shortcut Inspector / Repair
> Loop landed on `chrome-renderer-v1` (Slices 1, 2, 3A, 3B). **Validation only — no
> feature work, no refactor.** No application code was changed; this report and the
> reconciled docs are the only additions.

- **Branch:** `docs-validate-shortcut-inspector` (off `chrome-renderer-v1` @ `4458c9a`)
- **Date:** 2026-06-04
- **Files changed (code):** **none.** No backend, frontend, prompt, renderer, or
  config code touched.
- **Files changed (docs):** `CURRENT_TASK.md`, `NEXT_CHAT_HANDOFF.md`,
  `PROJECT_CONTEXT.md`, `SHORTCUT_INSPECTOR_REPAIR_DESIGN.md`,
  `VALIDATION_PROVIDER_SETTINGS_LARGE_PDF.md` (one stale "next" reference), and this
  new report. `DECISIONS.md` left unchanged (all relevant decisions already
  captured; validation revealed no new non-obvious rule).
- **Overall:** Shortcut Inspector (read-only `validity` + `/inspect`) and the repair
  loop (preview read-only / apply-only-write, in-place + clone) **PASS** at the
  static, Docker/smoke, and live-API levels. Served-bundle UI markers present.
  Secret-leak scan **CLEAN**. **No code bugs found.** One pre-existing cosmetic
  runtime artifact noted (a stray `S (repaired copy)` shortcut from an earlier
  session) — not a code issue.

---

## A. Static checks — PASS

| Check | Result |
| --- | --- |
| `python -m compileall api pipeline` | OK (exit 0) |
| `python test_scripts/test_shortcut_store.py` | **39/39** |
| `python test_scripts/test_shortcut_inspector.py` | **19/19** (incl. read-only sha256 + no-key-leak) |
| `python test_scripts/test_shortcut_repair.py` | **29/29** (incl. preview read-only + no-key-leak) |
| `npm --prefix frontend run build` | OK (~1.1s; SVG assets emitted; `index-*.js` 462 KB) |
| `npm --prefix frontend run test:shortcuts` | `verify-shortcut-status` **25/25** + `verify-shortcut-repair` **32/32** |

---

## B. Docker / smoke — PASS

| Check | Result |
| --- | --- |
| `docker compose config >/tmp/compose-check.txt` | exit 0 (output **not** pasted — expands `.env`) |
| `docker compose build` | OK (image built) |
| `docker compose up -d` | OK; container **healthy** on first health poll |
| `curl /api/health` | `{"ok":true}` |
| `curl /api/options` | HTTP 200; top keys `[generator_presets, input_modes, models, provider_details, providers, providers_v2, styles, themes]` |
| `python test_scripts/smoke_release.py` | **28 passed, 0 failed, 0 skipped** (no flake this run) |

Container baseline: 3 providers configured (deepseek/qwen/local); deepseek default
`deepseek-v4-pro`, qwen default `qwen3.7-plus`, local `gemma-4-…gguf`.

---

## C. Live Shortcut Inspector validation — PASS (16/16)

Exercised against the running container with **temporary** `ZZ_TEMP …` shortcuts
created via `POST /api/shortcuts`, then deleted (see §F). Read-only proof uses
`sha256(library/shortcuts.json)` before/after a preview.

### C1. Valid shortcut — PASS
- `builder_setup` (deepseek / `deepseek-v4-pro`, no style) →
  `validity.status: valid`, `valid: true`, **0 findings**. Inspector would show
  "No problems found"; no repair action applies.

### C2. Degraded shortcut — PASS
- Injected `builder_setup` with an **unavailable model** (`ghost-model-removed`)
  **and** a **missing style** (`deleted_style_xyz`).
- `validity.status: degraded`; findings = **both** `model_unavailable` **and**
  `style_missing` (full list, not first-failure → gap #2 fixed; the model check is
  present → gap #3 fixed).
- Legacy `valid: false` here because `style_missing` is a **pre-existing** legacy-
  `valid` breaker, while the new `model_unavailable` is degraded-severity — exactly
  the documented behaviour (a *model-only* degraded shortcut would keep
  `valid:true` + `status:degraded`). **Not a bug.**
- **Repair preview is read-only:** `sha256(shortcuts.json)` **identical**
  before/after preview (`e29936f620e0` == `e29936f620e0`). Preview returned the
  diff `model: ghost-model-removed → deepseek-chat`, `style: deleted_style_xyz →
  null` and `resulting validity: valid`.
- **Apply in-place** kept the **same id**, and re-inspect returned
  `status: valid` with **0 findings** (validity improved).

### C3. Broken shortcut — PASS
- Injected `builder_setup` with an **unknown/unconfigured provider**
  (`nonexistent_provider`) → `validity.status: broken`, finding `provider_missing`,
  legacy `valid: false` (so the existing activation guard keeps routing it to
  Models — activation behaviour unchanged).
- **Apply clone** (provider→qwen, model→qwen3.7-plus) **minted a new id**, the
  **original stayed `broken`** (untouched), and the **clone inspected `valid`**.

### C4. Error states — PASS
- Unknown shortcut inspect (`GET /api/shortcuts/sc_doesnotexist/inspect`) → **404**.
- Invalid repair (replacement provider `ghost_provider`) → **400**
  ("Unknown provider for repair: 'ghost_provider'.").
- Unknown `changes` key (`evil_key`) → **400**
  ("Unknown repair change fields: ['evil_key'].") — the mutation-boundary
  whitelist rejects, does not silently drop.

### C5. Stale-preview / Apply gating
- The "editing the draft after preview marks it stale and re-disables Apply"
  behaviour is **frontend-only** (the backend preview/apply are stateless) and is
  covered by `verify-shortcut-repair.mjs` (`changing a value/mode/clone-name
  changes the signature (stale)`, all green) and present in the served bundle
  ("preview again", "unchanged until", "original is unchanged"). Live pixel
  click-through remains a manual operator step (see §G).

---

## D. Served-bundle UI markers — PASS (proxy for the live UI)

The served `index-*.js` contains the expected Inspector/repair surfaces:
`Needs attention`, `Broken`, `No problems found`, `Read-only`, `Repair`,
`Preview`, `Apply`, `clone`, `repaired copy`, `create a repaired copy`,
`preview again`, `unchanged until`, `original is unchanged`, and the endpoints
`/inspect`, `repair/preview`, `repair/apply`. (Pixel-level layout/hover is not
asserted here — see §G.)

---

## E. Secret leak scan — CLEAN

Scanned against the **real** key values (harvested from `.env` + the container's
`config/secrets.json`; **never printed** — 2 candidate values). Also flagged any
`api_key`/`apiKey`/`secret_key` JSON field name.

| Target | Result |
| --- | --- |
| served frontend JS (`index-*.js`) | clean |
| `/api/options` | clean |
| `/api/provider-settings` | clean |
| `/api/shortcuts` (list/read) | clean |
| `…/inspect` responses (4 temp shortcuts) | clean |
| `…/repair/preview` response | clean |
| container logs (`docker compose logs`) | clean |
| all `docs/*.md` (incl. changed docs) | clean |

No raw key substring and no raw-key JSON field in any target. No real secret value
appears in this report.

---

## F. Cleanup — DONE
All four `ZZ_TEMP …` temporary shortcuts created during §C were deleted
(`DELETE /api/shortcuts/{id}` → 200 each); the shortcut list returned to its prior
contents.

---

## G. Findings / follow-up

- **No code bugs found.** The inspect→repair contract behaves exactly as the design
  and `DECISIONS.md` describe.
- **Pre-existing cosmetic artifact (not a bug):** a stray `S (repaired copy)`
  `builder_setup` shortcut remains in the runtime `library/shortcuts.json` (it is
  `valid`), left over from an earlier session's repair test. It is gitignored
  runtime data and was **not** created by this validation, so it was left in place;
  the operator may delete it from Customize Shortcuts if desired.
- **Not automated — needs a human click-through (polish, not a blocker):** the live
  Home/Customize 3-tier badge rendering, the Inspector drawer layout/spacing, and
  the Preview→Apply / clone flow including the stale-preview re-disable. DOM markers
  + wiring are proven; pixel layout/hover is not.

---

## H. Result summary

- **Code changed:** none (docs-only slice).
- **Docs reconciled:** `CURRENT_TASK.md`, `NEXT_CHAT_HANDOFF.md`,
  `PROJECT_CONTEXT.md`, `SHORTCUT_INSPECTOR_REPAIR_DESIGN.md`,
  `VALIDATION_PROVIDER_SETTINGS_LARGE_PDF.md`, + this report.
- **All validation gates pass:** static (compile + 6 test suites), Docker/smoke
  (config/build/up/health/options/smoke 28/28), live API (16/16), secret scan CLEAN.
- **Recommended next slice:** focused manual UI click-through / polish of the
  Inspector, then (optional) the degraded-activation confirm + "Repair instead"
  path (design §5.5). See `NEXT_CHAT_HANDOFF.md`.
- **Merge/push:** this docs-only branch is safe to merge into `chrome-renderer-v1`
  and push. No old/consumed branches were merged, rebased, or cherry-picked; no
  force-push; no `docker compose config` output pasted; no real secret printed.
