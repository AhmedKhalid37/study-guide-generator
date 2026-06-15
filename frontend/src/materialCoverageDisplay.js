// Pure, React-free helpers for the JobDetails "Material coverage" panel (Slice 88).
//
// Slice 88 is a READ-ONLY display slice. It surfaces the already-produced Full
// Material Coverage signals as compact, safe view models:
//
//   job.material_page_selection(s)   (Slices 79/80) → Builder exclusion intent
//   source_coverage_report.json      (Slice 77)     → per-source page coverage counts
//   visual_inclusion_plan.json       (Slice 84)     → planned non-table visual counts
//
// It changes NOTHING about extraction, OCR routing, material page-selection
// application, visual-manifest filtering, visual inclusion planning, table policy,
// rendering, exports, prompts, or providers. It implements no table reconstruction
// and inserts no visuals.
//
// This module is the read-only inspection boundary: it emits COUNTS and
// closed-vocabulary status/availability tokens ONLY. It never mutates input, never
// throws on malformed input, and never surfaces filenames, paths, source titles,
// document/OCR/caption/table text, image/asset refs, image bytes, data URIs,
// base64, provider payloads, tokens, full URLs, raw argv, socket paths,
// model/mmproj/executable paths, or raw exception strings. Even status tokens pass
// through a strict allowlist before display.

export const SOURCE_COVERAGE_ARTIFACT = "source_coverage_report.json";
export const VISUAL_INCLUSION_PLAN_ARTIFACT = "visual_inclusion_plan.json";
// Slice 97 — exact-name artifacts surfaced in the final Material Coverage panel.
export const TABLE_CANDIDATES_MANIFEST_ARTIFACT = "table_candidates_manifest.json";
export const TABLE_RECONSTRUCTION_POLICY_ARTIFACT = "table_reconstruction_policy.json";
export const GUIDE_QUALITY_REPORT_V2_ARTIFACT = "guide_quality_report_v2.json";

const SOURCE_COVERAGE_KIND = "source_coverage_report";
const VISUAL_INCLUSION_PLAN_KIND = "visual_inclusion_plan";
const TABLE_CANDIDATES_KIND = "table_candidates_manifest";
const TABLE_POLICY_KIND = "table_reconstruction_policy";
const GUIDE_QUALITY_KIND = "guide_quality_report";

// Closed status vocabularies. Anything else degrades to "unknown".
const COVERAGE_STATUSES = new Set(["completed", "partial", "skipped", "unreadable", "unknown"]);
const PLAN_STATUSES = new Set(["completed", "partial", "skipped", "unknown"]);
const TABLE_STATUSES = new Set(["completed", "partial", "skipped", "unknown"]);
const REPORT_STATUSES = new Set(["completed", "partial", "skipped", "unknown"]);
// Per-check status vocabulary owned by guide_quality_report_v2.
const CHECK_STATUSES = new Set(["passed", "warning", "not_applicable", "unknown"]);

// Closed set of guide-quality check kinds (fixed emission order in the report). Any
// other kind in the report is ignored; an absent kind degrades to "unknown".
const GUIDE_QUALITY_CHECK_KINDS = [
  "source_pages",
  "visuals",
  "tables",
  "missing_material",
  "coverage",
];

// Safe positional attachment key: "attachment_<index>" only. The backend envelope
// already strips filenames/paths/titles, but we re-guard here so a hostile key can
// never be counted (defense in depth) and is never read for display.
const SAFE_ATTACHMENT_KEY = /^attachment_\d+$/;

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function nonNegativeInteger(value) {
  return Number.isFinite(value) && value >= 0 ? Math.floor(value) : 0;
}

function pageArrayLength(value) {
  return Array.isArray(value) ? value.length : 0;
}

// Map a closed status token through an allowlist; anything unexpected (free text,
// over-long, non-string) degrades to "unknown" so no free-form text rides out.
function safeStatus(value, allowed) {
  if (typeof value !== "string") {
    return "unknown";
  }
  const trimmed = value.trim().toLowerCase();
  return allowed.has(trimmed) ? trimmed : "unknown";
}

function statusTone(status) {
  if (status === "completed") return "good";
  if (status === "partial") return "warn";
  if (status === "skipped") return "neutral";
  return "warn";
}

// A 404 means "not generated for this job" (non-PDF jobs, older jobs) and is a
// normal "not available", never a fatal error.
export function isCoverageArtifactMissing(error) {
  return Boolean(error) && error.status === 404;
}

