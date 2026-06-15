// Pure, React-free helpers for the JobDetails **Guide Quality** panel (Slice 104).
//
// Slice 102 added the guide-quality prompt contract + a flag-only contract lint;
// Slice 103 added the advisory guide-quality QA gate artifact. Slice 104 surfaces
// those already-sanitized, deterministic quality signals in JobDetails as a
// read-only / advisory panel. It is NOT a replacement for evaluation — it only
// summarizes the deterministic signals that already exist.
//
// Hard no-leak contract (matches the backend gate's own contract): these helpers
// copy **no string** out of the input artifacts. They read only a fixed set of
// known **non-negative integer count** fields and a small set of **closed status /
// kind tokens** (every token is validated against an in-module allow-list before it
// can ride out). Therefore no guide excerpt, phrase, heading, formula, numeric
// value, table content, caption, OCR text, filename, path, source title, image/asset
// ref, data URI, base64, provider payload, token, URL, or raw error can ever reach
// the display model — even if a hostile canary is injected into an input artifact.
//
// Every function tolerates missing/malformed input, never throws, and is
// deterministic (same input → byte-identical model). Artifact links are fixed
// exact-name labels only; no raw URLs are emitted.

// Reuse the already-shipped, sanitized summarizers + exact-name constants for the
// two artifacts the material-coverage panel also reads, so there is a single source
// of truth for their shapes (no duplicate parsing).
import {
  GUIDE_QUALITY_REPORT_V2_ARTIFACT,
  SOURCE_COVERAGE_ARTIFACT,
  isCoverageArtifactMissing,
  summarizeGuideQualityReportV2,
  summarizeSourceCoverage,
} from "./materialCoverageDisplay.js";

export {
  GUIDE_QUALITY_REPORT_V2_ARTIFACT,
  SOURCE_COVERAGE_ARTIFACT,
  isCoverageArtifactMissing,
};

// Exact-name artifacts owned by this panel.
export const GUIDE_QUALITY_QA_GATE_ARTIFACT = "guide_quality_qa_gate.json";
export const GUIDE_QUALITY_CONTRACT_LINT_ARTIFACT = "guide_quality_contract_lint.json";
export const MATH_VERIFICATION_ARTIFACT = "math_verification.json";

// Fixed, human-readable labels for the Artifacts section (never a raw URL/path).
export const GUIDE_QUALITY_ARTIFACT_LABELS = Object.freeze([
  { artifact: GUIDE_QUALITY_QA_GATE_ARTIFACT, label: "Guide Quality QA Gate" },
  { artifact: GUIDE_QUALITY_CONTRACT_LINT_ARTIFACT, label: "Guide Quality Contract Lint" },
  { artifact: GUIDE_QUALITY_REPORT_V2_ARTIFACT, label: "Guide Quality Report v2" },
  { artifact: MATH_VERIFICATION_ARTIFACT, label: "Math Verification" },
  { artifact: SOURCE_COVERAGE_ARTIFACT, label: "Source Coverage Report" },
]);

// --- Closed token allow-lists (this module owns what it emits) ---------------
const GATE_KIND = "guide_quality_qa_gate";
const LINT_KIND = "guide_quality_contract_lint";
const MATH_KIND = "math_verification";

const GATE_STATUSES = new Set(["passed", "warning", "skipped", "partial"]);
const GATE_CHECK_KINDS = new Set([
  "reasoning_leak",
  "required_structure",
  "math_verification",
  "source_coverage",
  "quality_report_v2",
]);
const GATE_CHECK_STATUSES = new Set(["passed", "warning", "unknown", "not_applicable"]);
const MATH_STATUSES = new Set(["completed", "skipped"]);

// --- Pure local helpers (no string ever copied from input) -------------------
function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function nonNegativeInteger(value) {
  return Number.isFinite(value) && value >= 0 ? Math.floor(value) : 0;
}

// Validate a scalar token against a closed allow-list; anything else → fallback.
function safeToken(value, allowed, fallback) {
  if (typeof value !== "string") return fallback;
  const token = value.trim().toLowerCase();
  return allowed.has(token) ? token : fallback;
}

