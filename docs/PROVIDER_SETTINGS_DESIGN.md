# PROVIDER_SETTINGS_DESIGN.md — In-app provider settings

> **Status: DESIGN ONLY. No code in this slice.** This document proposes a safe,
> server-side provider-settings system so a user can configure providers, models,
> and sampling/runtime defaults **from inside the app** instead of hand-editing
> `.env`, while API keys and other secrets stay strictly server-side and never
> reach the frontend. Nothing here is implementation-ready until the design is
> reviewed and a first slice is signed off (see §13).
>
> **Scope guard.** This design touches only the provider-configuration layer
> (`pipeline/provider_config.py`, `pipeline/llm_client.py`, the `/api/options` and
> provider/model-validation surface in `api/server.py`, and a new settings store +
> endpoints). It does **not** touch the generation pipeline, prompts, renderer,
> sanitizer, Library/exports, shortcuts, large-PDF, cancel, the job manager, or the
> **Local Model Manager** (a separate design-first feature). The numbered design
> below answers the 15 design questions from the task brief.

---

## 1. Current behavior summary

Provider configuration today is **100% environment-variable driven** and read
fresh from `os.getenv(...)` on every call. There is no persisted runtime config
and no in-app way to change any of it.

**Where it lives.**
- `pipeline/provider_config.py` is the single source of truth. It defines three
  providers — `deepseek`, `qwen`, `local` — each with a hard-coded default
  base URL and a static known-model list (`DEEPSEEK_MODELS`, `QWEN_MODELS`; the
  local list is discovered at runtime). `PROVIDER_ALIASES` maps display names and
  variants onto the three canonical ids.
- `pipeline/llm_client.py` holds `LLMConfig` (the immutable per-call config:
  `base_url`, `api_key`, `model`, `temperature`, `top_p`, `max_tokens`,
  `provider`, `extra_body`) and `generate_chat_completion(messages, config)`,
  which constructs an `openai.OpenAI` client and calls `chat.completions.create`.
- `load_env_file()` calls `python-dotenv`'s `load_dotenv()` (a no-op if the
  package is absent). In Docker, `.env` is also injected via compose `env_file`,
  so process env wins; `load_dotenv()` does **not** override already-set vars.

**How values are resolved (the env fallback chains).** Each provider reads an
ordered chain, e.g. DeepSeek key = `DEEPSEEK_API_KEY` → `LLM_API_KEY`; DeepSeek
model = `DEEPSEEK_MODEL` → `LLM_MODEL` → `DEEPSEEK_MODEL_FLASH` → `DEEPSEEK_MODELS[0]`;
base URL = `DEEPSEEK_BASE_URL` → `LLM_BASE_URL` → built-in constant. Qwen reads
`DASHSCOPE_API_KEY`/`QWEN_API_KEY`, `QWEN_MODEL`/`LLM_MODEL`, `DASHSCOPE_BASE_URL`/
`QWEN_BASE_URL`. Local reads `LOCAL_LLM_BASE_URL`/`LLM_BASE_URL`,
`LOCAL_LLM_MODEL`/`LLM_MODEL`, `LOCAL_LLM_API_KEY`/`LLM_API_KEY` (default `"local"`).

**Sampling / runtime params today.**
- `temperature`: global, from `LLM_TEMPERATURE` env (default `0.2`), unless a
  generator preset overrides it (`temperature_override`).
- `top_p` / `max_tokens`: **unset by default** — only sent when a preset (or
  future caller) supplies them, so existing calls stay byte-identical.
- Qwen "thinking": `extra_body={"enable_thinking": qwen_thinking_enabled}` (defaults
  to `True` in the current call sites).
- **timeout / retry count: not configurable today.** The OpenAI client uses its
  library defaults; there is no app-level timeout or retry knob.

**The public/safe boundary already exists.** `get_provider_registry()` returns a
list of **already-redacted** dicts via `_entry_to_public_dict()`:
`id`, `display_name`, `configured` (bool — derived from "is a key present"),
`available_models`, `default_model`, `base_url_configured` (bool), `base_url`
(**`None` for cloud providers**, set only for `local`), `discovery_error`,
`supports_thinking`, `kind`. **Raw API keys are never placed in this dict.**
`/api/options` exposes this as `provider_details` / `providers_v2`, plus a
flattened `providers` (display names) and `models` (name → list).

