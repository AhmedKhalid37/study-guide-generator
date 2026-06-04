// Shared metadata + mapping helpers for Home shortcuts (Slice 2B).
//
// The backend shortcut store (Slice 2A) is the single source of truth for what a
// shortcut may contain; these helpers only translate between the backend payload
// shape and the Builder's in-component state so capture ("Save as shortcut") and
// prefill (clicking a builder_setup card) stay symmetric. Keep the key sets here
// in sync with pipeline/shortcut_store.py — never widen them on the client.

export const SHORTCUT_TYPES = ["builder_setup", "tool", "library_view"];

export const TYPE_LABELS = {
  builder_setup: "Builder setup",
  tool: "Tool",
  library_view: "Library view",
};

// Tool keys the backend recognises (KNOWN_TOOL_KEYS) + friendly labels.
export const TOOL_LABELS = {
  clean_markdown: "Clean Markdown",
  improve_guide: "Improve Guide",
  add_style: "Add a Style",
  compare_styles: "Compare Styles",
  export_center: "Export Center",
  find_guide: "Find a Guide",
  quiz: "Quiz",
  outline: "Outline",
};
export const TOOL_KEYS = Object.keys(TOOL_LABELS);

// Library view bases the backend recognises (KNOWN_VIEW_BASES). The prefixed
// forms (folder:/tag:/search:) are produced from the optional query field.
export const VIEW_BASES = ["recent", "pinned", "favorites", "failed", "all"];
export const VIEW_BASE_LABELS = {
  recent: "Most recent",
  pinned: "Pinned / favorites",
  favorites: "Favorites",
  failed: "Failed jobs",
  all: "All guides",
};

export const INPUT_TYPES = ["generate_llm", "paste_text", "upload_markdown"];
export const INPUT_TYPE_LABELS = {
  generate_llm: "Generate with AI",
  paste_text: "Paste text",
  upload_markdown: "Upload markdown",
};

export const EXPORT_FORMATS = ["pdf", "docx", "markdown", "html"];

// Curated emoji + colour palettes for the customize form. Icons are stored as a
// short string (emoji); colours as hex. Both are validated again server-side.
export const ICON_CHOICES = [
  "📝", "📘", "📗", "📕", "🧹", "✨", "🔎", "⏯️", "⚡", "🎯",
  "🧠", "📐", "📊", "🗂️", "🏆", "🔬", "💡", "🧮", "🚀", "🪄",
];
export const COLOR_CHOICES = [
  "#F59E0B", "#60A5FA", "#A855F7", "#34D399", "#38BDF8",
  "#F472B6", "#F97316", "#F43F5E", "#C084FC", "#22D3EE",
];

// Max chars of opt-in saved prompt/source text a builder_setup shortcut may
// carry. Mirror of pipeline/shortcut_store.py MAX_SAVED_PROMPT_CHARS — keep in
// sync; the backend re-checks and rejects oversized input regardless.
export const MAX_SAVED_PROMPT_CHARS = 100000;

// ── Generator preset options (Shortcut Edit modal) ──────────────────────────
//
// The CANONICAL source is /api/options.generator_presets — the SAME list the
// Builder Style tab renders (None / Claude-Exam / Claude-Review / Claude-Cram).
// It must NEVER be the outline quick-template registry (/api/presets: Exam Cram /
// Academic Report / Presentation / …). Those are Outline templates, a separate
// registry; mixing them was the bug that made shortcuts save outline-template ids
// into payload.generator_preset and get flagged generator_preset_missing.
//
// Always leads with a "None" entry (empty id => clears generator_preset). A
// non-empty `current` value not present in the live list — a legacy/invalid id, or
// an outline-template id mis-saved by the old bug — is appended as a trailing,
// visibly-deprecated option so the modal LOADS it without crashing and WITHOUT
// rewriting it on read. The stored value only changes if the user picks another
// option and explicitly saves.
export function generatorPresetOptions(generatorPresets = [], current = "") {
  const list = Array.isArray(generatorPresets) ? generatorPresets : [];
  const options = [{ id: "", label: "None" }];
  list.forEach((preset) => {
    if (preset && preset.id) options.push({ id: preset.id, label: preset.name || preset.id });
  });
  const cur = (current || "").trim();
  if (cur && !list.some((preset) => preset && preset.id === cur)) {
    options.push({ id: cur, label: `${cur} — unavailable`, deprecated: true });
  }
  return options;
}

// ── Opt-in saved prompt/source text ─────────────────────────────────────────

