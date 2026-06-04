# SHORTCUT_INSPECTOR_REPAIR_DESIGN.md — Inspect & repair broken shortcuts

> **Status: DESIGN ONLY.** No backend or frontend code is implemented in this
> slice. This document defines a safe UX and backend contract for inspecting and
> repairing shortcuts whose saved references (provider / model / style / preset /
> section / axis / tool / view) have become invalid or degraded over time.
>
> **Scope guards honoured by this design:** it does **not** touch provider
> settings runtime, the Local Model Manager, or the large-PDF pipeline; it does
> **not** refactor the shortcut store (it *extends* the public read path and adds
> read-only + opt-in-write endpoints); and it never exposes raw API keys.
>
> Source of truth for the current behaviour: `pipeline/shortcut_store.py`,
> `frontend/src/components/HomeShortcuts.jsx`, `frontend/src/shortcutMeta.js`,
> `frontend/src/components/DesktopDashboard.jsx`,
> `pipeline/generator_presets.py`, `pipeline/provider_config.py`,
> `pipeline/style_store.py`, `pipeline/orchestrator.py`.

---

## 1. Current shortcut data model (as built today)

### 1.1 Storage

- Shortcuts live in a single versioned JSON file at `library/shortcuts.json`
  (`SHORTCUTS_JSON` in `pipeline/shortcut_store.py`), written atomically
  (temp file + `os.replace`, `0644`). It rides the existing `./library` volume
  mount, so it survives container restarts. Gitignored runtime data.
- A registry is `{"version": 1, "shortcuts": [ ... ]}`. Missing/corrupt files
  fall back to a default seed (`_seed_defaults` → `_default_seed`), derived from
  the app's **live** config (real provider default models, real preset/style ids).
- Each stored record has: `id` (`sc_<hex>`), `name`, `description`, `type`,
  `icon`, `color`, `pinned`, `order`, `created_at`, `updated_at`, `payload`.

### 1.2 The three shortcut types and their whitelisted payloads

`SHORTCUT_TYPES = (builder_setup, tool, library_view)`. `_normalize_payload`
builds a **fresh** payload dict reading only known keys — the whitelist security
boundary (any unknown/dangerous incoming key, e.g. `cmd`/`path`/`args`, is never
read, so it can never ride into a saved shortcut).

- **`tool`** → `{ "tool": <str> }`. Recognised keys: `KNOWN_TOOL_KEYS`
  (`clean_markdown`, `improve_guide`, `add_style`, `compare_styles`,
  `export_center`, `find_guide`, `quiz`, `outline`).
- **`library_view`** → `{ "view": <str> }`. Valid views: `KNOWN_VIEW_BASES`
  (`recent`, `pinned`, `failed`, `favorites`, `all`) **or** a prefixed form
  (`folder:<id>`, `tag:<name>`, `search:<query>`).
- **`builder_setup`** → the rich payload:
  - `input_type` ∈ `KNOWN_INPUT_TYPES` (`upload_markdown`/`paste_text`/`generate_llm`), default `generate_llm`.
  - `provider` (str|null), `model` (str|null), `generator_preset` (str|null), `style` (str|null).
  - `mode` (free-text, default `study_guide` — vestigial).
  - `target_pages` (int, clamped 1–100, optional).
  - `modules` (**legacy** dict-of-bool, `KNOWN_MODULE_KEYS`; shortcut/UI-only — never reached prompt assembly).
  - `include_sections` (**canonical** dict-of-bool; normalized via `orchestrator.normalize_include_sections` + `INCLUDE_SECTION_ALIASES`; only canonical enabled keys survive).
  - `output_depth` (enum `OUTPUT_DEPTH_VALUES` | null; **rejected** if invalid), `difficulty` (enum `DIFFICULTY_VALUES` | null; **rejected** if invalid).
  - `strict_math` (bool, default true), `export_formats` (subset of `KNOWN_EXPORT_FORMATS`).

### 1.3 Import / export

- **Export** (`export_shortcut` / `export_all` → `_exportable`): emits the clean
  stored shape (no computed `valid`/`reason`). For `builder_setup` it runs the
  translate-on-read bridge so a legacy `modules`-only shortcut exports with a
  derived `include_sections` (forward-compatible) **without mutating disk**.
- **Import** (`preview_import` / `import_shortcuts` → `_normalize_import_batch`):
  accepts a single object, a bare list, or a `{"shortcuts": [...]}` envelope.
  Each candidate is re-normalized through the **same whitelist** as create. Id
  conflicts get a fresh id unless `overwrite=True`; per-row meta flags
  (`_conflict`, `_overwritten`, `_id_regenerated`) are returned. Invalid items
  (bad `name`/`type`, invalid axis) are pushed into a batch `errors` list rather
  than aborting the whole import. **`overwrite` defaults to `false` everywhere in
  the UI**, so an import never silently replaces an existing shortcut.

### 1.4 How `builder_setup` payloads are normalized

`_normalize_payload(TYPE_BUILDER, raw)` coerces/validates field-by-field:
- string fields trimmed + length-capped (`_clean_str_field`);
- `include_sections` reduced to canonical enabled-only keys in
  `INCLUDE_SECTION_FRAGMENTS` order (unknown keys dropped silently);