**Validation surface.** `validate_provider_model(provider, model)` checks the
provider resolves, is `configured`, and the model is in the known list;
`_validate_provider_model` in `api/server.py` raises HTTP 400 on failure.
`_pick_generate_provider` resolves the request's provider (or picks the first
configured one) and its default model. Per-request `provider`/`model` always
override the default at generation time.

**Net:** changing a key, base URL, default model, or temperature today requires
editing `.env` (or compose env) and restarting/reloading the process. There is no
UI, no persistence layer, and **no settings store**.

---

## 2. Security model and non-negotiables

These are hard invariants. Any implementation that violates one is wrong.

1. **Raw API keys never leave the server.** No endpoint, log line, error message,
   `job.json`, export bundle, `/api/options` payload, or frontend state may ever
   contain a raw secret value. The frontend receives only **derived, non-secret
   status**.
2. **The frontend may receive only safe status:** `configured: true/false`, an
   optional **masked hint** (e.g. last 4 chars only, never more), provider id +
   display name, `base_url_configured` (bool) and — only where non-secret — the
   **host** of a base URL, the available model list, the active/default model,
   `supports_thinking`/`kind`, and validation/test status. This is exactly the
   existing `_entry_to_public_dict` contract, extended minimally.
3. **Secrets are write-only over the API.** A key can be **set** or **cleared**,
   never **read back**. There is no "GET key" path, even masked beyond a last-4
   hint, and even for the operator.
4. **The redaction boundary is one function.** All provider state returned to any
   caller must pass through a single public-serialization function (today
   `_entry_to_public_dict`). Secrets must be structurally impossible to serialize
   because the public DTO simply has no key field — not merely "filtered out."
5. **Errors are redacted at the boundary.** Provider/test errors are mapped to
   safe, classified messages (reuse `pipeline/errors.classify_exception` + the
   existing `_safe_log_line`) before they reach the client or the logs. Never echo
   the Authorization header, the key, or a full upstream error body.
6. **The secret store is local-only and gitignored.** It must live under an
   already-gitignored runtime path, never be baked into the Docker image, and never
   be added to an export bundle or `job.json`.
7. **No new secret in transit to the browser, ever — including base URLs that
   embed credentials.** If a base URL ever contains userinfo (`https://user:pass@…`),
   only the scheme+host is exposed; userinfo is stripped before serialization.
8. **Fail safe, not open, for secrets; fail open for advisory status.** Missing or
   unreadable secret store ⇒ behave exactly as "no key configured" (provider shows
   `configured: false`), never crash or leak a partial value.

---

## 3. Proposed storage model

**Recommendation: split public config from the secret store (two files), both
under a new gitignored runtime dir; `.env` remains the bootstrap fallback.**

```text
config/                         # NEW runtime dir (gitignored, Docker volume)
├── provider_settings.json      # NON-SECRET: base URLs, default provider/model,
│                               # model lists, sampling + runtime defaults, flags
└── secrets.json                # SECRET: api keys ONLY, file perms 0600
```

**Why split, not one file:** it makes the security boundary physical, not just a
code convention. The non-secret file can be logged, diffed, inspected, and
hand-edited safely; the secret file is the **only** place a raw key lives on disk
and is the only thing that needs `0600` perms and extra care. A reviewer can verify
"no secret leaks" by checking that the serializer reads from `provider_settings.json`
+ `configured` flags and **never** reads `secrets.json` into any response DTO.

**Why JSON files, not SQLite:** the repo already standardizes on small JSON stores
with the same shape and discipline — `style_store`, `library_store`,
`shortcut_store`, `generator_presets`. A new `provider_settings_store.py` should
mirror that pattern (atomic write via temp-file + `os.replace`, whitelist parsing of
untrusted fields per the repo's whitelist convention, defensive load that degrades
to defaults). SQLite adds a dependency and a migration surface for a single-operator
tool with a handful of providers — not justified.

**`provider_settings.json` (non-secret) — proposed shape:**

