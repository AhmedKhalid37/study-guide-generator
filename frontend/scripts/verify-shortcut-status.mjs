// Unit harness for the read-only Shortcut Inspector status helpers (Slice 2).
//
// Mirrors the existing verify-assets.mjs pattern (plain node, no test runner, no
// new dependency). Imports the REAL src/shortcutStatus.js — it is pure ESM with
// no React/JSX, so node can load it directly. Run:
//
//   node scripts/verify-shortcut-status.mjs
//
// Proves: status normalization across the 3 tiers, fallback for OLD shortcut
// payloads with no `validity`, finding-count helpers, and badge label mapping.

import {
  countFindingsBySeverity,
  issueCount,
  shortcutBadge,
  shortcutFindings,
  shortcutStatus,
  statusBadge,
  STATUS_BROKEN,
  STATUS_DEGRADED,
  STATUS_VALID,
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

// ── status normalization (prefers validity.status) ───────────────────────────
check(
  "validity.status valid -> valid",
  shortcutStatus({ valid: true, validity: { status: "valid", findings: [] } }) === STATUS_VALID
);
check(
  "validity.status degraded -> degraded",
  shortcutStatus({ valid: true, validity: { status: "degraded", findings: [] } }) === STATUS_DEGRADED
);
check(
  "validity.status broken -> broken",
  shortcutStatus({ valid: false, validity: { status: "broken", findings: [] } }) === STATUS_BROKEN
);

// ── fallback for OLD payloads with no `validity` object ──────────────────────
check(
  "no validity + valid:false -> broken",
  shortcutStatus({ valid: false }) === STATUS_BROKEN
);
check(
  "no validity + valid:true -> valid",
  shortcutStatus({ valid: true }) === STATUS_VALID
);
check(
  "no validity + valid absent -> valid",
  shortcutStatus({}) === STATUS_VALID
);
check(
  "unknown validity.status falls back to legacy valid:false -> broken",
  shortcutStatus({ valid: false, validity: { status: "weird" } }) === STATUS_BROKEN
);
check("null/undefined shortcut -> valid (no crash)", shortcutStatus(undefined) === STATUS_VALID);

// ── badge label mapping ──────────────────────────────────────────────────────
check("badge(valid) label", statusBadge(STATUS_VALID).label === "Valid");
check("badge(degraded) label", statusBadge(STATUS_DEGRADED).label === "Needs attention");
check("badge(broken) label", statusBadge(STATUS_BROKEN).label === "Broken");
check("badge(unknown) defaults to Valid", statusBadge("???").label === "Valid");
check(
  "shortcutBadge resolves through status",
  shortcutBadge({ validity: { status: "broken" } }).label === "Broken"
);

// ── finding helpers ──────────────────────────────────────────────────────────
const findings = [
  { code: "provider_missing", severity: "error" },
  { code: "style_missing", severity: "warning" },
  { code: "model_unavailable", severity: "warning" },
  { code: "legacy_field_ignored", severity: "info" },
  { code: "bogus", severity: "mystery" }, // unknown severity is ignored
];
const counts = countFindingsBySeverity(findings);
check("count errors", counts.error === 1, JSON.stringify(counts));
check("count warnings", counts.warning === 2, JSON.stringify(counts));
check("count info", counts.info === 1, JSON.stringify(counts));
check("unknown severity ignored", counts.error + counts.warning + counts.info === 4);
check("countFindingsBySeverity([]) is all zero", JSON.stringify(countFindingsBySeverity([])) === JSON.stringify({ error: 0, warning: 0, info: 0 }));
check("countFindingsBySeverity(undefined) does not crash", countFindingsBySeverity(undefined).error === 0);

check(
  "issueCount = errors + warnings (info excluded)",
  issueCount({ validity: { findings } }) === 3
);
check("issueCount of clean shortcut is 0", issueCount({ validity: { findings: [] } }) === 0);
check("issueCount of old payload (no validity) is 0", issueCount({ valid: false }) === 0);

check("shortcutFindings tolerates missing validity", shortcutFindings({}).length === 0);
check("shortcutFindings tolerates non-array", shortcutFindings({ validity: { findings: "nope" } }).length === 0);
check("shortcutFindings returns the array", shortcutFindings({ validity: { findings } }).length === 5);

if (failed) {
  console.error(`\n${failed} shortcut-status check(s) failed.`);
  process.exit(1);
}
console.log("\nAll shortcut-status checks passed.");
