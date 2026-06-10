export const MATH_VERIFICATION_ARTIFACT = "math_verification.json";
export const MATH_VERIFICATION_DISPLAY_LIMIT = 8;

const SUMMARY_KEYS = ["total", "ok", "mismatch", "unparseable"];
const KNOWN_STATUSES = new Set(["ok", "mismatch", "unparseable"]);

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

export function safeMathExcerpt(value, maxLength = 160) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

function claimStatus(claim) {
  const status = typeof claim?.status === "string" ? claim.status : "";
  return KNOWN_STATUSES.has(status) ? status : "unparseable";
}

function normalizeClaim(claim, index) {
  const status = claimStatus(claim);
  const text = safeMathExcerpt(claim?.text || claim?.expression || `Claim ${index + 1}`);
  return {
    id: typeof claim?.id === "string" && claim.id ? claim.id : `claim_${String(index + 1).padStart(4, "0")}`,
    line: Number.isFinite(claim?.line) && claim.line > 0 ? Math.floor(claim.line) : null,
    status,
    text,
    expression: safeMathExcerpt(claim?.expression),
    claimed: claim?.claimed === null || claim?.claimed === undefined ? "" : safeMathExcerpt(claim.claimed, 48),
    computed: claim?.computed === null || claim?.computed === undefined ? "" : safeMathExcerpt(claim.computed, 48),
    reason: safeMathExcerpt(claim?.reason, 120),
  };
}

function boundedClaims(claims, limit = MATH_VERIFICATION_DISPLAY_LIMIT) {
  if (!Array.isArray(claims)) {
    return { claims: [], hiddenCount: 0 };
  }
  const normalized = claims.map(normalizeClaim);
  const priority = normalized
    .filter((claim) => claim.status !== "ok")
    .concat(normalized.filter((claim) => claim.status === "ok"));
  return {
    claims: priority.slice(0, limit),
    hiddenCount: Math.max(0, normalized.length - limit),
  };
}

export function summarizeMathVerificationArtifact(artifact, limit = MATH_VERIFICATION_DISPLAY_LIMIT) {
  const emptySummary = normalizeSummary(null);
  if (!isRecord(artifact)) {
    return {
      state: "malformed",
      tone: "warn",
      label: "Unexpected artifact",
      message: "The math verification artifact is not a JSON object.",
      summary: emptySummary,
      claims: [],
      hiddenCount: 0,
    };
  }

  if (artifact.kind !== "math_verification") {
    return {
      state: "malformed",
      tone: "warn",
      label: "Unexpected artifact",
      message: "The artifact does not have the expected math verification kind.",
      summary: emptySummary,
      claims: [],
      hiddenCount: 0,
    };
  }

  if (artifact.status === "skipped") {
    return {
      state: "skipped",
      tone: "warn",
      label: "Skipped",
      message: safeMathExcerpt(artifact.safe_message || artifact.reason || "Math verification was skipped.", 180),
      reason: safeMathExcerpt(artifact.reason, 80),
      summary: emptySummary,
      claims: [],
      hiddenCount: 0,
    };
  }

  if (artifact.status !== "completed" || !isRecord(artifact.report)) {
    return {
      state: "malformed",
      tone: "warn",
      label: "Unexpected artifact",
      message: "The math verification artifact is missing a completed report.",
      summary: emptySummary,
      claims: [],
      hiddenCount: 0,
    };
  }

  const summary = normalizeSummary(artifact.report.summary);
  const { claims, hiddenCount } = boundedClaims(artifact.report.claims, limit);
  const hasIssues = summary.mismatch > 0 || summary.unparseable > 0;
  return {
    state: "completed",
    tone: hasIssues ? "warn" : "good",
    label: hasIssues ? "Issues found" : "Completed",
    message: hasIssues
      ? "Numeric verification found mismatches or unparseable claims."
      : "Numeric verification completed without mismatches.",
    source: safeMathExcerpt(artifact.source || artifact.report.source_name || "clean.md", 80),
    summary,
    claims,
    hiddenCount,
  };
}
