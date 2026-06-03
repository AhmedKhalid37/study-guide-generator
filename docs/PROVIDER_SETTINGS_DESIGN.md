# PROVIDER_SETTINGS_DESIGN.md — In-app provider settings

> **Status: DESIGN OF RECORD + Slices 1–5 IMPLEMENTED.** Sections §1–§18 below are
> the original **design record** (written design-first, before any code) for a
> safe, server-side provider-settings system so a user can configure providers,
> models, and sampling/runtime defaults **from inside the app** instead of
> hand-editing `.env`, while API keys and other secrets stay strictly server-side
> and never reach the frontend. **The implementation has since landed in five
> slices** — see the "implementation note (landed)" sections §19 (backend store +
> safe endpoints), §20 (frontend Providers UI), §21 (runtime defaults wired into
> live generation), §22 (backend fetch-models endpoint), and §23 (frontend Refresh
> Models UI). Where an implementation note tightened or deferred something relative
> to the design, the note is authoritative. The "DESIGN ONLY" framing applies to
> §1–§18 as the agreed shape; it does **not** mean the feature is unbuilt.
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

## 19. Slice 1 implementation note (landed)

> **Status: §18 first slice IMPLEMENTED** on branch `provider-settings-backend`
> (commit `Add backend provider settings store`). Backend-only; `/api/options`
> shape unchanged; no frontend UI. The original "DESIGN ONLY" banner at the top
> applies to §1–§18 as the design of record; this section records what actually
> shipped and the few places the implementation tightened or deferred the design.

**Shipped exactly as designed**
- Two-file split under a gitignored `config/`: `provider_settings.json` (`0644`,
  non-secret) and `secrets.json` (`0600`, raw keys only), via
  `pipeline/provider_settings_store.py` mirroring the repo's JSON-store discipline
  (atomic temp-file + `os.replace`, whitelist parsing, fail-safe defensive load).
- Precedence §4: a single resolver in `provider_config` (settings → `.env` →
  built-in default) feeds both the registry entries and `build_provider_config`.
  **No store files ⇒ byte-identical to the prior env path** (§15), verified.
  Sampling precedence is preset pin → store → env/default (§4b); presets are never
  a tier on the provider/model ladder (§13) and never repin provider/model.
- Endpoints `GET /api/provider-settings`, `PATCH /api/provider-settings/{provider}`
  (and `PATCH /api/provider-settings` for `default_provider`),
  `POST …/{provider}/clear-key`, `POST …/{provider}/test`, all before the static
  mount, all through the single redacting serializer `_settings_to_public_dict`
  (no key field by construction). `api_key` is write-only; blank = unchanged.
- Test probe: `max_tokens:1`, `temperature:0`, a short dedicated timeout
  (`PROVIDER_TEST_TIMEOUT = 10s`) added to `generate_chat_completion` as an
  opt-in kwarg (default `None` ⇒ byte-identical normal generation), no retries,
  no job/artifacts, errors via `classify_exception` and additionally scrubbed of
  the raw key.

**Tightened vs. the design**
- **`key_hint` requires length > 4** (not `>= 4`). A 4-char placeholder key (e.g.
  a `local` provider set to `"none"`) would otherwise have its last-4 hint equal
  the whole value; requiring `> 4` guarantees the hint is always a proper subset.
  The `local` env default `"local"` is likewise treated as "no real key" for
  `key_source` display.