// --- Material page selections (from the job response) ----------------------
//
// Reads only the safe, server-normalized envelopes already echoed by job_response:
//   job.material_page_selections = { version, attachments: { attachment_<i>: model }, warnings }
//   job.material_page_selection  = { version, mode, include_pages, exclude_pages, warnings } (global fallback)
// where each model is the Slice 78 page-selection model. Keys are positional
// (attachment_<index>) by construction; filenames/paths cannot appear here. This
// helper counts attachments that carry an explicit include/exclude page set and
// reports an active/inactive status — never any page numbers, key, or raw input.
export function summarizeMaterialSelections(job) {
  const result = {
    status: "inactive",
    attachmentsWithSelections: 0,
    globalActive: false,
    hasWarnings: false,
  };
  if (!isRecord(job)) {
    return result;
  }

  const envelope = job.material_page_selections;
  if (isRecord(envelope)) {
    const attachments = isRecord(envelope.attachments) ? envelope.attachments : {};
    for (const key of Object.keys(attachments)) {
      if (!SAFE_ATTACHMENT_KEY.test(key)) continue;
      const model = attachments[key];
      if (!isRecord(model)) continue;
      if (pageArrayLength(model.include_pages) > 0 || pageArrayLength(model.exclude_pages) > 0) {
        result.attachmentsWithSelections += 1;
      }
    }
    if (Array.isArray(envelope.warnings) && envelope.warnings.length > 0) {
      result.hasWarnings = true;
    }
  }

  const global = job.material_page_selection;
  if (isRecord(global)) {
    const mode = typeof global.mode === "string" ? global.mode.trim().toLowerCase() : "all";
    const hasPages =
      pageArrayLength(global.include_pages) > 0 || pageArrayLength(global.exclude_pages) > 0;
    if ((mode === "include" || mode === "exclude") && hasPages) {
      result.globalActive = true;
    }
  }

  result.status =
    result.attachmentsWithSelections > 0 || result.globalActive ? "active" : "inactive";
  return result;
}

// --- Source coverage report ------------------------------------------------
export function summarizeSourceCoverage(report) {
  if (!isRecord(report) || report.kind !== SOURCE_COVERAGE_KIND) {
    return {
      state: "malformed",
      status: "unknown",
      tone: "warn",
      sourceCount: 0,
      totalPages: 0,
      coveredPages: 0,
      embeddedTextPages: 0,
      ocrPages: 0,
      unreadablePages: 0,
      visualCandidatePages: 0,
    };
  }
  const status = safeStatus(report.status, COVERAGE_STATUSES);
  const summary = isRecord(report.summary) ? report.summary : {};
  return {
    state: status === "skipped" ? "skipped" : "available",
    status,
    tone: statusTone(status),
    sourceCount: nonNegativeInteger(summary.source_count),
    totalPages: nonNegativeInteger(summary.total_pages),
    coveredPages: nonNegativeInteger(summary.covered_pages),
    embeddedTextPages: nonNegativeInteger(summary.embedded_text_pages),
    ocrPages: nonNegativeInteger(summary.ocr_pages),
    unreadablePages: nonNegativeInteger(summary.empty_or_unreadable_pages),
    visualCandidatePages: nonNegativeInteger(summary.visual_candidate_pages),
  };
}

// --- Visual inclusion plan -------------------------------------------------
export function summarizeVisualInclusionPlan(plan) {
  if (!isRecord(plan) || plan.kind !== VISUAL_INCLUSION_PLAN_KIND) {
    return {
      state: "malformed",
      status: "unknown",
      tone: "warn",
      sourceCount: 0,
      candidateCount: 0,
      plannedUsefulCount: 0,
      tableLikeSkippedCount: 0,
      unsafeSkippedCount: 0,
      pagesWithPlannedVisuals: 0,
    };
  }
  const status = safeStatus(plan.status, PLAN_STATUSES);
  const summary = isRecord(plan.summary) ? plan.summary : {};
  return {
    state: status === "skipped" ? "skipped" : "available",
    status,
    tone: statusTone(status),
    sourceCount: nonNegativeInteger(summary.source_count),
    candidateCount: nonNegativeInteger(summary.candidate_count),
    plannedUsefulCount: nonNegativeInteger(summary.non_table_planned_count),
    tableLikeSkippedCount: nonNegativeInteger(summary.table_like_skipped_count),
    unsafeSkippedCount: nonNegativeInteger(summary.unsafe_or_incomplete_skipped_count),
    pagesWithPlannedVisuals: nonNegativeInteger(summary.page_count_with_planned_visuals),
  };
}