// Clamp opt-in saved prompt text to the shared size limit. Returns "" for
// non-strings / blank so callers treat "nothing to save" uniformly.
export function clampSavedPrompt(text) {
  if (typeof text !== "string" || !text.trim()) return "";
  return text.length > MAX_SAVED_PROMPT_CHARS ? text.slice(0, MAX_SAVED_PROMPT_CHARS) : text;
}

// Apply the opt-in saved-prompt decision to a builder_setup payload. `savePrompt`
// off (the default) REMOVES the key entirely — prompt text is never saved
// silently. On => the clamped, non-empty source text is attached under
// `saved_prompt`. Returns a NEW object; never mutates the input.
export function withSavedPrompt(payload, { savePrompt = false, sourceText = "" } = {}) {
  const next = { ...(payload || {}) };
  delete next.saved_prompt;
  if (savePrompt) {
    const clamped = clampSavedPrompt(sourceText);
    if (clamped) next.saved_prompt = clamped;
  }
  return next;
}

// True when a payload carries non-empty opt-in saved prompt text.
export function payloadHasSavedPrompt(payload) {
  return Boolean(payload && typeof payload.saved_prompt === "string" && payload.saved_prompt.trim());
}

// ── Builder <-> shortcut payload mapping ────────────────────────────────────

export const SOURCE_TO_INPUT = {
  llm: "generate_llm",
  paste: "paste_text",
  upload: "upload_markdown",
};
export const INPUT_TO_SOURCE = {
  generate_llm: "llm",
  paste_text: "paste",
  upload_markdown: "upload",
};

// Builder uses a coarse short/medium/long length; the shortcut payload stores a
// numeric target_pages. Map between them so a captured setup round-trips.
export function lengthToPages(length) {
  if (length === "short") return 10;
  if (length === "long") return 30;
  return 20;
}
export function pagesToLength(pages) {
  const n = Number(pages) || 0;
  if (n && n <= 12) return "short";
  if (n && n <= 24) return "medium";
  if (n) return "long";
  return "medium";
}

// Reduce a Builder `include_sections` dict (canonical key → bool) to a clean dict
// of only the enabled keys → true, dropping false/empty entries. The backend
// shortcut store re-validates/normalizes against the canonical key set, so this
// only needs to strip the obvious noise.
function cleanSections(includeSections = {}) {
  const next = {};
  if (includeSections && typeof includeSections === "object") {
    Object.entries(includeSections).forEach(([key, on]) => {
      if (on) next[key] = true;
    });
  }
  return next;
}

// Capture: turn live Builder state into a builder_setup payload (the inverse of
// applyBuilderPrefill in BuilderWorkspace). Kept here so capture + prefill share
// one definition of the mapping. The generation-affecting options use the
// CANONICAL backend fields (`include_sections` + the C1/C2 axes) — not the old
// shortcut-only `modules` state, which never reached prompt assembly.
export function builderStateToPayload({
  source,
  provider,
  model,
  generatorPreset,
  style,
  length,
  includeSections = {},
  outputDepth = "",
  difficulty = "",
  strictMath,
  exportFormats = ["pdf"],
  mode = "study_guide",
}) {
  return {
    input_type: SOURCE_TO_INPUT[source] || "generate_llm",
    provider: provider || null,
    model: model || null,
    generator_preset: generatorPreset || null,
    style: style || null,
    mode: mode || "study_guide",
    target_pages: lengthToPages(length),
    include_sections: cleanSections(includeSections),
    output_depth: outputDepth || null,
    difficulty: difficulty || null,
    strict_math: strictMath !== false,
    export_formats: Array.isArray(exportFormats) && exportFormats.length ? exportFormats : ["pdf"],
  };
}

// A compact human summary of a payload, for previews and card descriptions.
export function summarizePayload(shortcut) {
  if (!shortcut) return "";
  const { type, payload = {} } = shortcut;
  if (type === "tool") {
    return TOOL_LABELS[payload.tool] || payload.tool || "Unknown tool";
  }
  if (type === "library_view") {
    const view = payload.view || "";
    if (view.startsWith("search:")) return `Search "${view.slice(7) || "…"}"`;
    if (view.startsWith("folder:")) return `Folder ${view.slice(7)}`;
    if (view.startsWith("tag:")) return `Tag ${view.slice(4)}`;
    return VIEW_BASE_LABELS[view] || view || "Library";
  }
  // builder_setup
  const parts = [];
  if (payload.input_type) parts.push(INPUT_TYPE_LABELS[payload.input_type] || payload.input_type);
  if (payload.provider) parts.push(payload.provider);
  if (payload.generator_preset) parts.push(payload.generator_preset);
  if (payload.style) parts.push(payload.style);
  return parts.join(" · ") || "Builder setup";
}