function statusTone(status) {
  if (status === "passed") return "good";
  if (status === "warning") return "bad";
  return "warn"; // skipped / partial / unknown / not_applicable
}

// =============================================================================
// QA gate (guide_quality_qa_gate.json)
// =============================================================================
export function summarizeGuideQualityQaGate(gate) {
  if (!isRecord(gate) || gate.kind !== GATE_KIND) {
    return {
      state: "malformed",
      status: "unknown",
      tone: "warn",
      blocking: false,
      comprehensive: false,
      checkCount: 0,
      passedCount: 0,
      warningCount: 0,
      unknownCount: 0,
      checks: [],
    };
  }
  const status = safeToken(gate.status, GATE_STATUSES, "skipped");
  const summary = isRecord(gate.summary) ? gate.summary : {};
  const checks = [];
  if (Array.isArray(gate.checks)) {
    for (const entry of gate.checks) {
      if (!isRecord(entry)) continue;
      const kind = safeToken(entry.kind, GATE_CHECK_KINDS, null);
      if (kind === null) continue; // drop unknown-kind checks entirely
      checks.push({
        kind,
        status: safeToken(entry.status, GATE_CHECK_STATUSES, "unknown"),
        observedCount: nonNegativeInteger(entry.observed_count),
        expectedCount: nonNegativeInteger(entry.expected_count),
      });
    }
  }
  return {
    state: status === "skipped" ? "skipped" : "available",
    status,
    tone: statusTone(status),
    // ``blocking`` is advisory-only by construction; we never echo a truthy value.
    blocking: summary.blocking === true ? true : false,
    comprehensive: summary.comprehensive === true,
    checkCount: nonNegativeInteger(summary.check_count),
    passedCount: nonNegativeInteger(summary.passed_count),
    warningCount: nonNegativeInteger(summary.warning_count),
    unknownCount: nonNegativeInteger(summary.unknown_count),
    checks,
  };
}

// =============================================================================
// Prompt contract lint (guide_quality_contract_lint.json)
// =============================================================================
export function summarizeGuideQualityContractLint(lint) {
  const empty = {
    state: "malformed",
    status: "unknown",
    tone: "warn",
    comprehensive: false,
    reasoningLeakCount: 0,
    reasoningLeakStatus: "unknown",
    requiredSectionCount: 0,
    requiredSectionPresentCount: 0,
    requiredStructureStatus: "unknown",
    examAlertCount: 0,
    tableCount: 0,
    warningCount: 0,
  };
  if (!isRecord(lint) || lint.kind !== LINT_KIND) {
    return empty;
  }
  if (lint.status === "skipped") {
    return { ...empty, state: "skipped" };
  }
  const summary = isRecord(lint.summary) ? lint.summary : {};
  const comprehensive = summary.comprehensive === true;
  const reasoningLeakCount = nonNegativeInteger(summary.reasoning_leak_count);
  const requiredSectionCount = nonNegativeInteger(summary.required_section_count);
  const requiredSectionPresentCount = nonNegativeInteger(summary.required_section_present_count);
  const warningCount = nonNegativeInteger(summary.warning_count);

  const reasoningLeakStatus = reasoningLeakCount > 0 ? "warning" : "passed";
  let requiredStructureStatus = "not_applicable";
  if (comprehensive) {
    if (requiredSectionCount <= 0) {
      requiredStructureStatus = "unknown";
    } else if (requiredSectionPresentCount < requiredSectionCount) {
      requiredStructureStatus = "warning";
    } else {
      requiredStructureStatus = "passed";
    }
  }

  const tone = warningCount > 0 || reasoningLeakCount > 0 ? "bad" : "good";
  return {
    state: "available",
    status: warningCount > 0 || reasoningLeakCount > 0 ? "warning" : "passed",
    tone,
    comprehensive,
    reasoningLeakCount,
    reasoningLeakStatus,
    requiredSectionCount,
    requiredSectionPresentCount,
    requiredStructureStatus,
    examAlertCount: nonNegativeInteger(summary.exam_alert_count),
    tableCount: nonNegativeInteger(summary.table_count),
    warningCount,
  };
}