- axes validated against the enum and **rejected** (raise `ShortcutStoreError`)
  if bad — not coerced;
- `target_pages` clamped; `export_formats` filtered to the known set.

So at **write** time, sections/axes/export formats/tool/view are already
constrained — the *only* references that can rot after a valid save are the ones
checked against **live, mutable** config (provider, model, preset, style, and
the section/axis/tool/view *vocabulary* if the app later removes a key).

### 1.5 What `valid` / `reason` mean today

`_evaluate_validity(record)` is computed at **read time** (in `_public`, never
stored) and returns `(valid: bool, reason: str|None)`:

| type | check | reason on failure |
|---|---|---|
| `tool` | `payload.tool ∈ KNOWN_TOOL_KEYS` | `"references unavailable tool"` |
| `library_view` | view base known or known prefix | `"references unavailable view"` |
| `builder_setup` | `_provider_is_configured(provider)` | `"references unavailable provider"` |
| `builder_setup` | preset exists (if set) | `"references unavailable generator preset"` |
| `builder_setup` | style exists (if set) | `"references unavailable style"` |

`_public` attaches `valid`/`reason` to the returned view. The frontend already
consumes it: Home cards show a "Needs setup" badge + `invalidHint()` copy and set
`aria-disabled`; the customize rows + import preview show a "needs setup" chip;
`DesktopDashboard.handleActivateShortcut` refuses to load an invalid
`builder_setup` and instead routes the user to the Models page.

**Three concrete gaps in today's `valid`/`reason`:**

1. **Binary only.** It collapses "totally broken" and "usable but degraded"
   into one `valid:false`. A shortcut whose *style was deleted* (recoverable —
   could still generate with a default style) is treated identically to one
   whose *provider has no key* (genuinely unusable).
2. **First-failure only.** It returns at the first failing reference, so a
   shortcut with both a missing provider **and** a missing style reports only the
   provider. The user fixes one thing, re-checks, and discovers another.
3. **`model` is never validated.** `_evaluate_validity` checks provider/preset/
   style but **not** `payload.model`. A saved model that's no longer in the
   provider's `available_models` is silently resolved/fallen-back at Builder
   prefill time (`pendingPrefillRef` in `BuilderWorkspace.jsx`), so the card
   still says "valid" while the saved model is actually gone. Custom-model
   removal and provider model-registry changes are invisible to the badge.

This design **keeps `valid`/`reason` exactly as-is for backward compatibility**
(the existing frontend keeps working untouched) and **adds** a richer, additive
`validity` object alongside it.

---

## 2. What makes a shortcut invalid or degraded

Enumerated against the live registries each reference is checked against:

| Reference | Checked against | Failure condition | Severity |
|---|---|---|---|
| provider | `provider_config.get_provider_entry(...).configured` | provider unknown, or known but **not configured** (no key) | **broken** |
| model | the provider entry's `available_models` | `payload.model` set but not in the (configured) provider's model list (custom model removed, model retired/renamed) | **degraded** (provider default can serve) |
| generator preset | `generator_presets.generator_preset_exists` | preset id unknown (removed/renamed) | **degraded** (can generate without a preset) |
| style | `style_store.style_exists` | style id unknown (deleted/renamed) | **degraded** (can generate with a default/none style) |
| include_sections key | `orchestrator.INCLUDE_SECTION_FRAGMENTS` | a stored canonical key is no longer in the orchestrator map | **degraded** (drop unknown keys) |
| output_depth / difficulty | `OUTPUT_DEPTH_VALUES` / `DIFFICULTY_VALUES` | stored axis value no longer in the enum | **degraded** (drop the axis) |
| tool | `KNOWN_TOOL_KEYS` | tool key removed | **broken** (nothing to route to) |
| library view | `KNOWN_VIEW_BASES` / prefixes | view base/prefix removed | **broken** |
| export_formats | `KNOWN_EXPORT_FORMATS` | format removed (unlikely) | **degraded** (drop format) |
| legacy/stale fields | whitelist | old `modules`, unknown payload keys | **info** (already inert / translated-on-read; no action needed) |

Notes:
- Most "degraded" cases for **sections / axes / export formats** can't actually
  occur for a shortcut that was *saved by the current code* (they're normalized
  away at write). They matter for shortcuts written by an **older build** or
  hand-edited/imported JSON — exactly the "import brings in old/deprecated
  fields" case in the brief. The inspector reports them so a repair can drop them
  cleanly rather than leaving a dead toggle.
- `model` and `provider` are the real-world common breakages (a key is cleared,
  a custom model is removed, a default model changes).

---

## 3. Validation categories (three tiers)

Replace the binary read state with a **derived 3-tier status**, computed from a
list of per-reference findings:

- **`valid`** — every reference resolves; the shortcut loads exactly as saved.
- **`degraded`** (warning, *usable*) — at least one **optional/soft** reference
  is missing (style, preset, model, unknown section/axis/export key) but the
  shortcut can still launch a working setup by **dropping or defaulting** the
  bad parts. The user is warned but not blocked.