```jsonc
{
  "version": 1,
  "default_provider": "deepseek",          // overrides "first configured" pick
  "providers": {
    "deepseek": {
      "base_url": "https://api.deepseek.com/v1",
      "default_model": "deepseek-v4-pro",
      "custom_models": ["my-finetune-id"],  // user-added ids, merged with registry
      "temperature": 0.2,                    // null ⇒ inherit global/env default
      "top_p": null,
      "max_tokens": null,
      "thinking_default": null,              // qwen-only; null ⇒ provider default
      "timeout_seconds": 60,
      "retry_count": 2,
      "key_present": true,                   // mirror of secrets.json; see note
      "key_hint": "…a1b2"                    // last-4 only, safe to persist here
    }
  }
}
```

> **`key_present`/`key_hint` placement note.** The non-secret file may cache only a
> boolean and a last-4 hint for fast reads, but the **authoritative** presence check
> is "is there a non-empty value in `secrets.json` (or env fallback)". The hint is
> derived once on write and is itself non-secret (4 chars is below any useful
> reconstruction threshold). If you prefer zero secret-derived data in the public
> file, drop `key_hint` and compute it on read from the secret store inside the
> server only. Either is acceptable under §2; the doc recommends computing on read
> to keep the public file purely user-authored.

**`secrets.json` (secret) — proposed shape:**

```jsonc
{ "version": 1, "keys": { "deepseek": "<raw>", "qwen": "<raw>", "local": "<raw>" } }
```

Written `0600`, never serialized to any response, never logged, excluded from
exports and `job.json`. See §4 for encryption options.

---

## 4. Proposed config precedence

Provider/model selection and the other configurable fields resolve on **separate**
ladders. The user's selected provider/model is **authoritative** and is never
changed by a generator preset (see §13).

### 4a. Provider / model precedence (authoritative — presets never appear here)

A single resolver computes the effective provider and model. **Highest wins:**

```text
1. Per-job request provider/model   (request.provider / request.model — unchanged)
2. Provider-settings default        (config/provider_settings.json: default_provider
                                      + per-provider default_model)
3. Environment / .env fallback      (existing os.getenv chains — UNCHANGED)
4. Built-in code defaults           (DEEPSEEK_BASE_URL host, DEEPSEEK_MODELS[0], …)
```

- **A generator preset is NOT a tier on this ladder.** A preset never hard-pins,
  auto-switches, overrides, or blocks the provider/model. Its `provider` /
  `model_hint` are **advisory only** and feed at most a soft, non-blocking
  compatibility warning (§13). The user's selection is always what is sent.
- **Per-job request still wins for provider/model** — preserves today's behavior
  exactly (the Builder selection is authoritative).
- **The settings store sits *above* env**, so saving a default in-app overrides
  `.env` without editing it. **Env remains the fallback** (Q2 = yes): if the store
  has no default, the existing env chain is consulted unchanged.

### 4b. Base URL, sampling, and runtime-field precedence

For the remaining per-provider fields (base URL, temperature, top_p, max_tokens,
thinking default, timeout, retry count) the resolver is **highest wins:**

```text
1. Generator-preset sampling override  (preset temperature/top_p/max_tokens/thinking
                                         — applies to SAMPLING fields only, not to
                                         provider/model; see §13)
2. Provider-settings value             (config/provider_settings.json)
3. Environment / .env fallback         (existing os.getenv chains — UNCHANGED)
4. Built-in code defaults              (DEEPSEEK_BASE_URL, temp 0.2, …)
```

- A selected preset's pinned `temperature`/`top_p`/`max_tokens`/`thinking` apply on
  top of the per-provider defaults — presets are a curated, tuned unit (see
  `DECISIONS.md` "Generator presets are separate from styles"); a user's global
  temperature default must not silently override a preset that deliberately pins its
  own. **This is the only thing a preset overrides, and it is never provider/model.**
- `base_url`/`timeout`/`retry` have no preset tier; they resolve store → env →
  default.

### 4c. Shared rule

- **If no settings file exists at all, resolution is byte-identical to today** —
  every lookup (4a and 4b) falls straight through to the env chain / built-in
  defaults. This is the migration guarantee (§10/§15).

Implementation shape: `build_provider_config(...)` keeps its signature but gains an
internal "settings-first, env-fallback" lookup helper, e.g.
`_resolved(provider_id, "base_url")` that checks the store then falls back to the
current `os.getenv(...) or CONSTANT` chain. The existing
`temperature_override`/`top_p`/`max_tokens` params (preset path) stay above the store
for **sampling only** — they do not touch the provider/model the user selected.

