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
export const GUIDE_QUALITY_RUBRIC_SCORE_ARTIFACT = "guide_quality_rubric_score.json";
export const QUALITY_SAFETY_ARTIFACT = "quality_safety_unified_qa.json";

// Fixed, human-readable labels for the Artifacts section (never a raw URL/path).
export const GUIDE_QUALITY_ARTIFACT_LABELS = Object.freeze([
  { artifact: GUIDE_QUALITY_QA_GATE_ARTIFACT, label: "Guide Quality QA Gate" },
  { artifact: GUIDE_QUALITY_CONTRACT_LINT_ARTIFACT, label: "Guide Quality Contract Lint" },
  { artifact: GUIDE_QUALITY_REPORT_V2_ARTIFACT, label: "Guide Quality Report v2" },
  { artifact: GUIDE_QUALITY_RUBRIC_SCORE_ARTIFACT, label: "Guide Quality Rubric Score" },
  { artifact: QUALITY_SAFETY_ARTIFACT, label: "Quality Safety Unified QA" },
  { artifact: MATH_VERIFICATION_ARTIFACT, label: "Math Verification" },
  { artifact: SOURCE_COVERAGE_ARTIFACT, label: "Source Coverage Report" },
]);

// --- Closed token allow-lists (this module owns what it emits) ---------------
const GATE_KIND = "guide_quality_qa_gate";
const LINT_KIND = "guide_quality_contract_lint";
const MATH_KIND = "math_verification";
const RUBRIC_KIND = "guide_quality_rubric_score";

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
const RUBRIC_STATUSES = new Set(["completed", "partial", "skipped"]);
const RUBRIC_AXIS_STATUSES = new Set(["passed", "warning", "unknown", "not_applicable"]);
const RUBRIC_CONFIDENCE_VALUES = new Set(["deterministic", "advisory", "unsupported"]);
const RUBRIC_AXIS_KINDS = new Set([
  "reasoning_hygiene",
  "required_structure",
  "exam_focus",
  "reference_tables",
  "math_verification",
  "source_coverage",
  "coverage_signal_alignment",
  "visual_table_honesty",
  "beginner_scaffolding",
  "worked_example_completeness",
]);
const QUALITY_SAFETY_JOB_KIND = "quality_safety_job_artifact";
const QUALITY_SAFETY_UNIFIED_KIND = "quality_safety_unified_qa";
const QUALITY_SAFETY_STATUSES = new Set(["passed", "warning", "failed", "skipped", "partial", "unknown", "missing", "unavailable"]);
const QUALITY_SAFETY_COMPONENTS = ["layer1", "recompute", "canonical", "leak"];
const QUALITY_SAFETY_COMPONENT_SET = new Set([...QUALITY_SAFETY_COMPONENTS, "unknown"]);
const QUALITY_SAFETY_SEVERITIES = new Set(["blocking", "warning", "info", "unknown"]);
const QUALITY_SAFETY_VERIFICATION_STATUSES = new Set([
  "verified_recompute",
  "failed_recompute",
  "verified_canonical",
  "failed_canonical",
  "unverified",
  "not_applicable",
  "unknown",
]);
const QUALITY_SAFETY_AXES = ["accuracy", "coverage", "solved_problem", "clarity"];
const QUALITY_SAFETY_CHECK_IDS = new Set([
  "leaked_reasoning",
  "numeric_correctness",
  "worked_answer_completeness",
  "coverage",
  "mock_question_count",
  "weighted_gini",
  "total_error",
  "amount_of_say",
  "softmax",
  "cross_entropy",
  "forward_pass",
  "numeric_fact_not_recomputable",
  "non_numeric_fact_not_applicable",
  "canonical_fixture_match",
  "canonical_fixture_mismatch",
  "canonical_fixture_missing",
  "canonical_fixture_skipped_by_recompute_verified",
  "canonical_fixture_skipped_by_recompute_failed",
  "canonical_fixture_not_applicable",
  "quality_safety_leak_scan",
  "unknown",
  "unknown_check",
]);
const QUALITY_SAFETY_WARNING_TOKENS = new Set([
  "malformed_input_degraded",
  "component_missing",
  "component_malformed",
  "layer1_warning",
  "numeric_unverified",
  "canonical_unmatched",
  "leak_warning",
  "coverage_warning",
  "mock_question_warning",
  "unknown_verification_context",
  "candidate_markdown_missing",
  "extraction_bundle_missing",
  "fact_sheet_component_missing",
  "recompute_component_missing",
  "canonical_component_missing",
  "artifact_write_failed",
  "component_degraded",
  "unsafe_metadata_dropped",
  "max_items_reached",
  "unknown",
]);
const QUALITY_SAFETY_SUMMARY_KEYS = [
  "blocking_failure_count",
  "warning_count",
  "numeric_blocking_failure_count",
  "leak_blocking_failure_count",
  "verified_recompute_count",
  "verified_canonical_count",
  "failed_recompute_count",
  "failed_canonical_count",
  "unverified_fact_count",
  "unknown_context_leak_count",
];
const QUALITY_SAFETY_MAX_FAILURES = 12;
const QUALITY_SAFETY_MAX_WARNINGS = 12;
const QUALITY_SAFETY_MAX_FACT_IDS = 6;
const SAFE_FACT_ID_RE = /^[a-z0-9][a-z0-9._-]{0,48}$/;
const UNSAFE_FACT_ID_RE = /(private|source|deck|upload|quality|spec|evidence|quote|ocr|caption|table|provider|payload|\.pdf|\.docx|\.zip|\.png|\.jpe?g|\.webp|https?|authorization|bearer|token|secret|base64|data:)/i;

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
  if (status === "warning" || status === "failed") return "bad";
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
// Rubric score (guide_quality_rubric_score.json) — closed axes + counts only
// =============================================================================
export function summarizeGuideQualityRubricScore(rubric) {
  const empty = {
    state: "malformed",
    status: "skipped",
    tone: "warn",
    blocking: false,
    advisory: true,
    scoreTotal: 0,
    scorePossible: 0,
    knownAxisCount: 0,
    unknownAxisCount: 0,
    warningAxisCount: 0,
    rubricAxisCount: 0,
    axes: [],
  };
  if (!isRecord(rubric) || rubric.kind !== RUBRIC_KIND) {
    return empty;
  }
  const status = safeToken(rubric.status, RUBRIC_STATUSES, "skipped");
  const summary = isRecord(rubric.summary) ? rubric.summary : {};
  const axes = [];
  if (Array.isArray(rubric.axes)) {
    for (const entry of rubric.axes) {
      if (!isRecord(entry)) continue;
      const kind = safeToken(entry.kind, RUBRIC_AXIS_KINDS, null);
      if (kind === null) continue;
      const score = entry.score === 0 || entry.score === 1 || entry.score === 2 ? entry.score : null;
      axes.push({
        kind,
        status: safeToken(entry.status, RUBRIC_AXIS_STATUSES, "unknown"),
        confidence: safeToken(entry.confidence, RUBRIC_CONFIDENCE_VALUES, "unsupported"),
        score,
      });
    }
  }

  const warningAxisCount = nonNegativeInteger(summary.warning_axis_count);
  return {
    state: status === "skipped" ? "skipped" : "available",
    status,
    tone: warningAxisCount > 0 ? "bad" : status === "completed" ? "good" : "warn",
    // The rubric artifact is advisory-only by contract. Do not echo a hostile true.
    blocking: false,
    advisory: true,
    scoreTotal: nonNegativeInteger(summary.score_total),
    scorePossible: nonNegativeInteger(summary.score_possible),
    knownAxisCount: nonNegativeInteger(summary.known_axis_count),
    unknownAxisCount: nonNegativeInteger(summary.unknown_axis_count),
    warningAxisCount,
    rubricAxisCount: nonNegativeInteger(summary.rubric_axis_count),
    axes,
  };
}

