// Pure helpers for the Local Models command helper (LMM Slice 4).
//
// These normalize the static command-profile DTO from the backend
// (GET /api/local-model/command-profile —
// pipeline/provider_config.get_local_model_command_profiles) into a small, stable
// shape the UI renders as a copyable "Copy llama-server command" block. They are
// PURE functions (no React, no imports) so a node harness can unit-test them.
//
// HARD INVARIANT: this is a DISPLAY helper only. Nothing here (or in the panel that
// consumes it) executes, spawns, or starts anything — it only SHAPES a string the
// user copies and runs themselves. The command always carries a model PLACEHOLDER
// (never a real host path) and the backend never embeds a raw key or full URL; this
// layer only passes those already-safe fields through and tolerates missing/garbage
// data without throwing.

export const COPY_IDLE = "idle";
export const COPY_COPIED = "copied";
export const COPY_FAILED = "failed";

// Normalize one raw profile object into a render-safe shape, or null if unusable.
// `command` must be a non-empty string for the profile to be considered usable.
export function normalizeProfile(raw) {
  if (!raw || typeof raw !== "object") return null;
  const id = typeof raw.id === "string" ? raw.id : "";
  const command = typeof raw.command === "string" ? raw.command : "";
  if (!command.trim()) return null;
  return {
    id,
    label: typeof raw.label === "string" && raw.label ? raw.label : id || "Command",
    description: typeof raw.description === "string" ? raw.description : "",
    command,
    argv: Array.isArray(raw.argv) ? raw.argv.filter((t) => typeof t === "string") : [],
    placeholders:
      raw.placeholders && typeof raw.placeholders === "object" ? raw.placeholders : {},
    warnings: Array.isArray(raw.warnings)
      ? raw.warnings.filter((w) => typeof w === "string" && w)
      : [],
  };
}

// All usable profiles from the DTO (drops malformed / command-less entries).
export function commandProfiles(data) {
  const list = data?.profiles;
  if (!Array.isArray(list)) return [];
  return list.map(normalizeProfile).filter(Boolean);
}

// The recommended default profile: the DTO's `profile`, else the first usable one
// from `profiles`, else null. Always normalized (or null).
export function defaultProfile(data) {
  const direct = normalizeProfile(data?.profile);
  if (direct) return direct;
  const list = commandProfiles(data);
  return list.length ? list[0] : null;
}

// Resolve a profile by id, falling back to the default. Used to honour a UI
// selection without trusting the index position.
export function profileById(data, id) {
  if (typeof id === "string" && id) {
    const match = commandProfiles(data).find((p) => p.id === id);
    if (match) return match;
  }
  return defaultProfile(data);
}

// Whether a usable command exists to copy. The copy button is enabled ONLY when
// this is true — missing / garbage data disables the affordance gracefully.
export function commandAvailable(profile) {
  return !!(profile && typeof profile.command === "string" && profile.command.trim().length > 0);
}

// Stable label for the copy button across its idle / copied / failed states. The
// failed label doubles as the manual-copy fallback instruction.
export function copyButtonLabel(state) {
  if (state === COPY_COPIED) return "Copied";
  if (state === COPY_FAILED) return "Copy failed — select the text and copy manually";
  return "Copy command";
}

// Top-level helper notes (e.g. the Docker base-URL hint), tolerating missing data.
export function commandNotes(data) {
  const list = data?.notes;
  return Array.isArray(list) ? list.filter((n) => typeof n === "string" && n) : [];
}
