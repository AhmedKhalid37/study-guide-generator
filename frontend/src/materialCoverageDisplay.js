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

const SOURCE_COVERAGE_KIND = "source_coverage_report";
const VISUAL_INCLUSION_PLAN_KIND = "visual_inclusion_plan";

// Closed status vocabularies. Anything else degrades to "unknown".
const COVERAGE_STATUSES = new Set(["completed", "partial", "skipped", "unreadable", "unknown"]);
const PLAN_STATUSES = new Set(["completed", "partial", "skipped", "unknown"]);

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