// --- Composite display model ----------------------------------------------
//
// Combines the three safe summaries plus a static, deferred table-policy note.
// `sourceCoverageReport` / `visualInclusionPlan` may be null (not fetched yet or
// 404/unavailable) — in that case the corresponding section reports "unavailable"
// and is never treated as an error. Table reconstruction stays deferred, so the
// table-policy note is always the same static, non-leaking string.
export function buildMaterialCoverageDisplayModel({
  job = null,
  sourceCoverageReport = null,
  visualInclusionPlan = null,
} = {}) {
  return {
    selections: summarizeMaterialSelections(job),
    sourceCoverage: sourceCoverageReport
      ? summarizeSourceCoverage(sourceCoverageReport)
      : { state: "unavailable", status: "unavailable", tone: "neutral" },
    visualCoverage: visualInclusionPlan
      ? summarizeVisualInclusionPlan(visualInclusionPlan)
      : { state: "unavailable", status: "unavailable", tone: "neutral" },
    tablePolicy: {
      // Slice 85 added the table reconstruction policy CORE only; no artifact is
      // emitted and reconstruction is not enabled. This note is intentionally
      // static and carries no per-job source detail.
      state: "core_available",
      note: "Policy core available; table reconstruction not yet enabled.",
    },
    artifacts: {
      sourceCoverageReportAvailable: Boolean(sourceCoverageReport),
      visualInclusionPlanAvailable: Boolean(visualInclusionPlan),
    },
  };
}

// --- Table candidates manifest (Slice 92 artifact) -------------------------
//
// Reads the already-sanitized table_candidates_manifest.json for COUNTS ONLY. The
// manifest never carries table text / captions / source detail, but we re-guard
// here: only closed status tokens and non-negative integer counts ride out, and a
// wrong/missing kind degrades to a safe "malformed" view.
export function summarizeTableCandidatesManifest(manifest) {
  if (!isRecord(manifest) || manifest.kind !== TABLE_CANDIDATES_KIND) {
    return {
      state: "malformed",
      status: "unknown",
      tone: "warn",
      sourceCount: 0,
      candidateCount: 0,
      tableLikeCandidateCount: 0,
      skippedNonTableCount: 0,
      unsafeOrIncompleteSkippedCount: 0,
      pagesWithTableCandidates: 0,
    };
  }
  const status = safeStatus(manifest.status, TABLE_STATUSES);
  const summary = isRecord(manifest.summary) ? manifest.summary : {};
  return {
    state: status === "skipped" ? "skipped" : "available",
    status,
    tone: statusTone(status),
    sourceCount: nonNegativeInteger(summary.source_count),
    candidateCount: nonNegativeInteger(summary.candidate_count),
    tableLikeCandidateCount: nonNegativeInteger(summary.table_like_candidate_count),
    skippedNonTableCount: nonNegativeInteger(summary.skipped_non_table_count),
    unsafeOrIncompleteSkippedCount: nonNegativeInteger(summary.unsafe_or_incomplete_skipped_count),
    pagesWithTableCandidates: nonNegativeInteger(summary.page_count_with_table_candidates),
  };
}

// --- Table reconstruction policy (Slice 92 artifact) -----------------------
//
// Reads the already-sanitized table_reconstruction_policy.json for COUNTS ONLY. The
// policy never inserts a table as a screenshot, so `screenshotInsertCount` is always
// 0 by construction; we surface it so the panel can prove "not used".
export function summarizeTableReconstructionPolicy(policy) {
  if (!isRecord(policy) || policy.kind !== TABLE_POLICY_KIND) {
    return {
      state: "malformed",
      status: "unknown",
      tone: "warn",
      candidateCount: 0,
      policyItemCount: 0,
      reconstructWithOriginalCount: 0,
      simplifyOnlyCount: 0,
      deferCount: 0,
      skipUnreadableCount: 0,
      skipUnsafeCount: 0,
      screenshotInsertCount: 0,
    };
  }
  const status = safeStatus(policy.status, TABLE_STATUSES);
  const summary = isRecord(policy.summary) ? policy.summary : {};
  return {
    state: status === "skipped" ? "skipped" : "available",
    status,
    tone: statusTone(status),
    candidateCount: nonNegativeInteger(summary.candidate_count),
    policyItemCount: nonNegativeInteger(summary.policy_item_count),
    reconstructWithOriginalCount: nonNegativeInteger(summary.reconstruct_with_original_count),
    simplifyOnlyCount: nonNegativeInteger(summary.simplify_only_count),
    deferCount: nonNegativeInteger(summary.defer_count),
    skipUnreadableCount: nonNegativeInteger(summary.skip_unreadable_count),
    skipUnsafeCount: nonNegativeInteger(summary.skip_unsafe_count),
    // Always 0 by policy design; re-clamped here so a tampered value cannot show > 0.
    screenshotInsertCount: nonNegativeInteger(summary.screenshot_insert_count),
  };
}