---

## 5. How secrets are stored locally

**Recommendation: plain local JSON file (`config/secrets.json`) with `0600`
permissions + gitignore, with an OPTIONAL passphrase-based encryption flag deferred
to a later slice. OS keyring deferred (not cross-platform enough for this tool).**

Rationale and trade-offs:
- **Plain file + perms + gitignore (chosen baseline).** This is the **same trust
  level the project already accepts**: `.env` holds real keys in plaintext today and
  is gitignored. A `0600` JSON file under a gitignored, non-exported runtime dir is
  no worse than the status quo and is the smallest, most reviewable step. It is also
  consistent with the repo's existing JSON-store discipline.
- **Encrypted-at-rest (deferred, additive).** A later optional slice could encrypt
  `secrets.json` with a key derived from an operator passphrase or a host secret
  (e.g. `cryptography`/Fernet). This adds a dependency and a passphrase-entry UX and
  is **not** needed to match today's security posture, so it is explicitly deferred
  to keep the first slice tiny and dependency-free.
- **OS keyring (deferred).** `keyring` would be the most secure, but it is not
  reliably cross-platform (Linux needs a Secret Service/D-Bus session; headless
  Docker has none), and the app is Dockerized/local. Defer until/unless a
  desktop-native packaging story justifies it.

**Hard rules for the secret file:** created with `0600` (umask-safe: open with
`O_CREAT|O_WRONLY`, mode `0o600`), atomic temp-file write + `os.replace`, never
included in `docker build` context (already covered by `.dockerignore` excluding the
gitignored runtime dirs — to be confirmed for the new `config/` path, see §9), never
serialized, never logged.

---

## 6. Proposed backend API contract

All routes are registered with the other explicit `/api/*` routes, **before** the
static SPA mount, so they win over the catch-all (per CLAUDE.md). All responses go
through the single public serializer; **no route ever returns a raw key.**

### `GET /api/provider-settings`
Returns the safe, redacted view of every provider's effective settings + status.
**Returns (per provider):**
```jsonc
{
  "default_provider": "deepseek",
  "providers": [{
    "id": "deepseek",
    "display_name": "DeepSeek",
    "kind": "cloud",
    "configured": true,                 // key present (store OR env)
    "key_hint": "…a1b2",                // last-4 only, or null
    "key_source": "store",              // "store" | "env" | "none" (non-secret)
    "base_url_host": "api.deepseek.com",// host only, never full secret URL/userinfo
    "base_url_configured": true,
    "available_models": ["…"],          // registry ∪ custom_models
    "custom_models": ["my-finetune-id"],
    "default_model": "deepseek-v4-pro",
    "temperature": 0.2,                 // effective (store→env→default)
    "top_p": null, "max_tokens": null,
    "thinking_default": null,           // qwen only; null otherwise
    "supports_thinking": false,
    "timeout_seconds": 60,
    "retry_count": 2,
    "discovery_error": null,
    "last_test": { "ok": true, "at": "2026-06-03T12:00:00Z", "latency_ms": 412 } // or null
  }]
}
```

### `PATCH /api/provider-settings/{provider}`
Updates one provider's settings. **Body is a partial update**; only present fields
change. The `api_key` field is **write-only**:
- `"api_key": "<value>"` → store the new key (in `secrets.json`).
- `"api_key": ""` or field **absent** → **leave the existing key unchanged**
  (blank ≠ clear; see §8).
- `base_url`, `default_model`, `custom_models`, `temperature`, `top_p`,
  `max_tokens`, `thinking_default`, `timeout_seconds`, `retry_count` → validated and
  written to `provider_settings.json`.
- `default_provider` is set via the same route on a provider, or a dedicated
  `PATCH /api/provider-settings` body field `{"default_provider": "..."}`.
**Validation:** unknown provider → 400; out-of-range numbers (e.g. temperature not
in `[0,2]`, retry < 0, timeout ≤ 0) → 400; malformed base URL → 400; unknown fields
**dropped** (whitelist parsing, repo convention). **Returns** the same redacted
provider DTO as the GET (never the key).

