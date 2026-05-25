// Shared helpers for resolving a job's prompt_name id into a human-readable
// style name + source (built-in vs custom). The authoritative data comes from
// GET /api/styles; the static map below is a fallback for offline/first paint
// and, crucially, defines the stable set of built-in ids used to classify a
// style as built-in vs custom (including styles that were later deleted).

export const BUILTIN_STYLE_NAMES = {
  basic_study_guide: "Basic Study Guide",
  baby_steps: "Baby Steps",
  exam_cram: "Exam Cram",
  mcq_training: "MCQ Training",
  final_solution: "Final Solutions",
  claude_study_guide: "Editorial",
  master_longform: "Master Longform"
};

export function isBuiltinStyleId(promptName) {
  return Object.prototype.hasOwnProperty.call(BUILTIN_STYLE_NAMES, promptName);
}

// Build an id -> { name, source } map from a GET /api/styles response.
export function buildStyleLookup(stylesResponse) {
  const lookup = {};
  const add = (list, source) => {
    (list ?? []).forEach((style) => {
      if (style?.id) {
        lookup[style.id] = { name: style.name || style.id, source };
      }
    });
  };
  if (stylesResponse) {
    add(stylesResponse.builtin, "builtin");
    add(stylesResponse.custom, "custom");
  }
  return lookup;
}

// Resolve a prompt_name id into { id, name, source, isCustom }.
// Returns null for an empty id (e.g. the markdown/paste pipeline jobs).
export function resolveStyle(promptName, lookup) {
  if (!promptName) {
    return null;
  }
  const builtin = isBuiltinStyleId(promptName);
  const hit = lookup?.[promptName];
  const name = hit?.name || BUILTIN_STYLE_NAMES[promptName] || promptName;
  return {
    id: promptName,
    name,
    source: builtin ? "builtin" : "custom",
    isCustom: !builtin
  };
}