- **`key_hint`/`key_source` are computed on read** from the secret store / env
  inside the server (the doc's recommended option in §3) — nothing secret-derived
  is persisted in `provider_settings.json`.

**Deferred to a later slice (stored/displayed but not yet wired into generation)**
- `timeout_seconds`, `retry_count`, and `thinking_default` are validated, persisted,
  and surfaced in the public view, but **not** yet applied to the live OpenAI
  client (today's calls always pass an explicit `qwen_thinking`, and timeout/retry
  were never app-configurable). Wiring these is additive and left for the slice
  that needs them.
- `POST …/fetch-models`, encrypted-at-rest secrets / OS keyring, `.env` import, and
  the frontend Providers page (§11) remain deferred.

**Docker**
- `config/` added to `.gitignore` **and** `.dockerignore`; `./config` volume added
  to `docker-compose.yml`; `docker-entrypoint.sh` now chowns `/app/config` to
  `appuser` (the other runtime mounts were already chowned) so the non-root process
  can create the store. Confirmed writable end-to-end in Docker.

---

## 20. Slice 2 implementation note (landed)

> **Status: the §11 frontend Providers page IMPLEMENTED** on branch
> `provider-settings-ui` (commit `Add provider settings UI`). **Frontend + API
> client only** — no backend resolver/security change, no Local Model Manager, no
> provider auto-switching, no generator-preset hard-pinning, no dependency/lockfile
> change. Builds on the Slice 1 endpoints (§19) unchanged.

**Shipped (per §11)**
- **API client helpers** (`frontend/src/api/client.js`): `getProviderSettings`,
  `updateProviderSettings(provider, patch)`, `setDefaultProvider(provider)`,
  `clearProviderKey(provider)`, `testProviderSettings(provider, payload?)`. The
  patch is partial and includes `api_key` **only when non-empty** (blank = keep
  current key, per §8). No helper ever reads a raw key back.
- **New workspace** `ProviderSettingsWorkspace.jsx`, routed from the existing
  **Models** sidebar item. The previous read-only `ModelsPage` (which only rendered
  `/api/options`) was removed in favour of this editor. One card per provider with
  **safe fields only**: configured pill, `key_source`, last-4 `key_hint`,
  `base_url_host`, default-model select (registry ∪ custom), custom-model chips,
  temperature/top_p/max_tokens/timeout/retries, qwen-only thinking tri-state, and
  the `last_test` chip. A top "default provider" select calls
  `PATCH /api/provider-settings {default_provider}`.
- **Write-only key UX (§8):** the API-key input is a password field, never
  prefilled (placeholder shows only the masked `····<hint>`), empty on every load,
  sent only on Save, and cleared after Save. A **Remove key** button calls
  `clear-key` behind a confirm and is disabled unless `key_source === "store"`.
- **Test button (§7):** shows loading → OK/failure and renders only the backend's
  already-classified `{category, message, latency_ms, model}` — never a raw key or
  request body. **Base URL** is a blank-keeps-current override input since the
  backend exposes only `base_url_host`.
- **Resilience (§10):** the Builder keeps reading `/api/options` directly, so a
  failed `GET /api/provider-settings` only surfaces a recoverable error + Retry on
  the settings page; generation is unaffected.

**Security verification (frontend slice)**
- A sentinel key PATCHed on `local` appeared in **none** of
  `/api/provider-settings`, `/api/options`, the PATCH/test responses, the served
  `frontend/dist` JS bundle, or the non-secret `config/provider_settings.json`. It
  lived **only** in `secrets.json` (`0600`); host `cat config/secrets.json` is
  **Permission denied** (expected — the file is owned by the container app user),
  which supports rather than contradicts the §2 model. `clear-key` removed it and
  reverted `local` to `key_source:"env"`.

**Deferred (unchanged from §19):** wiring store `timeout_seconds`/`retry_count`/
`thinking_default` into the live client; `fetch-models`; encrypted-at-rest secrets /
OS keyring; `.env` import.

---

## 21. Slice 3 implementation note (landed)

> **Status: runtime defaults WIRED INTO LIVE GENERATION** on branch
> `provider-settings-runtime` (commit `Apply provider runtime settings`).
> **Backend/runtime + tests/docs only** — no frontend UI change, no provider/model
> auto-switching, no generator-preset hard-pinning, no dependency/lockfile change.
> Closes the "stored/displayed but not yet wired" deferral from §19/§20 for
> `timeout_seconds`, `retry_count`, and `thinking_default`.

**Where the wiring lives (call boundary, not job orchestration).** `LLMConfig`
gained two fields — `timeout: float | None = None` and `retry_count: int = 0` —
both defaulting to the "unset" values so `from_env()` / the CLI path / any caller
that doesn't set them stays byte-identical. `build_provider_config` resolves them
once (settings store → default; **no preset tier and no new env knob**, since
timeout/retry were never env-configurable) and stamps them on every `LLMConfig` it
returns. `generate_chat_completion` consumes them. Because the resolution is in the
shared builder + the single call boundary, **all** generation paths that build a
config through `build_provider_config` (study-guide, style-generate,
outline-generate, section-regenerate, quiz) inherit the behavior consistently,
without touching the orchestrator or job manager.

**Timeout (§4b, store → default).** Precedence in `generate_chat_completion`: an
explicit `timeout=` kwarg wins (the provider **test probe** still passes its short
fail-fast `PROVIDER_TEST_TIMEOUT`), else `config.timeout` from the store, else
`None` ⇒ the OpenAI client's own default (the pre-settings behavior). Passed as the
client-level `timeout` exactly as the Slice 1 probe kwarg did — no second
mechanism.

**Retry (§16 "transient only").** Bounded `[0,10]` (clamped defensively in the
resolver in case the JSON was hand-edited). `generate_chat_completion` makes
`retry_count + 1` attempts, retrying **only** transient API/transport failures —
HTTP 429, any 5xx, and connection/timeout SDK error type-names. It **never**
retries 4xx (auth 401, model-not-found 404, bad-request 400), and missing-config /
unsupported-provider raise in `build_provider_config` *before* any call, so they
can't be retried at all. Cancel is observed at the job boundary, never inside the
(uninterruptible) completion call. The retry is **internal to the single model
call** — no new job, no duplicate artifacts. The test probe forces `retries=0` so a
test fails fast and never hammers upstream (design §7). Linear backoff via a module
constant (`_RETRY_BACKOFF_SECONDS`) so a test can zero it.

**Thinking (§13, qwen-only).** `build_provider_config(qwen_thinking_enabled=...)`
became `bool | None`: an explicit request/preset value wins, else the store
`thinking_default` fills, else `True` (the historical default). The preset path
already passes the preset's pinned `thinking`, so **a preset's thinking beats the
store default** (explicit > store). To let "unset" actually fill from the store,
`LLMJobRequest.qwen_thinking` and the multipart default became `None`; the Builder
frontend still sends an explicit boolean, so the **UI behavior is unchanged** —
`thinking_default` only fills for API callers that omit the field. Applies to qwen
only (the sole `supports_thinking` provider); non-qwen branches ignore it.

**Compatibility guarantee re-verified.** With no `config/provider_settings.json` and
no `config/secrets.json`: `config.timeout is None`, `config.retry_count == 0`, qwen
`enable_thinking == True`, the OpenAI client is built with **no** `timeout` kwarg,
and exactly one attempt is made — byte-identical to trunk.

**Secret redaction unchanged.** No raw key is added to any view, config-as-response,
job manifest, or log: `LLMConfig.api_key` is server-side only and never serialized;
`/api/options` and `/api/provider-settings` still pass through the single redacting
serializers; the probe path still scrubs the key from classified error messages.

**Tests.** `test_scripts/test_provider_runtime_settings.py` (22 checks: no-store
byte-identical; stored timeout reaches the client; stored retry drives transient
retries and stops after `retry_count`; 401/400/404/missing-config are **not**
retried; `thinking_default` fills only when unset; preset thinking wins; preset
never changes provider/model; no key leaks in views or redacted errors). Plus the
existing `test_provider_settings_store.py` (26) and `smoke_release.py` (28/0/0,
incl. live LLM generation through the new path).

**Still deferred (unchanged):** `POST …/fetch-models`; encrypted-at-rest secrets /
OS keyring; `.env` import.

---

## 22. Slice 4 implementation note (landed)

> **Status: the §6 `POST …/{provider}/fetch-models` endpoint IMPLEMENTED** on branch
> `provider-settings-fetch-models` (commit `Add provider fetch-models endpoint`).
> **Backend + tests/docs only** — no frontend UI, no Local Model Manager, no provider
> auto-switching, no generator-preset hard-pinning, no dependency/lockfile change.
> Closes the long-standing `fetch-models` deferral from §19/§20/§21.

**Endpoint.** `POST /api/provider-settings/{provider}/fetch-models`, registered with
the other `/api/provider-settings*` routes **before** the static mount. Unknown
provider → **HTTP 400** (via the existing `_resolve_known_provider`). Runs in a
threadpool (blocking `urllib` call). Returns a small, stable JSON schema:

```jsonc
{ "provider": "qwen", "ok": true, "models": ["…"], "source": "provider",
  "base_url_host": "dashscope-intl.aliyuncs.com", "error": null }
```

On failure `ok:false`, `models:[]`, and `error:{category, message}` (a redacted,
user-safe message). `base_url_host` is **host-only** (`_base_url_host`, userinfo
stripped) — never the full URL.

**Fetch behavior (`provider_config.fetch_provider_models`).** It resolves the
**effective** base URL + key (store → `.env` → built-in default) via the existing
resolvers, then **reuses `_discover_openai_models(base_url, api_key=…)`** — the same
OpenAI-compatible `/models` discovery the `local` provider already uses — for **all**
providers (cloud + local). DeepSeek/Qwen hit `…/v1/models`; local hits
`{base_url}/models` (keeping the existing `host.docker.internal`-only-in-Docker
guard). A short fail-fast `PROVIDER_FETCH_MODELS_TIMEOUT` (10s) replaces the
discovery default so a "Refresh models" probe never hangs. The returned list is
**sorted + de-duplicated** (already done inside `_discover_openai_models`).

- **No model is required for listing.** It does **not** call `build_provider_config`
  (which requires/resolves a model and would force a `local` model error); it only
  needs base URL + key, so an unconfigured-model provider can still list.
- **Unconfigured / no base URL → safe non-OK** (no 400, no leak): missing base URL →
  `error.category:"provider_config"`; provider not `configured` →
  `"provider_auth"` with a generic "{provider} is not configured" message — never
  the missing-key specifics.
- **Errors classified + redacted:** `_classify_fetch_error` maps the discovery error
  string to a coarse category (`provider_auth` / `provider_ratelimit` /
  `provider_model` / `provider_network` / `local_offline` / `provider_error`);
  `_safe_fetch_message` strips the raw key and collapses any full base URL to host
  before returning (and caps length).

**Persistence behavior — READ-ONLY.** The endpoint creates **no job, no artifacts**,
and **does not write** `provider_settings.json` or `secrets.json`. It **does not**
auto-add the fetched ids to `custom_models` — it returns them only. Saving a selected
model into `custom_models` belongs to the future frontend "Refresh models" slice.
(See `DECISIONS.md` "fetch-models is read-only and does not auto-persist".)

**Precedence untouched.** No change to provider/model resolution
(request > store default > `.env` > built-in) or to the sampling/runtime ladders;
generator-preset `model_hint` stays a soft advisory and never repins provider/model.

**Verification.** `test_scripts/test_provider_fetch_models.py` (16 checks): sorted/
deduped success; local uses the `/models` discovery path; unconfigured → safe error;
HTTP 401 + network failures → classified, redacted, no key leak; the stored fake key
absent from the fetch response, `/api/provider-settings`, and `/api/options`; fetch
writes neither JSON file and adds no `custom_models`; provider/model precedence +
preset-pin advisory behavior unchanged. Plus live Docker proof: unknown → 400, local
→ safe `provider_network` timeout, DeepSeek (env-configured) → `ok:true` with the
real provider list; a sentinel key PATCHed on `local` appeared in **none** of the
fetch / `/api/provider-settings` / `/api/options` responses or the container logs,
and was cleared afterward. `test_provider_settings_store.py` 26/26,
`test_provider_runtime_settings.py` 22/22, release smoke **28/28**.

**Still deferred:** the frontend "Refresh models" button + save-to-`custom_models`;
encrypted-at-rest secrets / OS keyring; `.env` import; the Local Model Manager.

---

## 23. Slice 5 implementation note (landed)

> **Status: the §11 frontend "Refresh models" control IMPLEMENTED** on branch
> `provider-settings-fetch-models-ui` (commit `Add provider model refresh UI`).
> **Frontend + API client only** — no backend resolver/security/store change, no
> Local Model Manager, no provider auto-switching, no generator-preset hard-pinning,
> no dependency/lockfile change. Consumes the Slice 4 (§22) read-only endpoint
> unchanged.

**API client (`frontend/src/api/client.js`).** New `fetchProviderModels(provider)`
posts to `POST /api/provider-settings/{provider}/fetch-models` (no body) and returns
the backend's redacted `{provider, ok, models, source, base_url_host, error}`
verbatim. Like the other provider-settings helpers it never reads or echoes a raw
key.

**UI (`ProviderSettingsWorkspace.jsx`).** Each provider card gains a **Refresh
models** button (in a new "Discover models" field) with a loading state:
- **Success** renders the fetched ids in a panel summarized as `{n} fetched ·
  {m} new`. Each *new* id (one not already in the dropdown set = registry ∪ current
  draft `custom_models` ∪ default) shows a per-model **Add** button; an **Add all
  new** action stages every new id at once. Ids already known render a
  non-actionable `in list` / `added` tag (dedupe), so the user never re-adds a
  registry model.
- **Failure** renders only the backend's redacted `{category, message}` — never a
  raw key, full base URL, or userinfo. `base_url_host` is shown host-only as the
  field hint.
- **Empty** (`ok:true`, no models) shows a calm "No models returned — your saved
  models are unchanged" line.

**Review-only, no auto-persist, no auto-switch (the §22 contract upheld in the UI).**
Adding a fetched id only stages it into the card's **draft** `custom_models`;
nothing is written until the existing **Save** runs `PATCH
/api/provider-settings/{provider}`. A successful fetch never saves, never changes
the default model or default provider, and a re-seed of the provider DTO (after
Save / clear-key / page Refresh) clears any shown fetch list. The Builder keeps
reading `/api/options`, which surfaces the saved `custom_models` after Save — so a
newly-added model is selectable in the Builder only once the user deliberately
saves it.

**Security verification (frontend slice).** A sentinel key PATCHed on `local`
appeared in **none** of the fetch-models response, `/api/provider-settings`,
`/api/options`, or the served `frontend/dist` JS bundle, then was cleared (reverting
`local` to `key_source:"env"`). `test_provider_fetch_models.py` 16/16,
`test_provider_settings_store.py` 26/26, release smoke 28/28; frontend build +
`compileall` + `docker compose config`/`build`/`up` all OK, container healthy.

**Deferred (unchanged):** encrypted-at-rest secrets / OS keyring; `.env` import; the
Local Model Manager.

---

## Confirmation

**The design sections above (§1–§18) remain the design of record; Slices 1–5 are
now implemented** (notes §19–§23): backend store + safe endpoints (§19), frontend
Providers UI (§20), runtime defaults wired into live generation (§21), the
read-only fetch-models endpoint (§22), and the frontend Refresh Models UI (§23).
Across all five: no provider auto-switching, no generator-preset hard-pinning, no
dependency/lockfile change, and **raw API keys never leave the server**. The
fetch-models endpoint is read-only and never auto-persists; the Refresh Models UI
stages fetched ids into the draft `custom_models` and requires an **explicit Save**
to persist. **Still deferred:** encrypted-at-rest secrets / OS keyring; `.env`
import; and the **Local Model Manager** — which remains a **separate**,
design-first feature, not part of this provider-settings work.
