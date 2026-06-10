// Plain-node harness for the JobDetails guide-lint artifact UI helpers.
// Run:
//
//   node scripts/verify-guide-lint.mjs

import {
  safeLintExcerpt,
  summarizeGuideLintArtifact,
} from "../src/guideLintArtifact.js";

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

const completed = {
  version: 1,
  kind: "guide_lint",
  status: "completed",
  source: "clean.md",
  report: {
    version: 1,
    source_name: "clean.md",
    summary: { total: 5, error: 1, warning: 2, info: 2 },
    findings: [
      { id: "lint_0001", rule: "empty_heading", severity: "warning", line: 3, message: "Heading has no body.", excerpt: "## Intro" },
      { id: "lint_0002", rule: "katex_skipped", severity: "info", line: 0, message: "KaTeX skipped.", excerpt: "" },
      { id: "lint_0003", rule: "unbalanced_math", severity: "error", line: 10, message: "Unbalanced '$$'.", excerpt: "$$ x" },
      { id: "lint_0004", rule: "body_row_mismatch", severity: "warning", line: 14, message: "Row column mismatch.", excerpt: "| a |" },
      { id: "lint_0005", rule: "katex_skipped", severity: "info", line: 0, message: "Render check skipped.", excerpt: "" },
    ],
  },
};

const view = summarizeGuideLintArtifact(completed, 3);
check("completed state", view.state === "completed", view.state);
check("summary counts", view.summary.total === 5 && view.summary.error === 1 && view.summary.warning === 2 && view.summary.info === 2, JSON.stringify(view.summary));
check("error tone is bad", view.tone === "bad", view.tone);
check("source surfaced", view.source === "clean.md", view.source);
check("bounds findings", view.findings.length === 3 && view.hiddenCount === 2, `${view.findings.length}/${view.hiddenCount}`);
check("prioritizes error first", view.findings[0].severity === "error", view.findings.map((f) => f.severity).join(","));
check("warnings before info", view.findings[1].severity === "warning" && view.findings[2].severity === "warning", view.findings.map((f) => f.severity).join(","));
check("keeps line number", view.findings[0].line === 10, String(view.findings[0].line));
check("normalizes rule", view.findings[0].rule === "unbalanced_math", view.findings[0].rule);

const warnOnly = summarizeGuideLintArtifact({
  ...completed,
  report: {
    ...completed.report,
    summary: { total: 1, error: 0, warning: 1, info: 0 },
    findings: [completed.report.findings[0]],
  },
});
check("warning-only tone is warn", warnOnly.tone === "warn", warnOnly.tone);

const clean = summarizeGuideLintArtifact({
  ...completed,
  report: {
    version: 1,
    source_name: "clean.md",
    summary: { total: 0, error: 0, warning: 0, info: 0 },
    findings: [],
  },
});
check("clean completed good tone", clean.tone === "good", clean.tone);
check("clean has no findings", clean.findings.length === 0 && clean.hiddenCount === 0);

const infoOnly = summarizeGuideLintArtifact({
  ...completed,
  report: {
    version: 1,
    source_name: "clean.md",
    summary: { total: 1, error: 0, warning: 0, info: 1 },
    findings: [completed.report.findings[1]],
  },
});
check("info-only tone is good", infoOnly.tone === "good", infoOnly.tone);

const skipped = summarizeGuideLintArtifact({
  version: 1,
  kind: "guide_lint",
  status: "skipped",
  reason: "lint_error",
  safe_message: "Guide lint could not be completed.",
});
check("skipped state", skipped.state === "skipped", skipped.state);
check("skipped safe message", skipped.message === "Guide lint could not be completed.", skipped.message);
check("skipped has no counts", skipped.summary.total === 0 && skipped.findings.length === 0);

check("malformed non-object", summarizeGuideLintArtifact(null).state === "malformed");
check("malformed wrong kind", summarizeGuideLintArtifact({ kind: "math_verification", status: "completed" }).state === "malformed");
check("malformed missing report", summarizeGuideLintArtifact({ kind: "guide_lint", status: "completed" }).state === "malformed");
check("unknown severity becomes info", summarizeGuideLintArtifact({
  kind: "guide_lint",
  status: "completed",
  report: { summary: { total: 1, error: 0, warning: 0, info: 0 }, findings: [{ rule: "x", severity: "bogus", line: 1, message: "m", excerpt: "e" }] },
}).findings[0].severity === "info");
check("excerpt collapses whitespace", safeLintExcerpt("a\n   b\tc") === "a b c");
check("excerpt truncates", safeLintExcerpt("x".repeat(200), 12) === "xxxxxxxxx...");

if (failed) {
  console.error(`\nGuide-lint helper checks failed: ${failed}`);
  process.exit(1);
}

console.log("\nGuide-lint helper checks passed.");