// --- Guide quality report v2 (Slice 96 artifact) ---------------------------
//
// Reads the already-sanitized guide_quality_report_v2.json. This is the final
// observable signal for missing-material and coverage-aware behaviour. It emits only
// closed report/check status tokens and non-negative integer counts — the report's
// own `instruction` strings and `check_id`s are NOT surfaced (counts/statuses only).
// `safeImageRefCount` is the observed figure-ref count the report measured in the
// generated guide; we never expose the refs themselves.
export function summarizeGuideQualityReportV2(report) {
  const blankChecks = () => {
    const out = {};
    for (const kind of GUIDE_QUALITY_CHECK_KINDS) out[kind] = "unknown";
    return out;
  };
  if (!isRecord(report) || report.kind !== GUIDE_QUALITY_KIND) {
    return {
      state: "malformed",
      status: "unknown",
      tone: "warn",
      guidePresent: false,
      warningCount: 0,
      sourcePageSignalCount: 0,
      safeImageRefCount: 0,
      plannedVisualCount: 0,
      tableCandidateCount: 0,
      tablePolicyItemCount: 0,
      missingMaterialItemCount: 0,
      coverageSignalCount: 0,
      checks: blankChecks(),
    };
  }
  const status = safeStatus(report.status, REPORT_STATUSES);
  const summary = isRecord(report.summary) ? report.summary : {};
  const checks = blankChecks();
  if (Array.isArray(report.checks)) {
    for (const entry of report.checks) {
      if (!isRecord(entry)) continue;
      const kind = typeof entry.kind === "string" ? entry.kind.trim().toLowerCase() : "";
      if (Object.prototype.hasOwnProperty.call(checks, kind)) {
        checks[kind] = safeStatus(entry.status, CHECK_STATUSES);
      }
    }
  }
  return {
    state: status === "skipped" ? "skipped" : "available",
    status,
    tone: statusTone(status),
    guidePresent: summary.guide_present === true,
    warningCount: nonNegativeInteger(summary.warning_count),
    sourcePageSignalCount: nonNegativeInteger(summary.source_page_signal_count),
    safeImageRefCount: nonNegativeInteger(summary.safe_image_ref_count),
    plannedVisualCount: nonNegativeInteger(summary.planned_visual_count),
    tableCandidateCount: nonNegativeInteger(summary.table_candidate_count),
    tablePolicyItemCount: nonNegativeInteger(summary.table_policy_item_count),
    missingMaterialItemCount: nonNegativeInteger(summary.missing_material_item_count),
    coverageSignalCount: nonNegativeInteger(summary.coverage_signal_count),
    checks,
  };
}

// --- Composite FINAL display model (Slice 97) ------------------------------
//
// Extends the Slice 88 model with the table candidate/policy and guide-quality
// summaries so JobDetails can render the final read-only coverage dashboard. Each
// new artifact may be null (not fetched yet, 404, or unavailable) — in that case the
// section reports a calm "unavailable" state and is never treated as an error. The
// Slice 88 `tablePolicy` static note is preserved for backward compatibility.
export function buildMaterialCoverageFinalModel({
  job = null,
  sourceCoverageReport = null,
  visualInclusionPlan = null,
  tableCandidatesManifest = null,
  tableReconstructionPolicy = null,
  guideQualityReportV2 = null,
} = {}) {
  const base = buildMaterialCoverageDisplayModel({
    job,
    sourceCoverageReport,
    visualInclusionPlan,
  });
  return {
    ...base,
    tableCandidates: tableCandidatesManifest
      ? summarizeTableCandidatesManifest(tableCandidatesManifest)
      : { state: "unavailable", status: "unavailable", tone: "neutral" },
    tableReconstructionPolicy: tableReconstructionPolicy
      ? summarizeTableReconstructionPolicy(tableReconstructionPolicy)
      : { state: "unavailable", status: "unavailable", tone: "neutral" },
    guideQuality: guideQualityReportV2
      ? summarizeGuideQualityReportV2(guideQualityReportV2)
      : { state: "unavailable", status: "unavailable", tone: "neutral" },
    artifacts: {
      ...base.artifacts,
      tableCandidatesManifestAvailable: Boolean(tableCandidatesManifest),
      tableReconstructionPolicyAvailable: Boolean(tableReconstructionPolicy),
      guideQualityReportV2Available: Boolean(guideQualityReportV2),
    },
  };
}
