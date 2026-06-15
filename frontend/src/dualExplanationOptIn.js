// Slice 99: pure, React-free helpers for the Builder's per-job opt-in to
// "Explain like I'm 10 / Exam answer" dual explanation mode. Kept in a plain
// module so a node harness (scripts/verify-dual-explanation-mode-ui.mjs) can
// assert payload + label behaviour without a DOM.
//
// Unlike the visual pilot, this option has NO server-capability gate: it only
// asks the guide generator to add two short, source-grounded companion blocks
// ("Explain it simply" + "Exam answer") for difficult / exam-important concepts.
// It never sends source text, a filename, or a path — only the optional boolean.

// The single request field the opt-in adds (snake_case to match the backend
// LLMJobRequest / multipart field name).
export const DUAL_EXPLANATION_PAYLOAD_KEY = "dual_explanation_mode";

// User-facing copy (fixed, safe strings — never a path/token/source value).
export const DUAL_EXPLANATION_LABEL = "Explain difficult concepts two ways";
export const DUAL_EXPLANATION_HELPER =
  'Adds "Explain it simply" and "Exam answer" blocks for difficult or exam-important concepts.';

// Extra LLM-payload fields contributed by the opt-in: present ONLY when opted in,
// so a default / opted-out request stays byte-equivalent to before this slice.
// Non-boolean / falsy inputs contribute nothing (never sends `false`), matching
// the visual-pilot convention.
export function dualExplanationPayloadFields(dualExplanationMode) {
  return dualExplanationMode === true ? { [DUAL_EXPLANATION_PAYLOAD_KEY]: true } : {};
}