### `POST /api/provider-settings/{provider}/test`
Runs a minimal connectivity/auth probe (see §7). **Returns**
`{ "ok": true|false, "category": "...", "message": "<safe>", "latency_ms": 412,
"model": "<model tested>" }`. Creates **no job, no artifacts**, writes only a
`last_test` summary into `provider_settings.json` (non-secret). Errors are redacted
(§8/§12).

### `POST /api/provider-settings/{provider}/clear-key`
Explicit secret removal. Deletes the provider's key from `secrets.json`. **Returns**
the redacted DTO with `configured` recomputed (may still be `true` if an env
fallback key exists — the response makes the `key_source` explicit so the UI can say
"now using .env key" vs "no key"). This is the **only** way to remove a key; an empty
`api_key` in PATCH never clears.

### `POST /api/provider-settings/{provider}/fetch-models` (optional, local-friendly)
For OpenAI-compatible providers (esp. `local`), re-runs the existing
`_discover_openai_models(base_url, api_key)` and returns the discovered list +
`discovery_error`. Reuses today's discovery code; adds no new network surface beyond
what `/api/options` already does for `local`. **Returns** `{ "models": [...],
"discovery_error": null }`. No key in the response.

> **Backwards compatibility:** `/api/options` is **unchanged in shape** and remains
> the public options endpoint the Builder consumes (§10). The new
> `/api/provider-settings*` routes are additive.

---

## 7. Provider test-button behavior

The test button answers one question: "with the currently-effective settings, can
this provider authenticate and return a token?" — cheaply and without side effects.

- **Tiny prompt, tiny output.** Send a 1-message chat completion such as
  `[{"role":"user","content":"ping"}]` with `max_tokens: 1` (and `temperature: 0`)
  to the resolved `base_url`/`model`/key. Success = a non-error HTTP response with a
  choice; the content is irrelevant.
- **Short timeout + bounded retries.** Use the provider's `timeout_seconds`
  (default a *short* test timeout, e.g. 10s, independent of the generation timeout)
  and **no** retries for the test (a test should fail fast, not hammer the upstream).
- **No job, no artifacts, no manifest.** The test path must not touch the job
  manager, create a `jobs/<id>/` dir, write artifacts, or appear in Recent Jobs. It
  is a pure request/response against the provider.
- **Reuse the existing client + error classifier.** Call through
  `generate_chat_completion` (or a thin `test_provider` helper using the same
  `openai.OpenAI` construction) and classify failures with
  `pipeline/errors.classify_exception(exc, base_url=...)`, which already produces
  user-facing categories (auth, network, timeout, etc.).
- **No key leak in errors.** The Authorization header, the raw key, and any
  upstream body that might echo the key are **never** surfaced. Only the classified
  `category` + a safe message (§12). The `latency_ms` and tested `model` are safe to
  return.
- **Local provider nuance.** For `local`, the test doubles as a reachability check;
  the existing `host.docker.internal` guard message (only reachable from Docker)
  should be reused verbatim rather than reinvented.

---

## 8. How API keys are updated (write-only semantics)

To make accidental key-wipes impossible and round-tripping safe:

| Action                         | `api_key` in PATCH body | Effect                              |
| ------------------------------ | ----------------------- | ----------------------------------- |
| Set / replace key              | non-empty string        | Store the new key                   |
| Save other fields, keep key    | absent **or** `""`      | **Key unchanged** (blank = no-op)   |
| Remove key                     | (use clear-key route)   | Delete key from `secrets.json`      |

- **Write-only field.** The key field is input-only; no GET ever returns it. The UI
  renders a password input pre-filled with a **placeholder** (`••••a1b2` from
  `key_hint`), never the real value.
- **Blank means "unchanged," never "clear."** A user editing base URL + temperature
  and pressing Save must not accidentally wipe the key by submitting an empty field.
- **Clearing is explicit.** Only `POST .../clear-key` removes a key, behind a
  deliberate UI action ("Remove key") with a confirm.
- **Atomic + perms preserved.** Writes to `secrets.json` go through the atomic
  temp-file + `os.replace` path and re-assert `0600`.

---

## 9. How model lists are handled

Three tiers, merged for display, with the registry as the floor:

1. **Static known models from the registry** (`DEEPSEEK_MODELS`, `QWEN_MODELS`) —
   always present so the dropdown is never empty even before a key is set.