// =============================================================================
// Quality Safety (quality_safety_unified_qa.json) — closed tokens/counts only
// =============================================================================
export function normalizeQualitySafetyArtifact(raw) {
  const empty = {
    state: "unavailable",
    artifactStatus: "missing",
    status: "missing",
    tone: "warn",
    advisory: null,
    shippable: null,
    safetyFloorGreen: null,
    componentStatuses: Object.fromEntries(QUALITY_SAFETY_COMPONENTS.map((component) => [component, "unknown"])),
    axes: Object.fromEntries(QUALITY_SAFETY_AXES.map((axis) => [axis, null])),
    summary: Object.fromEntries(QUALITY_SAFETY_SUMMARY_KEYS.map((key) => [key, 0])),
    blockingFailures: [],
    warningTokens: [],
  };
  if (!isRecord(raw)) {
    return empty;
  }

  const root = raw.kind === QUALITY_SAFETY_JOB_KIND && isRecord(raw.quality_safety_unified_qa)
    ? raw.quality_safety_unified_qa
    : raw;
  if (!isRecord(root) || root.kind !== QUALITY_SAFETY_UNIFIED_KIND) {
    return { ...empty, state: "malformed", artifactStatus: "unavailable", status: "unavailable" };
  }

  const rawSummary = isRecord(root.summary) ? root.summary : {};
  const jobSummary = isRecord(raw.summary) ? raw.summary : {};
  const status = safeToken(root.status, QUALITY_SAFETY_STATUSES, "unknown");
  const componentStatuses = {};
  const rawComponents = isRecord(root.component_statuses) ? root.component_statuses : {};
  for (const component of QUALITY_SAFETY_COMPONENTS) {
    componentStatuses[component] = safeToken(rawComponents[component], QUALITY_SAFETY_STATUSES, "unknown");
  }

  const rawAxes = isRecord(root.deterministic_axes_0_5) ? root.deterministic_axes_0_5 : {};
  const axes = {};
  for (const axis of QUALITY_SAFETY_AXES) {
    axes[axis] = qualitySafetyAxis(rawAxes[axis]);
  }

  const summary = {};
  for (const key of QUALITY_SAFETY_SUMMARY_KEYS) {
    summary[key] = nonNegativeInteger(rawSummary[key]);
  }
  if (summary.warning_count === 0) {
    summary.warning_count = nonNegativeInteger(jobSummary.quality_safety_warning_count || jobSummary.warning_count);
  }

  const warningTokens = [];
  const warningSources = [root.warning_tokens, root.warnings, raw.warning_tokens, raw.warnings];
  for (const source of warningSources) {
    if (!Array.isArray(source)) continue;
    for (const token of source) {
      if (warningTokens.length >= QUALITY_SAFETY_MAX_WARNINGS) break;
      const safe = safeToken(token, QUALITY_SAFETY_WARNING_TOKENS, "unknown");
      if (!warningTokens.includes(safe)) warningTokens.push(safe);
    }
  }

  const rawFailures = Array.isArray(root.blocking_failures)
    ? root.blocking_failures
    : Array.isArray(raw.blocking_failures)
      ? raw.blocking_failures
      : [];
  const blockingFailures = [];
  for (const entry of rawFailures) {
    if (!isRecord(entry) || blockingFailures.length >= QUALITY_SAFETY_MAX_FAILURES) continue;
    const checkId = safeQualitySafetyCheckId(entry.check_id || entry.id);
    const row = {
      component: safeToken(entry.component, QUALITY_SAFETY_COMPONENT_SET, "unknown"),
      checkId,
      status: safeToken(entry.status, QUALITY_SAFETY_STATUSES, "unknown"),
      severity: safeToken(entry.severity, QUALITY_SAFETY_SEVERITIES, "unknown"),
      verificationStatus: safeToken(entry.verification_status, QUALITY_SAFETY_VERIFICATION_STATUSES, "unknown"),
    };
    const count = nonNegativeInteger(entry.count);
    if (count > 0) row.count = count;
    const factIds = safeQualitySafetyFactIds(entry.fact_ids);
    if (factIds.length > 0) row.factIds = factIds;
    blockingFailures.push(row);
  }

  return {
    ...empty,
    state: "available",
    artifactStatus: "loaded",
    status,
    tone: statusTone(status),
    advisory: typeof raw.advisory === "boolean" ? raw.advisory : null,
    shippable: typeof root.shippable === "boolean" ? root.shippable : null,
    safetyFloorGreen: typeof root.safety_floor_green === "boolean" ? root.safety_floor_green : null,
    componentStatuses,
    axes,
    summary,
    blockingFailures,
    warningTokens,
  };
}

