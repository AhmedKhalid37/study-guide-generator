// Pure, React-free helpers for the Slice 89 Full Material Coverage controls /
// warnings polish (Builder summary + JobDetails "what this means" notes).
//
// Slice 89 is a frontend UX/control slice ONLY. It adds no backend field, keeps the
// Slice 87 submit payload shape, and changes nothing about extraction, OCR routing,
// material page-selection application, visual-manifest filtering, visual inclusion
// planning, table policy, rendering, exports, prompts, or providers. It implements
// no table reconstruction and inserts no visuals.
//
// Both builders are leak-safe by construction:
//   * The Builder summary thinks ONLY in positional upload order — it accepts an
//     ordered array of raw exclusion-input strings and emits COUNTS plus a boolean
//     "some entries were ignored" flag. It never carries filenames, paths, page
//     numbers, or the raw invalid tokens the user typed.
//   * The JobDetails notes consume the Slice 88 display model (already counts/status
//     only) and emit a fixed, closed-vocabulary set of static, honest note strings.
//     No artifact warning text is ever passed through verbatim.
// Output is deterministic and tolerant of missing/malformed input.

import { parsePageListInput } from "./materialPageSelections.js";

// ---- Builder material coverage summary ------------------------------------

// Closed note tokens for the JobDetails "Coverage notes" area. Each maps to a fixed
// static string below — no per-job source detail ever rides through a token.
export const NOTE_SELECTIONS_APPLIED = "selections_applied";
export const NOTE_VISUALS_PLANNED = "visuals_planned_insertion_later";
export const NOTE_TABLE_DEFERRED = "table_reconstruction_deferred";
export const NOTE_ARTIFACTS_UNAVAILABLE = "artifacts_unavailable";

// Static, honest copy for each note token. Deliberately does NOT overpromise: it
// never claims full figure insertion / table reconstruction is enabled yet.
const NOTE_TEXT = {
  [NOTE_SELECTIONS_APPLIED]:
    "Page/slide exclusions were applied to source text and visual/table planning.",
  [NOTE_VISUALS_PLANNED]:
    "Useful non-table visuals were planned; full automatic insertion is a later step.",
  [NOTE_TABLE_DEFERRED]: "Table reconstruction is not enabled yet.",
  [NOTE_ARTIFACTS_UNAVAILABLE]:
    "Coverage artifacts may be unavailable for older jobs or jobs without extracted material.",
};

const NOTE_TONE = {
  [NOTE_SELECTIONS_APPLIED]: "good",
  [NOTE_VISUALS_PLANNED]: "neutral",
  [NOTE_TABLE_DEFERRED]: "neutral",
  [NOTE_ARTIFACTS_UNAVAILABLE]: "neutral",
};

// Canonical, deterministic note order.
const NOTE_ORDER = [
  NOTE_SELECTIONS_APPLIED,
  NOTE_VISUALS_PLANNED,
  NOTE_TABLE_DEFERRED,
  NOTE_ARTIFACTS_UNAVAILABLE,
];

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

// Build the Builder-side material coverage review summary from the per-attachment
// raw exclusion-input strings IN UPLOAD ORDER (the same array the submit path maps
// from `attachments`). Returns safe counts + status only:
//
//   { active, attachmentsWithExclusions, totalExcludedPages, hasInvalidTokens }
//
// Filenames/paths are never accepted or emitted (the array is positional), and the
// raw invalid tokens the user typed are never echoed — only the boolean flag.
export function buildBuilderMaterialCoverageSummary({ exclusionInputs = [] } = {}) {
  const inputs = Array.isArray(exclusionInputs) ? exclusionInputs : [];
  let attachmentsWithExclusions = 0;
  let totalExcludedPages = 0;
  let hasInvalidTokens = false;

  for (const raw of inputs) {
    const { pages, warnings } = parsePageListInput(raw);
    if (warnings.length > 0) hasInvalidTokens = true;
    if (pages.length > 0) {
      attachmentsWithExclusions += 1;
      totalExcludedPages += pages.length;
    }
  }

  return {
    active: attachmentsWithExclusions > 0,
    attachmentsWithExclusions,
    totalExcludedPages,
    hasInvalidTokens,
  };
}

// ---- JobDetails coverage notes --------------------------------------------

// Derive the closed-vocabulary "Coverage notes" for the JobDetails Material Coverage
// panel from the Slice 88 display model. Returns an array of safe note objects
// `{ token, tone, text }` in a fixed deterministic order. Tolerates a missing or
// malformed model (treats everything as unavailable). No artifact warning text,
// filename, path, or count is ever embedded in the note strings.
export function buildJobMaterialCoverageNotes(displayModel) {
  const model = isRecord(displayModel) ? displayModel : {};
  const selections = isRecord(model.selections) ? model.selections : {};
  const visualCoverage = isRecord(model.visualCoverage) ? model.visualCoverage : {};
  const artifacts = isRecord(model.artifacts) ? model.artifacts : {};

  const tokens = new Set();

  if (selections.status === "active") {
    tokens.add(NOTE_SELECTIONS_APPLIED);
  }

  // Only claim visuals were planned when the plan artifact actually parsed into a
  // usable (non-malformed) summary — never overpromise insertion.
  if (
    Boolean(artifacts.visualInclusionPlanAvailable) &&
    visualCoverage.state !== "malformed" &&
    visualCoverage.state !== "unavailable"
  ) {
    tokens.add(NOTE_VISUALS_PLANNED);
  }

  // Table reconstruction is core-only and deferred — always say so honestly.
  tokens.add(NOTE_TABLE_DEFERRED);

  // When neither coverage artifact is available, explain it calmly (older jobs /
  // jobs without extracted material) rather than as an error.
  if (
    !artifacts.sourceCoverageReportAvailable &&
    !artifacts.visualInclusionPlanAvailable
  ) {
    tokens.add(NOTE_ARTIFACTS_UNAVAILABLE);
  }

  return NOTE_ORDER.filter((token) => tokens.has(token)).map((token) => ({
    token,
    tone: NOTE_TONE[token],
    text: NOTE_TEXT[token],
  }));
}
