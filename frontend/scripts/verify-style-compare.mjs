// Unit harness for the Styles "Compare styles" pure helpers (Slice 14).
// Mirrors the existing verify-*.mjs pattern (plain node, no test runner, no new
// dependency). Imports the REAL src/styleCompare.js — pure ESM, no React/JSX.
// Run:
//
//   node scripts/verify-style-compare.mjs
//
// Proves:
//   * toggleCompareSelection adds/removes, never mutates, caps at MAX, and still
//     allows removal at capacity.
//   * stylePromptStats returns deterministic char/word/heading counts and the
//     math/quiz/concise guidance flags, with no LLM/semantic analysis.

import {
  MIN_COMPARE_STYLES,
  MAX_COMPARE_STYLES,
  toggleCompareSelection,
  stylePromptStats,
} from "../src/styleCompare.js";

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

// ── selection limits ─────────────────────────────────────────────────────────
check("MIN/MAX are 2/4", MIN_COMPARE_STYLES === 2 && MAX_COMPARE_STYLES === 4);

const base = ["a", "b"];
const added = toggleCompareSelection(base, "c");
check("adds a new id", added.join(",") === "a,b,c");
check("does not mutate input on add", base.join(",") === "a,b");

const removed = toggleCompareSelection(["a", "b", "c"], "b");
check("removes an existing id", removed.join(",") === "a,c");

const full = ["a", "b", "c", "d"];
check("ignores add at capacity (4)", toggleCompareSelection(full, "e").join(",") === "a,b,c,d");
check("still removes at capacity", toggleCompareSelection(full, "c").join(",") === "a,b,d");
check("handles non-array input", toggleCompareSelection(null, "a").join(",") === "a");

// ── prompt stats ─────────────────────────────────────────────────────────────
const empty = stylePromptStats("");
check("empty content -> zero counts", empty.charCount === 0 && empty.wordCount === 0 && empty.headingCount === 0);
check("empty content -> all flags false", !empty.hasMath && !empty.hasQuiz && !empty.hasConcise);
check("undefined content is safe", stylePromptStats(undefined).wordCount === 0);

const sample = [
  "# Study Guide",
  "## Key Formulas",
  "Write equations clearly using $x^2$ and LaTeX.",
  "Then build multiple-choice questions (MCQ) for recall.",
  "Keep it a concise one-page cheat sheet.",
].join("\n");
const stats = stylePromptStats(sample);
check("counts characters", stats.charCount === sample.length, String(stats.charCount));
check("counts words", stats.wordCount === sample.trim().split(/\s+/).length, String(stats.wordCount));
check("counts 2 ATX headings", stats.headingCount === 2, String(stats.headingCount));
check("detects math guidance", stats.hasMath === true);
check("detects quiz/MCQ guidance", stats.hasQuiz === true);
check("detects concise/cram wording", stats.hasConcise === true);

// A plain narrative prompt with no special guidance.
const plain = stylePromptStats("Write a friendly narrative chapter. Explain ideas in plain prose.");
check("narrative prompt -> no math flag", plain.hasMath === false);
check("narrative prompt -> no quiz flag", plain.hasQuiz === false);
check("narrative prompt -> no concise flag", plain.hasConcise === false);

// '#' that is not a heading (no following space/content) must not be counted.
check("ignores non-heading '#'", stylePromptStats("color #fff is nice\n#notabullet").headingCount === 0);

if (failed) {
  console.error(`\n${failed} style-compare check(s) failed.`);
  process.exit(1);
}
console.log("\nAll style-compare checks passed.");
