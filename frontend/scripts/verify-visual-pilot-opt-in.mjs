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
