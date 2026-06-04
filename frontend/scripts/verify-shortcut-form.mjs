// Unit harness for the Shortcut Edit modal / "Save as shortcut" helpers
// (generator-preset source fix + opt-in saved prompt). Mirrors the existing
// verify-shortcut-*.mjs pattern (plain node, no test runner, no new dependency).
// Imports the REAL src/shortcutMeta.js — pure ESM with no React/JSX. Run:
//
//   node scripts/verify-shortcut-form.mjs
//
// Proves:
//   * generatorPresetOptions sources the CANONICAL generator presets (None +
//     Claude-Exam/Review/Cram), never outline quick-templates; saves canonical
//     ids; clearing -> "" ; a legacy/invalid stored id loads as a trailing
//     "unavailable" option without crashing or being rewritten.
//   * opt-in saved prompt: default off omits saved_prompt; on attaches the typed
//     source text; clamps to the size limit; never mutates the input payload.

import {
  generatorPresetOptions,
  withSavedPrompt,
  clampSavedPrompt,
  payloadHasSavedPrompt,
  MAX_SAVED_PROMPT_CHARS,
} from "../src/shortcutMeta.js";

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

// The canonical /api/options.generator_presets shape (metadata only, no bodies).
const CANONICAL = [
  { id: "claude_exam", name: "Claude-Exam" },
  { id: "claude_review", name: "Claude-Review" },
  { id: "claude_cram", name: "Claude-Cram" },
];
// The WRONG source the bug used (/api/presets = outline quick-templates).
const OUTLINE_TEMPLATES = [
  { id: "exam_guide", name: "Exam Cram" },
  { id: "report_guide", name: "Academic Report" },
  { id: "presentation", name: "Presentation" },
  { id: "chapter_summary", name: "Chapter Summary" },
  { id: "final_revision", name: "Final Revision" },
];

// ── generator preset dropdown source ─────────────────────────────────────────
const opts = generatorPresetOptions(CANONICAL, "");
check("dropdown leads with None (empty id)", opts[0].id === "" && opts[0].label === "None");
check(
  "dropdown shows the real generator presets",
  opts.map((o) => o.label).join(",") === "None,Claude-Exam,Claude-Review,Claude-Cram",
  opts.map((o) => o.label).join(",")
);
check(
  "dropdown uses canonical ids (claude_exam/review/cram)",
  opts.slice(1).map((o) => o.id).join(",") === "claude_exam,claude_review,claude_cram"
);
check(
  "dropdown does NOT contain outline-template labels",
  !opts.some((o) => ["Exam Cram", "Academic Report", "Presentation", "Chapter Summary", "Final Revision"].includes(o.label))
);

// Selecting "None" clears the value (empty id, not a sentinel).
check("None option clears generator_preset to ''", generatorPresetOptions(CANONICAL).find((o) => o.label === "None").id === "");

// A legacy/invalid stored id (incl. an outline-template id mis-saved by the bug)
// loads safely as a trailing deprecated option — not silently dropped/rewritten.
const legacy = generatorPresetOptions(CANONICAL, "exam_guide");
const last = legacy[legacy.length - 1];
check("legacy/invalid id appended as trailing option", last.id === "exam_guide", JSON.stringify(last));
check("legacy/invalid id is marked deprecated/unavailable", last.deprecated === true && /unavailable/.test(last.label));
check("legacy id does not duplicate a real preset", generatorPresetOptions(CANONICAL, "claude_exam").length === opts.length);
check("empty/whitespace current adds no extra option", generatorPresetOptions(CANONICAL, "   ").length === opts.length);
check("does not crash on non-array presets", generatorPresetOptions(null, "claude_exam")[0].id === "");

// ── opt-in saved prompt ──────────────────────────────────────────────────────
const base = { provider: "deepseek", generator_preset: "claude_exam" };

// Default / unchecked -> payload omits saved_prompt.
const off = withSavedPrompt(base, { savePrompt: false, sourceText: "private notes" });
check("checkbox OFF omits saved_prompt", !("saved_prompt" in off), JSON.stringify(off));
check("withSavedPrompt default is off", !("saved_prompt" in withSavedPrompt(base)));

// Checked -> payload includes the typed source text verbatim.
const on = withSavedPrompt(base, { savePrompt: true, sourceText: "Photosynthesis notes" });
check("checkbox ON includes saved_prompt", on.saved_prompt === "Photosynthesis notes");
check("withSavedPrompt does not mutate input", !("saved_prompt" in base));

// Checked but no text -> nothing saved (no silent empty key).
check("ON with blank text saves nothing", !("saved_prompt" in withSavedPrompt(base, { savePrompt: true, sourceText: "   " })));

// Editing: an inherited saved_prompt is stripped when the box is turned off.
const inherited = { ...base, saved_prompt: "old content" };
check("OFF strips an inherited saved_prompt", !("saved_prompt" in withSavedPrompt(inherited, { savePrompt: false })));

// Size clamp.
const huge = "x".repeat(MAX_SAVED_PROMPT_CHARS + 50);
check("clampSavedPrompt caps at the limit", clampSavedPrompt(huge).length === MAX_SAVED_PROMPT_CHARS);
check("withSavedPrompt clamps oversized text", withSavedPrompt(base, { savePrompt: true, sourceText: huge }).saved_prompt.length === MAX_SAVED_PROMPT_CHARS);
check("clampSavedPrompt('' ) -> ''", clampSavedPrompt("   ") === "");
check("clampSavedPrompt(non-string) -> ''", clampSavedPrompt(undefined) === "");

// Indicator helper.
check("payloadHasSavedPrompt true when present", payloadHasSavedPrompt({ saved_prompt: "hi" }) === true);
check("payloadHasSavedPrompt false when absent", payloadHasSavedPrompt(base) === false);
check("payloadHasSavedPrompt false on blank", payloadHasSavedPrompt({ saved_prompt: "  " }) === false);

if (failed) {
  console.error(`\n${failed} shortcut-form check(s) failed.`);
  process.exit(1);
}
console.log("\nAll shortcut-form checks passed.");