2. **User-added custom model ids** (`custom_models` in the settings store) — merged
   with the registry list (dedup, registry-first then custom), so a user can target
   a new/renamed model without a code change. Consistent with the existing
   `_models_with_default` "ensure default is present" behavior and the
   "Custom model ID" path already in `_selected_model`.
3. **Local OpenAI-compatible discovery** — for `local` (and optionally any provider
   via `fetch-models`), reuse `_discover_openai_models()` to populate the list from
   the upstream `/models` endpoint, with `discovery_error` surfaced safely.

The effective `available_models` returned to the Builder is
`registry ∪ custom_models (∪ discovered for local)`, exactly as
`_entry_to_public_dict` already assembles it — extended only to fold in
`custom_models`. **Model lists are never secret** and can be freely returned.

---

## 10. How the Builder consumes provider settings

- **`/api/options` stays the public options endpoint** and keeps its current shape
  (`providers`, `models`, `provider_details`, `providers_v2`). The Builder
  (`BuilderWorkspace.jsx`) continues to read `provider_details`/`providers_v2`
  unchanged — `configured`, `available_models`, `default_model`,
  `base_url_configured`, `discovery_error`, `supports_thinking`, `kind`.
- **`/api/options` derives its values from the settings store first, env second.**
  Internally `get_provider_registry()` switches from "read env" to "read resolved
  settings (store→env→default)", so once a user saves a key in-app, `configured`
  flips to `true` and the new default model / custom models appear — **without any
  Builder change**. The redaction guarantees are unchanged because the same
  `_entry_to_public_dict` boundary is used.
- **A new Settings/Providers workspace** (frontend, a *later* slice) is the place to
  edit keys/URLs/defaults/sampling via the `/api/provider-settings*` routes. The
  Builder is a *consumer* of the resulting safe options, not an editor of secrets.
  This keeps the Claude-style UI baseline and avoids putting secret-entry fields in
  the generation flow.

---

## 11. Frontend UI flow (later slice — design only)

A dedicated **Providers** settings page (sibling to Styles/Library workspaces):
- One card per provider showing: status pill (`configured`/`not configured`,
  `key_source`), `base_url_host`, default model dropdown (registry ∪ custom),
  sampling fields (temperature/top_p/max_tokens), thinking toggle (qwen only),
  timeout/retry, and a **Test** button with a live result chip.
- **API key field is a password input** showing only the `key_hint` placeholder;
  typing a new value sets it on Save; leaving it blank keeps the current key; a
  separate **Remove key** button calls clear-key with a confirm.
- **Add custom model** input appends to `custom_models`.
- **Default provider** is a single-select across configured providers.
- Saving issues `PATCH /api/provider-settings/{provider}`; the page never receives
  or displays a raw key. All status comes from `GET /api/provider-settings`.

This UI is **explicitly out of the recommended first slice** (§13); the first slice
is backend-only and keeps `/api/options` backward-compatible.

---

## 12. Redaction / error-handling rules

- **Single serializer.** Extend `_entry_to_public_dict` (or add a parallel
  `_settings_to_public_dict`) as the **only** path producing provider DTOs. It has
  no key field by construction. Add a unit/smoke assertion that no response under
  `/api/provider-settings*` or `/api/options` contains any substring of a stored key.
- **Base URL exposure.** Return **host only** (`urllib.parse.urlparse(...).hostname`),
  never query/userinfo. Strip any `user:pass@` before serialization.
- **Error classification.** All provider/test failures pass through
  `pipeline/errors.classify_exception(exc, base_url=...)` → `{category, message}`;
  only those reach the client. Log lines go through the existing `_safe_log_line`.
- **Never echo upstream bodies or headers.** Auth headers and raw upstream JSON
  (which can echo keys) are dropped; only the classified category/message survive.
- **`last_test` is summary-only.** Persist `{ok, at, latency_ms}` (+ safe category),
  never the request/response bodies.
- **Logging.** No code path may log `secrets.json` contents, the Authorization
  header, or `config.api_key`. (Add a grep-style check in the test for the test.)

---

## 13. How this interacts with generator presets & `model_hint` warnings

**The user's selected provider/model is authoritative. A generator preset never
hard-pins, auto-switches, overrides, or blocks it.** A selected preset may do exactly
three things — and nothing else touches provider/model:

