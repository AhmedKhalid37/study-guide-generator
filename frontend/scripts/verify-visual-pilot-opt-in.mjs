// Plain-node harness for the Builder's per-job visual markdown image pilot opt-in
// (Slice 55).
//
// Run:
//
//   node scripts/verify-visual-pilot-opt-in.mjs
//
// Exercises the pure opt-in helpers (src/visualPilotOptIn.js) that the Builder uses
// to (a) shape the optional `enable_visual_references` request field and (b) drive
// the toggle's checked/disabled state from the server capability. Asserts: the
// payload field is sent ONLY when opted in (default request unchanged), the toggle
// is forced off + disabled when the server capability is absent, a job opt-in can
// never make the request carry the field while the capability is off in a way that
// would matter (capability gates the effective state), the exact safe field name /
// label, and that NO raw path / token / URL / data-URI / base64 / image-byte
// content can ride out through any helper.

import {
  VISUAL_PILOT_PAYLOAD_KEY,
  isVisualPilotEffectivelyOn,
  isVisualPilotToggleEnabled,
  isVisualReferencesReady,
  visualPilotReadinessNote,
  visualPilotPayloadFields
} from "../src/visualPilotOptIn.js";

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

// ---- exact, safe field name ------------------------------------------------
check("payload key is exact snake_case", VISUAL_PILOT_PAYLOAD_KEY === "enable_visual_references");

// ---- payload fields: present ONLY when opted in ----------------------------
check("default (false) sends no field", JSON.stringify(visualPilotPayloadFields(false)) === "{}");
check("undefined sends no field", JSON.stringify(visualPilotPayloadFields(undefined)) === "{}");
check("null sends no field", JSON.stringify(visualPilotPayloadFields(null)) === "{}");
// Never serialise an explicit `false`; only ever add `true`.
check(
  "opted-in sends exactly { enable_visual_references: true }",
  JSON.stringify(visualPilotPayloadFields(true)) === JSON.stringify({ enable_visual_references: true })
);
// Non-boolean truthy inputs do NOT smuggle a value through (strict true only).
check("truthy non-true string sends no field", JSON.stringify(visualPilotPayloadFields("yes")) === "{}");
check("number 1 sends no field", JSON.stringify(visualPilotPayloadFields(1)) === "{}");

// ---- toggle effective state ------------------------------------------------
// Default: capability unknown/off and nothing requested ⇒ off.
check("effective off by default", isVisualPilotEffectivelyOn({}) === false);
check("requested but capability off ⇒ off", isVisualPilotEffectivelyOn({ capabilityEnabled: false, requested: true }) === false);
check("capability on but not requested ⇒ off", isVisualPilotEffectivelyOn({ capabilityEnabled: true, requested: false }) === false);
check("capability on AND requested ⇒ on", isVisualPilotEffectivelyOn({ capabilityEnabled: true, requested: true }) === true);

// ---- toggle enabled (interactive) state ------------------------------------
check("toggle disabled when capability off", isVisualPilotToggleEnabled(false) === false);
check("toggle disabled when capability undefined", isVisualPilotToggleEnabled(undefined) === false);
check("toggle enabled when capability on", isVisualPilotToggleEnabled(true) === true);

// ---- Slice 57: readiness truth table (master flag AND local figure extraction)
// Derived from /api/options.capabilities. Trust the backend's derived
// visual_references_ready when present; else AND the two component booleans.
check("ready false: master off + figure off",
  isVisualReferencesReady({ visual_markdown_image_pilot: false, local_figure_extraction: false, visual_references_ready: false }) === false);
check("ready false: master on + figure off",
  isVisualReferencesReady({ visual_markdown_image_pilot: true, local_figure_extraction: false, visual_references_ready: false }) === false);
check("ready false: master off + figure on",
  isVisualReferencesReady({ visual_markdown_image_pilot: false, local_figure_extraction: true, visual_references_ready: false }) === false);
check("ready true: master on + figure on",
  isVisualReferencesReady({ visual_markdown_image_pilot: true, local_figure_extraction: true, visual_references_ready: true }) === true);
// Missing/empty capabilities ⇒ not ready (safe default).
check("ready false: undefined capabilities", isVisualReferencesReady(undefined) === false);
check("ready false: empty capabilities", isVisualReferencesReady({}) === false);
// Fallback AND when the derived flag is absent (older/partial payload).
check("ready true via fallback AND when derived flag absent",
  isVisualReferencesReady({ visual_markdown_image_pilot: true, local_figure_extraction: true }) === true);
check("ready false via fallback when one component absent",
  isVisualReferencesReady({ visual_markdown_image_pilot: true }) === false);

// ---- Slice 57: calm readiness note (which server switch is missing) ---------
check("note empty when ready",
  visualPilotReadinessNote({ visual_markdown_image_pilot: true, local_figure_extraction: true, visual_references_ready: true }) === "");
check("note: master off message is calm + safe",
  visualPilotReadinessNote({ visual_markdown_image_pilot: false, local_figure_extraction: false, visual_references_ready: false })
    === "Visual references are not enabled on this server.");
check("note: master on + figure off message is calm + safe",
  visualPilotReadinessNote({ visual_markdown_image_pilot: true, local_figure_extraction: false, visual_references_ready: false })
    === "Visual references need local figure extraction to be enabled on this server.");
check("note: undefined capabilities ⇒ master-off message",
  visualPilotReadinessNote(undefined) === "Visual references are not enabled on this server.");
// The notes are fixed safe copy: no path / env name / token / url / data-uri.
const NOTE_LEAKS = [
  ["path", /(\/home\/|\/usr\/|\/etc\/|\/var\/|\/root\/|\/tmp\/|\/opt\/|C:\\)/],
  ["env name", /GUIDEFORGE_[A-Z_]+/],
  ["url", /https?:\/\/|file:\/\/|ftp:\/\//],
  ["token", /(sk-|sk_|pk-|rk_)[A-Za-z0-9_-]{8,}/],
  ["datauri", /data:[^;]+;base64,/]
];
for (const caps of [undefined, {}, { visual_markdown_image_pilot: true, local_figure_extraction: false }]) {
  const note = visualPilotReadinessNote(caps);
  for (const [label, re] of NOTE_LEAKS) {
    check(`note has no ${label}`, !re.test(note), note);
  }
}

// ---- the field never carries any sensitive content -------------------------
// The opt-in only ever contributes the single boolean true; assert the serialised
// payload contains no path/url/token/data-uri/base64/image-byte shapes.
const serialized = JSON.stringify({
  ...visualPilotPayloadFields(true)
});
const LEAKS = [
  ["path", /(\/home\/|\/usr\/|\/etc\/|\/var\/|\/root\/|\/tmp\/|\/opt\/|C:\\)/],
  ["url", /https?:\/\/|file:\/\/|ftp:\/\//],
  ["token", /(sk-|sk_|pk-|rk_)[A-Za-z0-9_-]{8,}/],
  ["datauri", /data:[^;]+;base64,/],
  ["socket", /\.sock\b/],
  ["gguf", /\.gguf\b|mmproj/i]
];
for (const [label, re] of LEAKS) {
  check(`payload has no ${label}`, !re.test(serialized), serialized);
}

if (failed) {
  console.error(`\n${failed} check(s) failed`);
  process.exit(1);
}
console.log("\nAll visual-pilot opt-in checks passed.");
