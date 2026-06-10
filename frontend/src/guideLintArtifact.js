// Pure, React-free helpers for the JobDetails guide-lint artifact UI (Slice 28).
//
// Normalizes the read-only `guide_lint.json` artifact produced by Slice 27 into a
// compact, advisory view model. The guide lint is a *structural / rendering-risk*
// check (empty headings, broken tables, unbalanced math, KaTeX render risk,
// missing sections, page-citation plausibility) — it is NOT a content-truth
// check. This module never mutates input, never throws on malformed input, and
// never surfaces raw URLs, secrets, or host paths.

export const GUIDE_LINT_ARTIFACT = "guide_lint.json";
export const GUIDE_LINT_DISPLAY_LIMIT = 8;

const SUMMARY_KEYS = ["total", "error", "warning", "info"];
const KNOWN_SEVERITIES = new Set(["error", "warning", "info"]);
// Sort order for "top findings": most severe first.
const SEVERITY_RANK = { error: 0, warning: 1, info: 2 };

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function nonNegativeInteger(value) {
  return Number.isFinite(value) && value >= 0 ? Math.floor(value) : 0;
}

function normalizeSummary(summary) {
  const source = isRecord(summary) ? summary : {};
  return Object.fromEntries(SUMMARY_KEYS.map((key) => [key, nonNegativeInteger(source[key])]));
}

export function safeLintExcerpt(value, maxLength = 160) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

function findingSeverity(finding) {
  const severity = typeof finding?.severity === "string" ? finding.severity : "";
  return KNOWN_SEVERITIES.has(severity) ? severity : "info";
}

function normalizeFinding(finding, index) {
  const severity = findingSeverity(finding);
  return {
    id:
      typeof finding?.id === "string" && finding.id
        ? finding.id
        : `lint_${String(index + 1).padStart(4, "0")}`,
    rule: safeLintExcerpt(finding?.rule || "rule", 60),
    severity,
    line: Number.isFinite(finding?.line) && finding.line > 0 ? Math.floor(finding.line) : null,
    message: safeLintExcerpt(finding?.message, 200),
    excerpt: safeLintExcerpt(finding?.excerpt, 160),
  };
}

function boundedFindings(findings, limit = GUIDE_LINT_DISPLAY_LIMIT) {
  if (!Array.isArray(findings)) {
    return { findings: [], hiddenCount: 0 };
  }
  const normalized = findings.map(normalizeFinding);
  // Stable severity sort (error → warning → info) while preserving original
  // order within a severity bucket (findings already arrive line-ordered).
  const priority = normalized
    .map((finding, index) => ({ finding, index }))
    .sort((a, b) => {
      const rank = SEVERITY_RANK[a.finding.severity] - SEVERITY_RANK[b.finding.severity];
      return rank !== 0 ? rank : a.index - b.index;
    })
    .map((entry) => entry.finding);
  return {
    findings: priority.slice(0, limit),
    hiddenCount: Math.max(0, normalized.length - limit),
  };
}

export function summarizeGuideLintArtifact(artifact, limit = GUIDE_LINT_DISPLAY_LIMIT) {
  const emptySummary = normalizeSummary(null);
  if (!isRecord(artifact)) {
    return {
      state: "malformed",
      tone: "warn",
      label: "Unexpected artifact",
      message: "The guide-lint artifact is not a JSON object.",
      summary: emptySummary,
      findings: [],
      hiddenCount: 0,
    };
  }

  if (artifact.kind !== "guide_lint") {
    return {
      state: "malformed",
      tone: "warn",
      label: "Unexpected artifact",
      message: "The artifact does not have the expected guide-lint kind.",
      summary: emptySummary,
      findings: [],
      hiddenCount: 0,
    };
  }

  if (artifact.status === "skipped") {
    return {
      state: "skipped",
      tone: "warn",
      label: "Skipped",
      message: safeLintExcerpt(artifact.safe_message || artifact.reason || "Guide lint was skipped.", 180),
      reason: safeLintExcerpt(artifact.reason, 80),
      summary: emptySummary,
      findings: [],
      hiddenCount: 0,
    };
  }

  if (artifact.status !== "completed" || !isRecord(artifact.report)) {
    return {
      state: "malformed",
      tone: "warn",
      label: "Unexpected artifact",
      message: "The guide-lint artifact is missing a completed report.",
      summary: emptySummary,
      findings: [],
      hiddenCount: 0,
    };
  }

  const summary = normalizeSummary(artifact.report.summary);
  const { findings, hiddenCount } = boundedFindings(artifact.report.findings, limit);
  const hasErrors = summary.error > 0;
  const hasWarnings = summary.warning > 0;
  let tone = "good";
  let label = "Completed";
  let message = "No structural or rendering-risk issues were found.";
  if (hasErrors) {
    tone = "bad";
    label = "Issues found";
    message = "Guide lint found likely render-breaking issues. This is a structural check, not a content-truth check.";
  } else if (hasWarnings) {
    tone = "warn";
    label = "Warnings";
    message = "Guide lint found possible structural or formatting issues. This is a structural check, not a content-truth check.";
  }
  return {
    state: "completed",
    tone,
    label,
    message,
    source: safeLintExcerpt(artifact.source || artifact.report.source_name || "clean.md", 80),
    summary,
    findings,
    hiddenCount,
  };
}