1. **Apply its system-prompt block.** The preset injects its tuned system prompt
   (then appends `MARKDOWN_MATH_SYSTEM`), per the existing `DECISIONS.md` "Generator
   presets are separate from styles" behavior. Unaffected by provider settings.
2. **Apply its sampling overrides.** The preset's pinned
   `temperature`/`top_p`/`max_tokens`/`thinking` override the per-provider **sampling**
   defaults from the settings store (precedence §4b, tier 1 > tier 2). The settings
   store only supplies the sampling **default** when no preset pins a value. This
   override is **sampling-only** — it does **not** change `base_url`, and it does
   **not** change the selected provider/model.
3. **Emit/display a soft compatibility warning.** The preset's `provider` /
   `model_hint` may surface a **non-blocking advisory** when the user's selected model
   looks different from the preset's tuned target. Per `DECISIONS.md` "Soft
   `model_hint`, not a hard pin", this warning **never** disables Generate, **never**
   auto-switches the model, and **never** alters the generate payload — the request
   always carries the user's selected `provider`/`model` verbatim.

Consequences for this design:
- **A preset is not a tier on the provider/model ladder (§4a).** It is absent from
  provider/model resolution entirely; only request → settings default → env →
  built-in default decide provider/model.
- **`model_hint` stays a soft advisory.** The provider-settings work changes none of
  the soft-warning logic; the user's selected provider/model (now possibly a
  `custom_models` entry) is still authoritative, and the existing conservative
  "prefer no warning" matcher (`presetMeta.js`) is untouched.
- **No new hard pins anywhere.** Provider settings introduce a *default* provider/model,
  not a lock; per-job selection overrides it exactly as today, and presets add no
  enforcement.

---

## 14. Docker / local deployment notes

- **New volume for `config/`.** Add `./config:/app/config` to `docker-compose.yml`
  volumes (alongside the existing `jobs`/`user_prompts`/`library` mounts) so saved
  settings + secrets persist across container restarts. This is a **deployment**
  change to plan in the implementation slice, not done here.
- **Never bake into the image.** Add `config/` to `.gitignore` **and** ensure the
  `.dockerignore` excludes it (the image must build without host secrets; the
  directory is created at runtime and bind-mounted, mirroring how `jobs/` etc. are
  handled). Confirm `.dockerignore` before shipping the store.
- **`.env` still works in Docker.** Compose `env_file: .env` continues to inject the
  env fallback; the store sits above it. Nothing forces a user to migrate.
- **Permissions in-container.** The app runs as a non-root user (per the Docker
  hardening); `config/secrets.json` written `0600` by that user is correct. The
  bind-mounted host dir should be owned/permissioned so the container user can write.
- **Do not paste `docker compose config`.** It expands `.env` in plaintext (CLAUDE.md
  §5) — unchanged caution; the new config dir does not appear in that output anyway.

---

## 15. Migration / backward compatibility

- **No settings file ⇒ exactly today's behavior.** If `config/provider_settings.json`
  and `config/secrets.json` are absent, every resolver lookup falls straight through
  to the existing env chain / built-in defaults. `build_provider_config`,
  `get_provider_registry`, and `/api/options` produce **byte-identical** results to
  the current code. This is the migration guarantee and the acceptance test for the
  first slice.
