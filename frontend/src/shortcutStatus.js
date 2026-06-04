// Frontend status helpers for the read-only Shortcut Inspector (Slice 2).
//
// These mirror the backend validity tiers computed in
// pipeline/shortcut_store.py (_validity / _status_from_findings). They are PURE
// functions (no React, no imports) so a node harness can unit-test them, and so
// every surface (Home card badge, customize row chip, Inspector drawer) derives
// its status the SAME way. The backend owns the vocabulary — never invent a new
// status here.

export const STATUS_VALID = "valid";
export const STATUS_DEGRADED = "degraded";
export const STATUS_BROKEN = "broken";

const KNOWN_STATUSES = new Set([STATUS_VALID, STATUS_DEGRADED, STATUS_BROKEN]);

// Derive the 3-tier status for a shortcut view. Prefers the additive
// `validity.status` from the Slice 1 backend; falls back to the legacy boolean
// `valid` for OLD payloads (or import-preview rows) that do not yet carry a
// `validity` object:
//   missing validity + valid === false  -> broken
//   missing validity + valid !== false  -> valid
// An unknown/garbage validity.status is treated the same as missing.
export function shortcutStatus(shortcut) {
  const status = shortcut?.validity?.status;
  if (KNOWN_STATUSES.has(status)) return status;
  if (shortcut?.valid === false) return STATUS_BROKEN;
  return STATUS_VALID;
}

// Display metadata per tier. `tone` is a stable, CSS-agnostic key the UI maps to
// colours; copy follows the brief (valid → "Valid", degraded → "Needs
// attention", broken → "Broken").
const BADGE_META = {
  [STATUS_VALID]: { label: "Valid", tone: "valid" },
  [STATUS_DEGRADED]: { label: "Needs attention", tone: "degraded" },
  [STATUS_BROKEN]: { label: "Broken", tone: "broken" },
};

export function statusBadge(status) {
  return BADGE_META[status] || BADGE_META[STATUS_VALID];
}

// Convenience: the badge for a whole shortcut view.
export function shortcutBadge(shortcut) {
  return statusBadge(shortcutStatus(shortcut));
}

// Safe accessor for the findings array (tolerates missing validity / non-arrays).
export function shortcutFindings(shortcut) {
  const list = shortcut?.validity?.findings;
  return Array.isArray(list) ? list : [];
}

// Count findings by severity. Severity uses the backend's error/warning/info
// (mapping to broken/degraded/info tiers). Unknown severities are ignored.
export function countFindingsBySeverity(findingList = []) {
  const counts = { error: 0, warning: 0, info: 0 };
  const list = Array.isArray(findingList) ? findingList : [];
  for (const finding of list) {
    const sev = finding?.severity;
    if (sev === "error" || sev === "warning" || sev === "info") counts[sev] += 1;
  }
  return counts;
}

// Total actionable issues (errors + warnings; info is advisory only), for a
// compact "N issues" chip on a customize row.
export function issueCount(shortcut) {
  const counts = countFindingsBySeverity(shortcutFindings(shortcut));
  return counts.error + counts.warning;
}
