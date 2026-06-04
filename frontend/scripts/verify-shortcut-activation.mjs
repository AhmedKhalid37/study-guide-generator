// Unit harness for the shortcut activation decision (degraded-activation slice).
//
// Mirrors verify-shortcut-status.mjs (plain node, no test runner, no new
// dependency). Imports the REAL src/shortcutStatus.js — pure ESM, no React/JSX.
// Run:
//
//   node scripts/verify-shortcut-activation.mjs
//
// Proves the pure gating that the Home activation flow relies on:
//   - valid shortcut launches immediately (no prompt)
//   - degraded-yet-launchable shortcut asks for confirmation instead of launching
//   - broken shortcut is blocked (never auto-launches)
//   - legacy `valid === false` always blocks, even if validity.status disagrees
//   - missing `validity` falls back to the legacy boolean (old payloads)

import {
  activationDecision,
  ACTIVATE_BLOCKED,
  ACTIVATE_CONFIRM,
  ACTIVATE_LAUNCH,
} from "../src/shortcutStatus.js";

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

// ── valid → launch immediately ───────────────────────────────────────────────
check(
  "valid shortcut launches",
  activationDecision({ valid: true, validity: { status: "valid", findings: [] } }) === ACTIVATE_LAUNCH
);
check(
  "no validity + valid:true launches (old payload)",
  activationDecision({ valid: true }) === ACTIVATE_LAUNCH
);
check(
  "no validity + valid absent launches (old payload)",
  activationDecision({}) === ACTIVATE_LAUNCH
);

// ── degraded (still launchable) → confirm ────────────────────────────────────
check(
  "degraded + valid:true asks for confirmation",
  activationDecision({ valid: true, validity: { status: "degraded", findings: [{ severity: "warning" }] } }) ===
    ACTIVATE_CONFIRM
);

// ── broken → blocked ─────────────────────────────────────────────────────────
check(
  "broken status blocks launch",
  activationDecision({ valid: false, validity: { status: "broken", findings: [{ severity: "error" }] } }) ===
    ACTIVATE_BLOCKED
);
check(
  "no validity + valid:false blocks (old payload)",
  activationDecision({ valid: false }) === ACTIVATE_BLOCKED
);

// ── legacy guard wins over a disagreeing validity.status ─────────────────────
check(
  "valid:false blocks even if validity.status says degraded",
  activationDecision({ valid: false, validity: { status: "degraded" } }) === ACTIVATE_BLOCKED
);
check(
  "validity.status broken blocks even if legacy valid:true",
  activationDecision({ valid: true, validity: { status: "broken" } }) === ACTIVATE_BLOCKED
);

// ── robustness ───────────────────────────────────────────────────────────────
check("undefined shortcut launches (no crash)", activationDecision(undefined) === ACTIVATE_LAUNCH);

if (failed) {
  console.error(`\n${failed} shortcut-activation check(s) failed.`);
  process.exit(1);
}
console.log("\nAll shortcut-activation checks passed.");