// =============================================================================
// Math verification (math_verification.json) — COUNTS ONLY, never claim text
// =============================================================================
export function summarizeMathVerificationArtifact(math) {
  const empty = {
    state: "malformed",
    status: "unknown",
    tone: "warn",
    checkedCount: 0,
    okCount: 0,
    mismatchCount: 0,
    unparseableCount: 0,
  };
  if (!isRecord(math) || math.kind !== MATH_KIND) {
    return empty;
  }
  const status = safeToken(math.status, MATH_STATUSES, null);
  if (status === "skipped") {
    return { ...empty, state: "skipped", status: "skipped" };
  }
  if (status !== "completed" || !isRecord(math.report)) {
    return empty;
  }
  // Read ONLY the numeric summary of the inner report — never the claim list,
  // expressions, claimed/computed values, or reasons.
  const summary = isRecord(math.report.summary) ? math.report.summary : {};
  const mismatchCount = nonNegativeInteger(summary.mismatch);
  const unparseableCount = nonNegativeInteger(summary.unparseable);
  const checkedCount = nonNegativeInteger(summary.total);
  const hasIssues = mismatchCount > 0 || unparseableCount > 0;
  return {
    state: "available",
    status: "completed",
    tone: hasIssues ? "bad" : "good",
    checkedCount,
    okCount: nonNegativeInteger(summary.ok),
    mismatchCount,
    unparseableCount,
  };
}

// =============================================================================
// Composite panel model
// =============================================================================
//
// Each artifact argument may be ``null`` (not fetched, 404, network error, or
// non-JSON) — every section then degrades to a calm "unavailable" state and is
// never treated as a hard error. Older jobs without these artifacts still produce
// a stable model.
export function summarizeGuideQualityPanelModel({
  qaGate = null,
  contractLint = null,
  guideQualityReportV2 = null,
  mathVerification = null,
  sourceCoverageReport = null,
} = {}) {
  const gate = qaGate === null ? null : summarizeGuideQualityQaGate(qaGate);
  const lint = contractLint === null ? null : summarizeGuideQualityContractLint(contractLint);
  const math = mathVerification === null ? null : summarizeMathVerificationArtifact(mathVerification);
  const reportV2 = guideQualityReportV2 === null ? null : summarizeGuideQualityReportV2(guideQualityReportV2);
  const coverage = sourceCoverageReport === null ? null : summarizeSourceCoverage(sourceCoverageReport);

  // Additional safe count not exposed by summarizeSourceCoverage: number of fully
  // unreadable sources. Read directly as a non-negative integer (no string copied).
  let unreadableSourceCount = 0;
  if (isRecord(sourceCoverageReport) && isRecord(sourceCoverageReport.summary)) {
    unreadableSourceCount = nonNegativeInteger(sourceCoverageReport.summary.unreadable_source_count);
  }

  return {
    // QA gate section ("not available" when the artifact is absent).
    qaGate: gate === null ? unavailable() : gate,
    qaGateAvailable: gate !== null,
    // Prompt contract lint section.
    contractLint: lint === null ? unavailable() : lint,
    contractLintAvailable: lint !== null,
    // Math verification section.
    mathVerification: math === null ? unavailable() : math,
    mathVerificationAvailable: math !== null,
    // Coverage / completeness section.
    sourceCoverage: coverage === null ? null : coverage,
    sourceCoverageAvailable: coverage !== null,
    unreadableSourceCount,
    guideQualityReportV2: reportV2 === null ? null : reportV2,
    guideQualityReportV2Available: reportV2 !== null,
    // Quality-check chips come from the QA gate's closed-kind checks.
    qualityChecks: gate === null ? [] : gate.checks,
    // Fixed exact-name artifact links (labels only — never a raw URL).
    artifactLinks: GUIDE_QUALITY_ARTIFACT_LABELS.map((entry) => ({ ...entry })),
  };
}

function unavailable() {
  return { state: "unavailable", status: "unknown", tone: "warn" };
}
