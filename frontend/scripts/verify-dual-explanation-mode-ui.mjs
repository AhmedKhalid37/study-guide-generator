// Plain-node harness for the Builder's "Explain like I'm 10 / Exam answer" dual
// explanation mode opt-in (Slice 99).
//
// Run:
//
//   node scripts/verify-dual-explanation-mode-ui.mjs
//
// Exercises the pure opt-in helper (src/dualExplanationOptIn.js) the Builder uses
// to shape the optional `dual_explanation_mode` request field, and statically
// asserts the BuilderWorkspace wiring. Asserts: the field is sent ONLY when opted
// in (default request unchanged), default is off, the exact safe field name +
// label/helper copy, that the option payload does NOT touch `page_selections` or
// `material_page_selections`, determinism on repeat, and that no path / token /
// URL / data-URI / base64 / source content can ride out through the helper.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import {
  DUAL_EXPLANATION_PAYLOAD_KEY,
  DUAL_EXPLANATION_LABEL,
  DUAL_EXPLANATION_HELPER,
  dualExplanationPayloadFields
} from "../src/dualExplanationOptIn.js";

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

// ---- exact, safe field name + copy -----------------------------------------
check("payload key is exact snake_case", DUAL_EXPLANATION_PAYLOAD_KEY === "dual_explanation_mode");
check("label copy present", DUAL_EXPLANATION_LABEL === "Explain difficult concepts two ways");
check(
  "helper copy present + mentions both modes",
  DUAL_EXPLANATION_HELPER.includes("Explain it simply") && DUAL_EXPLANATION_HELPER.includes("Exam answer")
);

// ---- payload fields: present ONLY when opted in (default off) ---------------
check("default (false) sends no field", JSON.stringify(dualExplanationPayloadFields(false)) === "{}");
check("undefined sends no field", JSON.stringify(dualExplanationPayloadFields(undefined)) === "{}");
check("null sends no field", JSON.stringify(dualExplanationPayloadFields(null)) === "{}");
// Never serialise an explicit `false`; only ever add `true`.
check(
  "opted-in sends exactly { dual_explanation_mode: true }",
  JSON.stringify(dualExplanationPayloadFields(true)) === JSON.stringify({ dual_explanation_mode: true })
);
// Non-boolean truthy inputs do NOT smuggle a value through (strict true only).
check("truthy non-true string sends no field", JSON.stringify(dualExplanationPayloadFields("yes")) === "{}");
check("number 1 sends no field", JSON.stringify(dualExplanationPayloadFields(1)) === "{}");

// ---- determinism -----------------------------------------------------------
check(
  "deterministic on repeat (true)",
  JSON.stringify(dualExplanationPayloadFields(true)) === JSON.stringify(dualExplanationPayloadFields(true))
);
check(
  "deterministic on repeat (false)",
  JSON.stringify(dualExplanationPayloadFields(false)) === JSON.stringify(dualExplanationPayloadFields(false))
);

// ---- the field never carries any sensitive / source content ----------------
const serialized = JSON.stringify({ ...dualExplanationPayloadFields(true) });
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
// The payload contributes EXACTLY one key and never the page-selection fields.
const keys = Object.keys(dualExplanationPayloadFields(true));
check("payload has exactly one key", keys.length === 1);
check("payload does not carry page_selections", !keys.includes("page_selections"));
check("payload does not carry material_page_selections", !keys.includes("material_page_selections"));
check("disabled payload is empty (touches nothing)", Object.keys(dualExplanationPayloadFields(false)).length === 0);

// ---- static wiring assertions over BuilderWorkspace.jsx --------------------
const here = dirname(fileURLToPath(import.meta.url));
const jsx = readFileSync(join(here, "..", "src", "components", "BuilderWorkspace.jsx"), "utf8");
check("BuilderWorkspace imports the dual-explanation helper", jsx.includes('from "../dualExplanationOptIn"'));
check("BuilderWorkspace has dualExplanationMode state", jsx.includes("const [dualExplanationMode, setDualExplanationMode]"));
check("BuilderWorkspace defaults state to false", jsx.includes("useState(false);"));
check("BuilderWorkspace renders the toggle with the label", jsx.includes("DUAL_EXPLANATION_LABEL"));
check("BuilderWorkspace renders the helper copy", jsx.includes("DUAL_EXPLANATION_HELPER"));
check("BuilderWorkspace spreads dualExplanationPayloadFields", jsx.includes("dualExplanationPayloadFields(dualExplanationMode)"));
// The dual-explanation wiring must NOT alter the page-selection payload spreads.
check("page_selections payload spread preserved", jsx.includes("page_selections: pageSelections }"));
check("material_page_selections payload spread preserved", jsx.includes("material_page_selections: materialPageSelections }"));

if (failed) {
  console.error(`\n${failed} check(s) failed`);
  process.exit(1);
}
console.log("\nAll dual-explanation mode UI checks passed.");
