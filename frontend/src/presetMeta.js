// Generator-preset display helpers for the Builder preset cards (Slice C4b).
//
// This file holds ONLY frontend display/compat logic. The preset DATA (id, name,
// purpose, description, recommended_use, model, model_hint, provider, params,
// available) is owned by the backend and reaches the UI through
// `/api/options.generator_presets` (see `pipeline/generator_presets.py`). Never
// hardcode preset copy here — consume the backend metadata.
//
// Two responsibilities:
//   1. Map a provider id → a local SVG logo (with a text-badge fallback).
//   2. Decide whether the user's selected model matches a preset's SOFT
//      `model_hint`, so the card can show an advisory (never blocking) warning.

import deepseekIcon from "./assets/providers/deepseek.svg";
import qwenIcon from "./assets/providers/qwen.svg";
import localIcon from "./assets/providers/local.svg";

// Only the providers we actually ship a local SVG for. Anything else falls back
// to a styled text badge. Icons are rendered on a light chip because some logos
// (Qwen, Local) are near-black and would be invisible on the dark UI.
const PROVIDER_ICONS = {
  deepseek: deepseekIcon,
  qwen: qwenIcon,
  local: localIcon,
};

// Human-readable badge label used when no icon matches.
const PROVIDER_LABELS = {
  deepseek: "DeepSeek",
  qwen: "Qwen",
  local: "Local",
};

// Conservative provider-id normalisation: lowercase, trim, drop spaces/hyphens.
// "deepseek" / "Local" / "qwen" all already normalise to themselves.
export function normalizeProviderId(provider) {
  return String(provider || "")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "");
}

// Local SVG URL for a provider, or null when none ships (→ caller uses a badge).
export function providerIconFor(provider) {
  return PROVIDER_ICONS[normalizeProviderId(provider)] || null;
}

// Display label for the text-badge fallback. Falls back to the raw provider
// string, then "Other", so an unknown provider still renders something sane.
export function providerLabelFor(provider) {
  const id = normalizeProviderId(provider);
  if (PROVIDER_LABELS[id]) return PROVIDER_LABELS[id];
  const raw = String(provider || "").trim();
  return raw || "Other";
}

// Reduce a model name/id to a comparable token: lowercase + strip every
// non-alphanumeric char. "DeepSeek V4 Pro" and "deepseek-v4-pro" both collapse to
// "deepseekv4pro"; "Qwen 3.7 Max" and "qwen3.7-max" both to "qwen37max".
export function normalizeModelToken(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

// Soft compatibility check for a generator preset vs the user's selected model.
//
// Returns `{ warn, hint }`:
//   warn === true  → we are CONFIDENT the selected model does not match the soft
//                    `model_hint` → show an advisory (never blocking) warning.
//   warn === false → no hint, unknown selection, or a confident match → no warning.
//   `hint`         → the preset's `model_hint` (only set when it exists).
//
// `model_hint` is PROSE ("DeepSeek V4 Pro", "Gemma 4 (31B dense preferred)") while
// the selected value is a model id ("deepseek-v4-pro", "gemma-4-…gguf"). We compare
// the alphanumeric-only forms and also accept the cleaner `model` chip string as a
// rescue candidate (e.g. "Gemma 4" → "gemma4" matches "gemma-4-…gguf" where the
// longer prose hint would not). A match counts when either candidate equals, is
// contained in, or contains the selected token. We only ever warn when a
// `model_hint` is present and we are confident there is no match — preferring NO
// warning over a noisy false positive when unsure.
export function presetCompat(preset, selectedModel) {
  if (!preset) return { warn: false };
  const hint = preset.model_hint;
  if (!hint) return { warn: false }; // preset has no soft hint → never warn
  const sel = normalizeModelToken(selectedModel);
  if (!sel) return { warn: false }; // unknown selection → don't warn
  const candidates = [hint, preset.model].map(normalizeModelToken).filter(Boolean);
  const matched = candidates.some(
    (cand) => sel === cand || sel.includes(cand) || cand.includes(sel)
  );
  return { warn: !matched, hint };
}