function qualitySafetyAxis(value) {
  return Number.isFinite(value) && value >= 0 && value <= 5 ? value : null;
}

function safeQualitySafetyCheckId(value) {
  const token = safeToken(value, QUALITY_SAFETY_CHECK_IDS, "unknown");
  return token === "unknown_check" ? "unknown" : token;
}

function safeQualitySafetyFactIds(value) {
  if (!Array.isArray(value)) return [];
  const ids = [];
  for (const item of value) {
    if (ids.length >= QUALITY_SAFETY_MAX_FACT_IDS) break;
    if (typeof item !== "string") continue;
    const token = item.trim().toLowerCase();
    if (SAFE_FACT_ID_RE.test(token) && !UNSAFE_FACT_ID_RE.test(token) && !ids.includes(token)) ids.push(token);
  }
  return ids;
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
  rubricScore = null,
  qualitySafetyArtifact = null,
} = {}) {
  const gate = qaGate === null ? null : summarizeGuideQualityQaGate(qaGate);
  const lint = contractLint === null ? null : summarizeGuideQualityContractLint(contractLint);
  const math = mathVerification === null ? null : summarizeMathVerificationArtifact(mathVerification);
  const reportV2 = guideQualityReportV2 === null ? null : summarizeGuideQualityReportV2(guideQualityReportV2);
  const coverage = sourceCoverageReport === null ? null : summarizeSourceCoverage(sourceCoverageReport);
  const rubric = rubricScore === null ? null : summarizeGuideQualityRubricScore(rubricScore);
  const qualitySafety = normalizeQualitySafetyArtifact(qualitySafetyArtifact);

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
    // Rubric score section.
    rubricScore: rubric === null ? unavailable() : rubric,
    rubricScoreAvailable: rubric !== null,
    // Quality Safety advisory floor section.
    qualitySafety,
    qualitySafetyAvailable: qualitySafety.state === "available",
    // Quality-check chips come from the QA gate's closed-kind checks.
    qualityChecks: gate === null ? [] : gate.checks,
    // Fixed exact-name artifact links (labels only — never a raw URL).
    artifactLinks: GUIDE_QUALITY_ARTIFACT_LABELS.map((entry) => ({ ...entry })),
  };
}

function unavailable() {
  return { state: "unavailable", status: "unknown", tone: "warn" };
}