- **`broken`** (needs repair, *not usable as-is*) — at least one **required**
  reference is missing: an unconfigured/unknown **provider** for a
  `builder_setup`, or an unavailable **tool**/**view** for those types. Launching
  would drop the user into a non-functional setup, so activation is gated to
  repair-or-redirect.

Mapping rule: **status = worst severity across findings** (`broken` >
`degraded` > `valid`). `valid` (the existing boolean) stays `= (status ==
"valid")` so old consumers are unchanged: a degraded shortcut keeps reporting
`valid:false` today, but the new `status` lets the UI distinguish "usable with
warnings" from "blocked".

> **Decision (see DECISIONS.md):** keep the legacy boolean `valid`/`reason`
> untouched and **add** a richer `validity` object. Do not repurpose `valid` to
> mean "usable", because the existing activation guard treats `valid:false` as
> "do not load" — silently flipping its meaning would let a degraded shortcut
> auto-load with parts missing, violating "no silent rewrite".

---

## 4. Backend API contract (proposed)

All additive. Reads never mutate `shortcuts.json` (no migration-on-read).
Writes happen **only** on the explicit apply endpoint.

### 4.1 Enriched read shape (additive field on the existing list/get)

`GET /api/shortcuts` and `GET /api/shortcuts/{id}` gain an additive `validity`
object on each shortcut view (computed in `_public`, alongside the unchanged
`valid`/`reason`):

```jsonc
"validity": {
  "status": "valid" | "degraded" | "broken",
  "findings": [
    {
      "field": "provider",          // provider|model|generator_preset|style|include_sections|output_depth|difficulty|tool|view|export_formats
      "severity": "broken" | "degraded" | "info",
      "code": "provider_unconfigured", // stable machine code (see §4.5)
      "value": "deepseek",          // the offending stored value (never a key/secret)
      "message": "DeepSeek is not configured (no API key)."
    }
  ]
}
```

- `status` is the worst severity of `findings` (empty findings ⇒ `valid`).
- `findings` is the **full** list (fixes gap #2) and **includes** the model
  check (fixes gap #3).
- No raw keys: `provider_config` already redacts; the inspector reads only
  `configured` / `available_models` / `default_model` — never `secrets.json`.

### 4.2 Inspect one shortcut (read-only)

`GET /api/shortcuts/{id}/inspect`

Returns the shortcut view **plus** repair *candidates* for each finding (the
data the UI needs to offer a replacement) — still read-only, no mutation:

```jsonc
{
  "shortcut": { ...the _public view including validity... },
  "repairs": [
    {
      "field": "provider",
      "code": "provider_unconfigured",
      "current": "deepseek",
      "suggested": "qwen",                  // first configured provider, or null
      "options": [                          // safe, derived choices the UI lists
        { "id": "qwen", "label": "Qwen", "configured": true }
      ],
      "removable": false                    // provider can't just be dropped
    },
    {
      "field": "style",
      "code": "style_missing",
      "current": "old_custom_style",
      "suggested": null,
      "options": [ { "id": "basic_study_guide", "label": "Basic Study Guide" }, ... ],
      "removable": true                     // style can be cleared (use default)
    }
  ]
}
```

- `options` are derived from the live registries (`provider_config` configured
  providers, the chosen provider's `available_models`, `list_generator_presets`,
  `style_store.list_styles`, the section/axis vocab) — **non-secret, redacted**.
- `suggested` is a conservative default (e.g. first configured provider; the
  provider's `default_model` for a missing model) but is **never auto-applied**.

### 4.3 Preview a repair (read-only)

`POST /api/shortcuts/{id}/repair/preview`

Body: a **repair instruction set** — explicit, per-field choices the user made:

```jsonc
{
  "repairs": {
    "provider": { "action": "replace", "value": "qwen" },
    "model":    { "action": "replace", "value": "qwen3.7-max" },
    "style":    { "action": "remove" },
    "generator_preset": { "action": "keep" },
    "include_sections": { "action": "drop_unknown" }   // strip keys not in the vocab
  },
  "clone": false        // if true, the previewed result would be saved as a NEW shortcut
}
```

Returns the **proposed** post-repair shortcut view (re-validated) **without
saving**, plus a `changes` diff and the resulting `validity`:

```jsonc
{
  "preview": { ...proposed _public view, re-validated... },
  "changes": [
    { "field": "provider", "from": "deepseek", "to": "qwen" },
    { "field": "model", "from": "deepseek-v4-pro", "to": "qwen3.7-max" },
    { "field": "style", "from": "old_custom_style", "to": null }
  ],
  "resulting_status": "valid",
  "clone": false
}
```

- The preview runs the proposed payload through the **same** `_normalize_payload`
  + `_evaluate_validity`/findings logic, so the previewed status is exactly what
  apply would produce. Pure function of inputs; touches no disk.
- Unknown/invalid replacement values are rejected the same way create/update
  reject them (HTTP 400), so the preview can't promise an illegal repair.

### 4.4 Apply a repair (the only write)

`POST /api/shortcuts/{id}/repair/apply`

Same body as preview. Behaviour:
- `clone: false` → updates the existing shortcut in place via the **existing**
  `update_shortcut` path (so the same whitelist + normalization + atomic write
  apply; `updated_at` bumps). Returns the saved view.
- `clone: true` → leaves the original untouched and **creates a new** shortcut
  (via `create_shortcut`) with the repaired payload and a `" (repaired)"`-suffixed
  name. Returns both ids. This is the "clone before repair if destructive" path.
- Repairs are **opt-in per field**: a field with `action: "keep"` (or absent) is
  left exactly as stored. Apply never touches a field the user didn't choose.
- Re-validates after write; if the result is still `broken`, it still saves (the
  user may be doing a partial fix) but the response surfaces the remaining
  `validity` so the UI can keep warning.

### 4.5 Stable finding/repair codes

A small fixed vocabulary (so the frontend maps codes → copy, like
`invalidHint` does today), e.g.:
`provider_unknown`, `provider_unconfigured`, `model_unavailable`,
`generator_preset_missing`, `style_missing`, `section_unknown`,
`axis_unknown`, `export_format_unknown`, `tool_unavailable`, `view_unavailable`,
`legacy_field_present`.

### 4.6 Invariants the contract preserves

- **Reads never mutate.** `GET …/inspect` and `…/repair/preview` are pure;
  `shortcuts.json` is byte-identical before/after (mirrors the existing
  translate-on-read guarantee).
- **Imports keep whitelist behaviour.** No change to import: it still
  re-normalizes through the whitelist and reports invalid items in `errors`. The
  inspector simply makes a *post-import* "needs repair" state visible and
  actionable; it does not loosen import validation.
- **One write path.** Apply reuses `update_shortcut`/`create_shortcut`; no new
  raw write to `shortcuts.json`, so the store's atomic-write + whitelist
  invariants hold automatically.
- **No raw keys** anywhere in any response (provider data is already redacted).

---

## 5. Frontend UX (proposed)

Consumes the new `validity`/`inspect`/`preview`/`apply` contract. Reuses the
existing badge/chip/modal patterns in `HomeShortcuts.jsx`; no new design system.

### 5.1 Home shortcut card status badge

- Today: a single amber "Needs setup" badge when `valid === false`.
- Proposed: drive the badge off `validity.status`:
  - `valid` → no badge (unchanged).
  - `degraded` → a **soft** amber "Usable — needs review" badge; the card still
    activates (loads with the degraded parts dropped/defaulted, after a one-time
    confirmation — see §5.5), so the user isn't blocked.
  - `broken` → a **red** "Needs repair" badge; clicking opens the Inspector
    instead of loading a broken setup (replaces today's silent redirect-to-Models
    with an explainable repair surface).
- Tooltip uses the first finding's `message`; keep the existing `aria-disabled`
  semantics for `broken`.

### 5.2 Customize Shortcuts modal — per-row warnings + "Repair"

- Each `ShortcutRow` shows a status chip (`valid`/`degraded`/`broken`) instead of
  the single "needs setup" chip.
- Rows that are `degraded`/`broken` gain a **Repair** icon-button (wrench) next to
  Edit/Duplicate that opens the Inspector drawer for that shortcut.
- Import preview rows already show a per-item invalid chip; extend them to show
  the tiered status and, for a `broken`/`degraded` imported item, a "Repair after
  import" hint (repair runs against the saved shortcut, post-import).

### 5.3 Inspector drawer / modal

A focused panel (reuse the modal shell) showing, for one shortcut:
- Header: name, type, overall status.
- A **findings list**: one row per finding — field, human message, severity icon.
- For each repairable finding, an inline **repair control**:
  - **provider** → a `<select>` of configured providers (`suggested` preselected).
  - **model** → a `<select>` of the chosen provider's `available_models`
    (defaults to "Provider default" = clear the saved model).
  - **style** → a `<select>` of built-in + custom styles, plus "None (use default)".
  - **generator preset** → a `<select>` of available presets, plus "None".
  - **unknown sections / axes / export formats** → a "Remove unavailable" toggle
    (drops the dead keys).
- A **Clone before repair** checkbox (default **off** for in-place; the UI
  *recommends* clone when the user is repairing a default/shared shortcut).
- Live **preview**: as the user makes choices, call `…/repair/preview` and show
  the `changes` diff + resulting status ("This will become **Valid**").
- A clear **explanation block** before applying: plain-language summary of what
  will change (e.g. "Provider DeepSeek → Qwen; model cleared to provider default;
  style 'old_custom_style' removed"). Nothing is written until the user clicks
  **Apply repair** (or **Save as repaired copy** when clone is on).

### 5.4 Suggested repair actions (the menu the brief asks for)

- choose replacement **provider** (configured only);
- choose replacement **model** (within the chosen provider);
- choose replacement **style**;
- choose replacement **generator preset**;
- **remove** unavailable optional fields (style/preset/model/sections/axes/formats);
- **clone before repair** (non-destructive: original kept, repaired copy created).

### 5.5 Clear explanation before applying

- The Inspector always shows the diff + resulting status before the Apply button
  is enabled.
- Activating a **degraded** card from Home shows a one-line confirm ("This
  shortcut's style/model is unavailable and will be skipped — continue?") rather
  than silently loading a changed setup. Choosing "Repair instead" opens the
  Inspector.

---

## 6. Safety rules preserved

- **No silent overwrite.** Every state change is an explicit user action
  (Apply / Save copy). Preview is read-only. Activation of a degraded shortcut
  requires a confirm; broken shortcuts cannot auto-load.
- **No auto-switch of provider/model.** `suggested` values are *preselected
  hints*, never applied without the user confirming via Apply. Consistent with
  the existing "soft `model_hint`, not a hard pin" decision.
- **No raw keys exposed.** All provider data flows through the already-redacted
  `provider_config` public surface (`configured`/`available_models`/
  `default_model`/`key_hint`), never `secrets.json`.
- **No migration-on-read.** `inspect`/`preview` and the enriched `validity` field
  are computed at read time and write nothing — `shortcuts.json` stays
  byte-identical until the user explicitly applies a repair (mirrors the existing
  translate-on-read bridge guarantee).
- **Old shortcuts still load as much as possible.** Degraded shortcuts remain
  launchable (bad parts dropped/defaulted with consent); the whitelist + bridge
  keep legacy `modules`/section fields readable. Repair is *offered*, never forced.

---

## 7. Implementation slices

Each slice is independently shippable and verifiable (build + compile + docker +
smoke), one branch per slice, surgical edits.

### Slice 1 — backend inspector only (read-only)
- Add a findings engine in `shortcut_store.py`: a `_collect_findings(record)`
  that returns the full list (provider/model/preset/style/section/axis/export/
  tool/view), and a `_validity(record)` that derives `status` from findings.
- Add the additive `validity` object to `_public` (keep `valid`/`reason` exactly
  as-is, derived from the new engine so they stay consistent).
- Add `GET /api/shortcuts/{id}/inspect` (shortcut view + repair candidates from
  live registries). **No write paths, no frontend.**
- Model check uses `provider_config` `available_models`; everything redacted.

> **IMPLEMENTED — Slice 1 (branch `shortcut-inspector-backend`, DONE #39 in
> `CURRENT_TASK.md`).** Shipped exactly as scoped, read-only, additive:
>
> - **Engine in `pipeline/shortcut_store.py`:** `_collect_findings(record)` (a
>   fail-soft wrapper around `_collect_findings_inner`; on any unexpected error it
>   returns a single `inspection_error` *degraded* finding rather than crashing a
>   list/read), `_status_from_findings` (`error`⇒`broken`, `warning`⇒`degraded`,
>   else `valid`), and `_validity(record)` → `{status, findings[], repairable}`.
>   Candidate lists come from live **redacted** registries
>   (`_provider_candidates`/`_provider_models`/`_style_candidates`/
>   `_preset_candidates`/section + axis vocab) — provider/model/style/preset
>   ids + labels only, never a key.
> - **Finding shape** matches the brief: `{code, severity, field, message,
>   current_value, repairable, candidates?}`. Severity uses `error`/`warning`/
>   `info` (mapping to the `broken`/`degraded`/`valid` tiers). Codes implemented:
>   `provider_missing`, `provider_unconfigured`, `model_unavailable`,
>   `style_missing`, `generator_preset_missing`, `section_unknown`,
>   `output_depth_invalid`, `difficulty_invalid`, `tool_route_missing` (used for
>   both unavailable tool **and** view), `legacy_field_ignored`,
>   `payload_shape_invalid`, `inspection_error`.
> - **Additive `validity`** is attached in `_public`, so it rides `GET
>   /api/shortcuts`, `GET /api/shortcuts/{id}`, and import-preview. Export
>   (`_exportable`) is untouched (still no computed fields).
> - **Route:** `GET /api/shortcuts/{id}/inspect` returns the flat
>   `{id, name, type, valid, reason, validity, repair_candidates}` shape from the
>   brief (not the nested `{shortcut, repairs}` sketch in §4.2). `repair_candidates`
>   carries `providers`, `models_by_provider`, `styles`, `generator_presets`,
>   plus `sections`/`output_depth`/`difficulty`. Unknown id → 404.
> - **Legacy-`valid` divergence (intentional):** see §9 below and the
>   `DECISIONS.md` entry. Unlike the §3 sketch, the implementation does **not**
>   force `valid == (status == "valid")`; `valid`/`reason` come from the untouched
>   `_evaluate_validity`, so a *newly-detected* degraded case (`model_unavailable`,
>   `section_unknown`, invalid axis) keeps the legacy `valid:true` it has today
>   while `validity.status` becomes `degraded`. This preserves the activation
>   guard byte-for-byte. Invalid axes are treated as **degraded** (ignored/
>   defaulted at load), not broken.
> - **Tests:** `test_scripts/test_shortcut_inspector.py` (19/19) +
>   `test_shortcut_store.py` (39/39, unchanged) + live Docker proof; read-only
>   `shortcuts.json` sha256 unchanged; sentinel-key leak scan clean.

### Slice 2 — frontend badges + Inspector UI (read-only)
- Drive Home card badge + customize-row chip off `validity.status` (3 tiers).
- Add the Inspector drawer that calls `…/inspect` and renders findings + repair
  candidate controls + a (still preview-less) summary. Add the **Repair** button
  to degraded/broken rows.
- No apply yet: the drawer can show what's wrong and what *could* be chosen, with
  Apply disabled/"coming next". (Or gate the whole drawer behind Slice 3 if
  preferred — but read-only inspection is useful on its own.)

> **IMPLEMENTED — Slice 2 (branch `shortcut-inspector-ui`, DONE #40 in
> `CURRENT_TASK.md`).** Frontend-only + API client + a node harness + docs;
> **no backend behaviour changed** (the Slice 1 response shape was correct as-is).
> Read-only — there is no preview/apply/repair/mutation anywhere in this slice.
>
> - **API client:** `inspectShortcut(id)` in `frontend/src/api/client.js` → `GET
>   /api/shortcuts/{id}/inspect`, using the shared `requestJson` helper (404 /
>   network errors surface the server `detail` like every other helper). The
>   response is already redacted; the client never handles a raw key.
> - **Status helpers (`frontend/src/shortcutStatus.js`, pure, no React):**
>   `shortcutStatus` (prefers `validity.status`; **fallback** for old payloads
>   with no `validity` → `valid:false` ⇒ broken, else valid), `statusBadge`
>   (label/tone: valid→"Valid", degraded→"Needs attention", broken→"Broken"),
>   `countFindingsBySeverity`, `issueCount`, `shortcutFindings`. Tolerates missing
>   validity, unknown status, non-array findings, null shortcut.
> - **Home cards (`HomeShortcuts.jsx`):** valid stays quiet (no badge); degraded →
>   amber "Needs attention" chip, broken → red "Broken" chip. The chip + a small
>   Info button are clickable (`stopPropagation`) to open the Inspector. **Card
>   activation is unchanged** — still gated on the legacy `valid` boolean, routed
>   by `DesktopDashboard.handleActivateShortcut` exactly as before (broken
>   shortcuts are never auto-routed to Builder/Tools by this slice).
> - **Customize rows:** per-row tiered status chip + issue count, plus an
>   **Inspect** icon-button opening the drawer. Create/edit/import/export/reorder/
>   pin/delete behaviour untouched. Import-preview rows left as-is (they have no
>   saved id to inspect; "repair after import" stays a Slice 3 idea).
> - **Inspector drawer (`ShortcutInspector.jsx`):** right-side read-only panel.
>   Calls `inspectShortcut(id)` on open (seeds header from the list view while
>   loading); shows loading / 404 / network-error states; renders name, type,
>   status pill, legacy `valid/reason` (when blocked), every finding (code, field,
>   severity, message, current_value, repairable + candidate count), and a
>   candidates **summary** (configured/total providers, models-per-provider,
>   style/preset/section/axis counts). States plainly: *"Repair actions are not
>   available yet. This inspector is read-only."* The only repair control is a
>   **disabled** "Repair (coming next)" button — no Save/Apply.
> - **Tests:** node harness `frontend/scripts/verify-shortcut-status.mjs` (25/25,
>   wired into `npm --prefix frontend test`) covering status normalization, old-
>   payload fallback, finding counts, badge labels. Backend `test_shortcut_*`
>   unchanged (19/19 + 39/39). Live Docker: real Chromium drove the degraded badge
>   → Inspector (findings + candidates + read-only note + disabled repair, no
>   Apply), the Customize-row Inspect button, and a valid shortcut's "No problems
>   found". Full secret scan (served bundle + inspect/list/options/provider-
>   settings + logs) clean.

### Slice 3 — repair apply flow
- Add `POST …/repair/preview` (pure) and `POST …/repair/apply`
  (`update_shortcut` in place, or `create_shortcut` when `clone`).
- Wire the Inspector's live preview + diff + Apply / Save-as-copy. Add the
  degraded-activation confirm + "Repair instead" path on Home.

> **IMPLEMENTED — Slice 3A: backend repair endpoints (branch
> `shortcut-inspector-repair-backend`, DONE #41 in `CURRENT_TASK.md`).**
> Backend-only; **the frontend repair UI wiring is Slice 3B and remains
> deferred.**
>
> - **One shared normalizer (`_prepare_repair`) in `pipeline/shortcut_store.py`**
>   feeds both `preview_repair` (read-only) and `apply_repair` (the only write),
>   so a preview is byte-for-byte the computation an apply would persist.
> - **Request schema (the brief's explicit patch, slightly tightened):**
>   ```jsonc
>   {
>     "mode": "in_place" | "clone",
>     "changes": {
>       "provider": "qwen", "model": "qwen3.7-plus",
>       "style": "baby_steps", "generator_preset": "claude_cram",
>       "output_depth": "balanced", "difficulty": "exam_level",
>       "include_sections": { "remove": ["unknown_key"], "set": {"glossary": true} },
>       "remove_fields": ["generator_preset", "model"]
>     },
>     "clone_name": "Repaired shortcut name"   // clone only; derived if omitted
>   }
>   ```
>   This is an **explicit whitelist** — unknown top-level keys (outside
>   `mode`/`changes`/`clone_name`) and unknown `changes` keys are **rejected
>   (HTTP 400)**, not silently ignored (the mutation-boundary rule). `remove_fields`
>   may only drop **optional** builder fields (`model`/`style`/`generator_preset`/
>   `output_depth`/`difficulty`); **`provider` is not removable**. The proposed
>   payload is run through the same `_normalize_payload` as create/update, so
>   nothing outside the schema ever persists. **No arbitrary JSON merge-patch.**
> - **Validation against live config:** a replacement provider must resolve **and**
>   be configured; a replacement model is validated against the **repaired** provider
>   (provider supplied in the same repair wins, else the existing provider; a
>   model-only repair with no provider context → 400); style/preset checked for
>   existence; axes validated by the store enum; `include_sections.set` keys must be
>   canonical/alias keys. All invalid values → 400, nothing written.
> - **Responses** follow the brief's suggested shapes. Preview returns
>   `{ok, mode, shortcut_id, original{…validity}, proposed{name, type, payload,
>   …validity}, diff[], warnings[]}`; apply returns `{ok, mode, shortcut{public
>   payload}, diff[], warnings[]}`. `diff` is per-field
>   (`{field: "payload.<k>", from, to}`); `warnings` flags a still-degraded/broken
>   result.
> - **Apply reuses existing CRUD** — `update_shortcut` (in place, id + other fields
>   preserved, `updated_at` bumped) or `create_shortcut` (clone: new id, original
>   untouched, name = `clone_name` or `"<name> (repaired copy)"`). No new raw write
>   path, so the store's whitelist + atomic write hold automatically.
> - **Routes:** `POST /api/shortcuts/{id}/repair/preview` + `…/repair/apply`,
>   registered with the other `/api/shortcuts/*` routes (before the static
>   catch-all). Unknown id → 404; bad request → 400. Repair currently supports
>   `builder_setup` only (others → safe 400).
> - **Invariants honoured:** read-only preview (`shortcuts.json` sha256 unchanged),
>   no auto-repair, no migration-on-read, no silent overwrite, no provider/model
>   auto-switch (preset `model_hint` stays advisory), no raw key read or returned.
> - **Tests:** `test_scripts/test_shortcut_repair.py` (29/29) +
>   `test_shortcut_store.py` (39/39) + `test_shortcut_inspector.py` (19/19) +
>   `test_provider_settings_store.py` (26/26), all unchanged/green.

> **IMPLEMENTED — Slice 3B: frontend repair UI wiring (branch
> `shortcut-inspector-repair-ui`, DONE #42 in `CURRENT_TASK.md`).** Frontend +
> API client + a node harness + docs; **no backend behaviour changed** (the Slice
> 3A contract was correct as-is). Turns the read-only Slice 2 drawer into a safe
> repair surface.
>
> - **API client (`frontend/src/api/client.js`):** `previewShortcutRepair(id,
>   payload)` (READ-ONLY) + `applyShortcutRepair(id, payload)` (the only write),
>   using the shared `requestJson` helper, so 400/404 surface the server `detail`
>   like every other call. Both send the Slice 3A whitelisted patch
>   (`{mode, changes{…}, clone_name?}`); responses are already redacted.
> - **Pure helpers (`frontend/src/shortcutRepair.js`, no React):**
>   `emptyRepairDraft` (starts empty), `buildRepairPayload` (draft → request;
>   drops empty `replace` values so a half-finished choice never mutates),
>   `draftHasChanges`, `draftSignature` (stable signature for preview staleness),
>   `modelCandidatesForProvider` (filters models by the effective provider),
>   `effectiveProvider` (a chosen replacement provider wins over the saved one),
>   `defaultCloneName` (`"{name} (repaired copy)"`), `repairFieldKey`
>   (finding.field → supported repair key, or null). The frontend never widens the
>   backend's field/op vocabulary.
> - **Inspector drawer (`ShortcutInspector.jsx`):** the disabled "Repair (coming
>   next)" footer is replaced with an enabled repair panel **only** when the
>   shortcut is a repairable `builder_setup` with a supported action; otherwise a
>   calm "No repair needed." / "No supported repair action for these findings."
>   note (no Apply). Per repairable finding it renders a control: provider/model/
>   style/preset/output_depth/difficulty as Keep / Replace-with / Remove selects
>   (model filtered by the selected/repaired provider; provider is **not**
>   removable), and a per-key Remove toggle for unknown `include_sections` keys.
>   A mode selector (in-place / clone) with a clone-name input (default
>   `"{name} (repaired copy)"`). **Preview repair** calls the read-only endpoint
>   and shows the proposed mode, the field diff, the resulting status, warnings,
>   and an "original is unchanged until you apply" note. **Apply** is disabled
>   until a *fresh* preview exists for the current draft (editing the draft marks
>   the preview stale and re-disables Apply), and requires an explicit confirm
>   step whose copy differs for in-place ("update the saved shortcut") vs clone
>   ("create a repaired copy and leave the original unchanged"). On success it
>   refreshes the parent list (`onRepaired`) and re-inspects in place.
> - **Safety:** no repair API call on open; draft starts empty; no apply without a
>   fresh preview + explicit confirm; no provider/model auto-switch (suggestions
>   are never auto-applied); tolerant of missing candidates / unknown finding codes
>   / old shortcut payloads. Card **activation behaviour is unchanged** (still
>   gated on legacy `valid`; broken never auto-routed).
> - **Tests:** node harness `frontend/scripts/verify-shortcut-repair.mjs`
>   (`npm --prefix frontend run test:shortcut-repair`) covering payload shape,
>   empty-draft no-op, clone name/default, model filtering, effective-provider,
>   and the staleness signature. Backend `test_shortcut_*` unchanged (29/29 +
>   19/19 + 39/39). Live Docker: real repair flow proven end-to-end (broken →
>   inspect → preview is byte-identical to the list before/after → apply in-place
>   keeps the id and flips to valid → clone makes a new id and leaves the original
>   broken → invalid provider → 400). Release smoke 28/28; full secret scan
>   (served bundle + inspect/preview/apply/list/options/provider-settings + logs)
>   clean.

### Optional later polish
- "Repair all" batch action across multiple broken shortcuts (loops apply).
- A Home banner summarising "N shortcuts need attention".
- Auto-suggest the closest model by normalized-token match (reuse `presetMeta`'s
  matcher idea) — still preselect-only, never auto-apply.

---

## 8. Acceptance tests per slice

### Slice 1 (backend inspector)
- `validity.status` is `valid` for a fully-resolving shortcut; `degraded` when
  only style/preset/model/unknown-section is missing; `broken` when the provider
  is unconfigured or a tool/view is unavailable.
- `findings` lists **all** problems (a shortcut missing both provider and style
  returns two findings) — proves gap #2 fixed.
- A `builder_setup` whose saved `model` is not in the configured provider's
  `available_models` yields a `model_unavailable` (severity `degraded`) finding —
  proves gap #3 fixed.
- Legacy `valid`/`reason` are unchanged for every existing fixture (`valid ==
  (status == "valid")`; `reason` == the first broken-or-degraded message as
  today). Existing `test_scripts/test_shortcut_store.py` stays green.
- `GET …/inspect` returns redacted repair `options` (configured providers,
  provider models, styles, presets); a full-payload secret scan finds **no** key.
- **No-mutation proof:** `sha256(shortcuts.json)` identical before/after a list +
  inspect of a deliberately-broken injected shortcut.

### Slice 2 (frontend badges + Inspector)
- Home renders the correct badge tier for valid/degraded/broken fixtures (DOM
  presence in the built bundle, via the existing esbuild-harness pattern).
- A broken card opens the Inspector (does not load the Builder); a degraded card
  shows the soft badge.
- Inspector lists findings and renders the right control per field (provider/
  model/style/preset selects, remove toggles) seeded from `…/inspect`.
- No raw key string anywhere in the served bundle or network payloads.

### Slice 3 (repair apply)
- `…/repair/preview` returns the correct `changes` diff and `resulting_status`
  without writing (sha256 unchanged).
- `…/repair/apply` `clone:false` updates in place (status improves, `updated_at`
  bumps, id stable); `clone:true` leaves the original and creates a new
  `" (repaired)"` shortcut.
- Invalid replacement values (unknown provider/model/preset/style, bad axis) →
  HTTP 400, nothing written.
- A partial repair (fix provider, leave style missing) saves and the response
  still reports the remaining `degraded` finding.
- Live end-to-end in Docker: break a shortcut (clear a provider key / remove a
  custom model), inspect → preview → apply → shortcut becomes valid and launches.

---

## 9. Risk analysis

- **Meaning drift on `valid`.** The biggest risk is changing what `valid:false`
  means and breaking the existing activation guard. *Mitigation:* keep `valid`/
  `reason` byte-compatible; add `validity` alongside; gate behaviour off the new
  `status`. Covered by the "legacy unchanged" acceptance test.
- **False "broken" from a flaky registry read.** If `get_provider_entry` throws
  transiently, a shortcut could be mislabelled broken. *Mitigation:* the existing
  `_provider_is_configured` already swallows exceptions to `False`; the inspector
  should treat *inspection* failures as `degraded`/`info` (fail-soft, like the
  large-PDF preflight degrades to `ok`), never hard-block, and never crash a list.
- **Auto-apply creep.** Pressure to "just fix it for the user" risks silent
  rewrites. *Mitigation:* the contract makes apply the *only* write and requires
  an explicit per-field instruction; preview is mandatory in the UX.
- **Model-suggestion wrongness.** Auto-suggesting a replacement model could pick a
  poor match. *Mitigation:* suggestions are preselect-only; default is "provider
  default" (clear the model), which is always safe.
- **Clone proliferation.** Repeated clone-before-repair could clutter the list.
  *Mitigation:* clone is opt-in (default off for in-place), name-suffixed, and
  subject to the existing `MAX_SHORTCUTS` cap.
- **Scope creep into store refactor.** *Mitigation:* the findings engine is
  additive (new functions + an additive field); apply reuses existing CRUD. No
  change to the whitelist, write format, or import semantics.
- **Two transports drift.** Repair endpoints are JSON-only (no attachments), so
  the `/api/jobs/llm` two-path rule does not apply; but the permanent rule is
  noted so a future field addition stays consistent.

---

## 10. Recommendation

Proceed with **Slice 1 (backend inspector, read-only)** first — it is low-risk,
purely additive, immediately fixes the three real gaps (binary status, first-
failure-only, missing model check), and gives the frontend a stable contract to
build against. Slices 2 and 3 follow with sign-off. No code is implemented in
this design slice.