- **No `.env` rewrite, ever.** The system never edits, reads-for-display, or migrates
  `.env`. Following the repo's "translate-on-read beats in-place migration" precedent
  (shortcut store), env values are consulted live as a fallback and never copied into
  the store automatically. (An optional, **explicit** "Import current .env keys into
  the store" button could exist later, but is opt-in, not automatic.)
- **First write creates the dir.** The store lazily creates `config/` (mode-safe) on
  the first PATCH/clear-key, like the other JSON stores create their dirs on demand.
- **Field-by-field fallback.** A partially-populated store (e.g. only a key set, no
  base URL) falls back to env/default for the unset fields — no all-or-nothing.

---

## 16. Risk analysis

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Raw key leaks via a response DTO | low | **critical** | Single serializer with no key field; automated "no key substring in any response" test; key is write-only |
| Key leaks via logs / error bodies | medium | **critical** | `classify_exception` + `_safe_log_line` at the boundary; never log `api_key`/auth header/upstream body |
| Secret file committed or baked into image | low | **critical** | `config/` in `.gitignore` **and** `.dockerignore`; bind-mount at runtime; confirm before ship |
| Accidental key wipe on Save | medium | high | Blank `api_key` = unchanged; clearing requires explicit clear-key route + confirm |
| Settings store corrupt/unreadable | low | medium | Defensive load degrades to env/default (fail-safe), never crash; atomic writes |
| Preset incorrectly overriding provider/model | low | medium | Presets are absent from the provider/model ladder (§4a); they override **sampling only** (§4b tier 1 > tier 2) and emit only a non-blocking warning; byte-identical default-path test |
| Base URL with embedded userinfo leaks | low | high | Expose host only; strip userinfo before serialize |
| Test button used as a job/spam vector | low | low | No job/artifacts; max_tokens:1; short timeout; no retries |
| Docker volume perms (container user can't write) | medium | low | Document mount ownership; `0600` written by the app user |
| `/api/options` shape drift breaks Builder | low | medium | Keep `/api/options` shape frozen; settings only change *values*, not keys/structure |

---

## 17. Explicit non-goals

- **No code in this slice.** Design only.
- **No Local Model Manager work** — separate design-first feature; this design only
  reuses the existing `local` provider + `_discover_openai_models`.
- **No changes to generation pipeline, prompts, renderer, sanitizer, math
  validation, Library/exports, shortcuts, large-PDF, cancel, or the job manager.**
- **No `.env` migration or rewrite**, and **no** automatic import of env keys.
- **No new dependency / lockfile change** in the first slice (encryption + keyring
  are deferred precisely to keep it dependency-free).
- **No encrypted-at-rest secret store** in the first slice (deferred, additive).
- **No OS keyring** (cross-platform/Docker constraints; deferred).
- **No multi-user / per-user secrets** — single-operator tool; one secret store.
- **No frontend Settings UI** in the first slice (backend-only; `/api/options`
  stays backward-compatible).

---

## 18. Recommended first implementation slice

**Backend-only: server-side provider-settings store + safe read/update/test
endpoints, with `/api/options` still backward-compatible. No frontend settings UI.**

Concretely:
1. Add `pipeline/provider_settings_store.py` mirroring the existing JSON-store
   pattern (atomic write, whitelist parse, defensive load), managing
   `config/provider_settings.json` (non-secret) and `config/secrets.json`
   (`0600`, secret).
2. Add the resolver layer in `pipeline/provider_config.py`: a settings-first /
   env-fallback lookup used by `build_provider_config` and `get_provider_registry`,
   preserving precedence §4. **Default-path (no store) byte-identical to today.**
3. Add routes `GET /api/provider-settings`, `PATCH /api/provider-settings/{provider}`,
   `POST /api/provider-settings/{provider}/test`,
   `POST /api/provider-settings/{provider}/clear-key` (and optionally
   `/fetch-models`), all behind the single redacting serializer, registered before
   the static mount.
4. Add `config/` to `.gitignore` and `.dockerignore`; add the `./config` volume to
   `docker-compose.yml`.
5. Tests: (a) no-store ⇒ `/api/options` + `build_provider_config` byte-identical to
   today; (b) set key via PATCH ⇒ `configured` flips, key never in any response;
   (c) blank `api_key` keeps existing key, clear-key removes it; (d) test endpoint
   creates no job/artifacts and redacts errors; (e) a grep assertion that no stored
   key substring appears in any `/api/provider-settings*` or `/api/options` response
   or log line.

Verification per repo norm: `npm --prefix frontend run build`,
`python -m compileall api pipeline`, `docker compose config`,
`docker compose build`, `docker compose up`, `curl /api/health`, `curl /api/options`,
`python test_scripts/smoke_release.py`.

**The frontend Providers settings page (§11) is the SECOND slice**, gated on this
backend landing and a review of the redaction tests.

---

## Confirmation

**This document is docs-only. No application code, configuration, `.env`, provider
config, API behavior, frontend, Docker, or dependency/lockfile was changed in this
slice.** The only change is the addition of this design report under `docs/`.
Provider-settings implementation is **NOT** implementation-ready until this design is
reviewed and the first slice (§18) is signed off.
