// Slice 55: pure, React-free helpers for the Builder's per-job opt-in to the
// off-by-default visual markdown image pilot. Kept in a plain module so a node
// harness (scripts/verify-visual-pilot-opt-in.mjs) can assert payload + toggle
// behaviour without a DOM.
//
// IMPORTANT: these helpers only shape the OPTIONAL per-job request boolean and the
// toggle's effective state. They are NOT the security gate. Insertion still
// requires the backend global env master switch
// (GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT) AND the per-job opt-in, both
// re-checked server-side. A request can never bypass the master switch from here.

// The single request field the opt-in adds (snake_case to match the backend
// LLMJobRequest / multipart field name).
export const VISUAL_PILOT_PAYLOAD_KEY = "enable_visual_references";

// The toggle is only "effectively on" when the server advertises the capability
// (the global master switch is on) AND the user has requested it. Mirrors the
// disabled-toggle UX: with the capability off the control is forced visually off.
export function isVisualPilotEffectivelyOn({ capabilityEnabled, requested } = {}) {
  return Boolean(capabilityEnabled) && Boolean(requested);
}

// Whether the per-job opt-in toggle should be interactive. Off (disabled) unless
// the server capability is present.
export function isVisualPilotToggleEnabled(capabilityEnabled) {
  return Boolean(capabilityEnabled);
}

// Extra LLM-payload fields contributed by the opt-in: present ONLY when opted in,
// so a default / opted-out request stays byte-equivalent to before this slice.
// Non-boolean / falsy inputs contribute nothing (never sends `false`).
export function visualPilotPayloadFields(enableVisualReferences) {
  return enableVisualReferences === true ? { [VISUAL_PILOT_PAYLOAD_KEY]: true } : {};
}
