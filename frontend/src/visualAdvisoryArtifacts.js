// Pure, React-free helpers for the JobDetails "Visual advisory" panel (Slice 50).
//
// Normalizes the read-only advisory visual artifact chain into compact, safe view
// models:
//
//   visual_assets_manifest.json  (Slice 40)  → page-level visual *candidates*
//   visual_asset_scoring.json    (Slice 47)  → advisory per-asset priority scoring
//   visual_replacement_plan.json (Slice 49)  → advisory candidate_* actions
//
// All three are advisory-only siblings reached by their EXACT filename. They make
// no production include/omit decision and never embed visuals into guides. This
// module is the read-only inspection boundary: it surfaces COUNTS and
// closed-vocabulary status/availability flags ONLY. It never mutates input, never
// throws on malformed input, and never surfaces raw OCR text, captions, source
// text, image bytes, data URIs, base64, provider payloads, paths, URLs, tokens, or
// any private document content. Even closed-vocab reason tokens are passed through
// a strict allowlist regex before display.

export const VISUAL_MANIFEST_ARTIFACT = "visual_assets_manifest.json";
export const VISUAL_SCORING_ARTIFACT = "visual_asset_scoring.json";
export const VISUAL_PLAN_ARTIFACT = "visual_replacement_plan.json";

// Closed reason token reported by the plan when Chandra-derived items are present;
// Chandra *extraction* integration stays blocked (Slice 45 status:not_run).
const CHANDRA_BLOCKED_REASON = "chandra_blocked";

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function nonNegativeInteger(value) {
  return Number.isFinite(value) && value >= 0 ? Math.floor(value) : 0;
}

// Only ever emit a short, lowercase closed-vocab token (a-z, 0-9, underscore).
// Anything else (or anything too long) degrades to a safe fallback so no free-form
// or sensitive text can ride out through a "reason"/status string.
export function safeToken(value, fallback = "unavailable") {
  if (typeof value !== "string") {
    return fallback;
  }
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > 48 || !/^[a-z0-9_]+$/.test(trimmed)) {
    return fallback;
  }
  return trimmed;
}

export function isArtifactMissing(error) {
  // A 404 means "not generated for this job" (e.g. non-PDF jobs, older jobs) and
  // is treated as a normal "not available", never a fatal error.
  return Boolean(error) && error.status === 404;
}

function warningCount(artifact) {
  return Array.isArray(artifact?.warnings) ? artifact.warnings.length : 0;
}

// Shared front-door: validate kind + status before any per-artifact summary. The
// returned base view model is extended by each summarizer with its own counts.
function baseState(artifact, expectedKind) {
  if (!isRecord(artifact)) {
    return {
      state: "malformed",
      tone: "warn",
      label: "Unexpected artifact",
      reason: "unavailable",
      warningCount: 0,
    };
  }
  if (artifact.kind !== expectedKind) {
    return {
      state: "malformed",
      tone: "warn",
      label: "Unexpected artifact",
      reason: "unavailable",
      warningCount: 0,
    };
  }
  if (artifact.status === "skipped") {
    return {
      state: "skipped",
      tone: "warn",
      label: "Skipped",
      reason: safeToken(artifact.reason),
      warningCount: warningCount(artifact),
    };
  }
  if (artifact.status !== "completed") {
    return {
      state: "malformed",
      tone: "warn",
      label: "Unexpected artifact",
      reason: "unavailable",
      warningCount: warningCount(artifact),
    };
  }
  return {
    state: "completed",
    tone: "good",
    label: "Completed",
    reason: null,
    warningCount: warningCount(artifact),
  };
}

export function summarizeVisualManifest(artifact) {
  const base = baseState(artifact, "visual_assets_manifest");
  if (base.state !== "completed") {
    return {
      ...base,
      assetCount: 0,
      pagesWithVisualSignals: 0,
      extractedFigureCount: 0,
    };
  }
  const summary = isRecord(artifact.summary) ? artifact.summary : {};
  return {
    ...base,
    label: "Available",
    assetCount: nonNegativeInteger(summary.asset_count),
    pagesWithVisualSignals: nonNegativeInteger(summary.pages_with_visual_signals),
    extractedFigureCount: nonNegativeInteger(summary.extracted_figure_count),
  };
}

export function summarizeVisualScoring(artifact) {
  const base = baseState(artifact, "visual_asset_scoring");
  if (base.state !== "completed") {
    return {
      ...base,
      scoreCount: 0,
      highPriorityCount: 0,
      mediumPriorityCount: 0,
      lowPriorityCount: 0,
      unknownPriorityCount: 0,
    };
  }
  const summary = isRecord(artifact.summary) ? artifact.summary : {};
  return {
    ...base,
    label: "Available",
    scoreCount: nonNegativeInteger(summary.asset_count),
    highPriorityCount: nonNegativeInteger(summary.high_priority_count),
    mediumPriorityCount: nonNegativeInteger(summary.medium_priority_count),
    lowPriorityCount: nonNegativeInteger(summary.low_priority_count),
    unknownPriorityCount: nonNegativeInteger(summary.unknown_priority_count),
  };
}

// Presence-only scan for the closed `chandra_blocked` reason in plan items or the
// plan's top-level warnings. Reads only the closed-vocab token, never item detail.
function planHasChandraBlocked(artifact) {
  const items = Array.isArray(artifact?.items) ? artifact.items : [];
  for (const item of items) {
    const reasons = Array.isArray(item?.reasons) ? item.reasons : [];
    if (reasons.includes(CHANDRA_BLOCKED_REASON)) {
      return true;
    }
  }
  const warnings = Array.isArray(artifact?.warnings) ? artifact.warnings : [];
  return warnings.includes(CHANDRA_BLOCKED_REASON);
}

export function summarizeVisualReplacementPlan(artifact) {
  const base = baseState(artifact, "visual_replacement_plan");
  if (base.state !== "completed") {
    return {
      ...base,
      itemCount: 0,
      includeAsFigureCount: 0,
      convertToTableCount: 0,
      summarizeAsTextCount: 0,
      reviewOnlyCount: 0,
      unknownCount: 0,
      chandraBlockedPresent: false,
    };
  }
  const summary = isRecord(artifact.summary) ? artifact.summary : {};
  return {
    ...base,
    label: "Available",
    itemCount: nonNegativeInteger(summary.item_count),
    includeAsFigureCount: nonNegativeInteger(summary.candidate_include_as_figure_count),
    convertToTableCount: nonNegativeInteger(summary.candidate_convert_to_table_count),
    summarizeAsTextCount: nonNegativeInteger(summary.candidate_summarize_as_text_count),
    reviewOnlyCount: nonNegativeInteger(summary.review_only_count),
    unknownCount: nonNegativeInteger(summary.unknown_count),
    chandraBlockedPresent: planHasChandraBlocked(artifact),
  };
}
