// Plain-node harness for the JobDetails math verification artifact UI helpers.
// Run:
//
//   node scripts/verify-math-verification.mjs

import {
  safeMathExcerpt,
  summarizeMathVerificationArtifact,
} from "../src/mathVerification.js";

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
  kind: "math_verification",
  status: "completed",
  source: "clean.md",
  report: {
    version: 1,
    source_name: "clean.md",
    summary: { total: 3, ok: 1, mismatch: 1, unparseable: 1 },
    claims: [
      { id: "claim_0001", line: 10, text: "2 + 2 = 4", expression: "2 + 2", claimed: 4, computed: 4, status: "ok" },
      { id: "claim_0002", line: 12, text: "2 + 2 = 5", expression: "2 + 2", claimed: 5, computed: 4, status: "mismatch", reason: "computed value differs" },
      { id: "claim_0003", line: 14, text: "x + 2 = 5", expression: "x + 2", claimed: 5, computed: null, status: "unparseable", reason: "unknown name" },
    ],
  },
};

const view = summarizeMathVerificationArtifact(completed, 2);
check("completed state", view.state === "completed", view.state);
check("summary counts", view.summary.total === 3 && view.summary.ok === 1 && view.summary.mismatch === 1 && view.summary.unparseable === 1, JSON.stringify(view.summary));
check("issues tone", view.tone === "warn", view.tone);
check("bounds claims", view.claims.length === 2 && view.hiddenCount === 1, `${view.claims.length}/${view.hiddenCount}`);
check("prioritizes mismatch", view.claims[0].status === "mismatch", view.claims.map((claim) => claim.status).join(","));
check("keeps line number", view.claims[0].line === 12, String(view.claims[0].line));

const clean = summarizeMathVerificationArtifact({
  ...completed,
  report: {
    ...completed.report,
    summary: { total: 1, ok: 1, mismatch: 0, unparseable: 0 },
    claims: [completed.report.claims[0]],
  },
});
check("clean completed good tone", clean.tone === "good", clean.tone);

const skipped = summarizeMathVerificationArtifact({
  version: 1,
  kind: "math_verification",
  status: "skipped",
  reason: "verifier_error",
  safe_message: "Math verification skipped safely.",
});
check("skipped state", skipped.state === "skipped", skipped.state);
check("skipped has no report counts", skipped.summary.total === 0 && skipped.claims.length === 0);

check("malformed non-object", summarizeMathVerificationArtifact(null).state === "malformed");
check("malformed wrong kind", summarizeMathVerificationArtifact({ kind: "validation", status: "completed" }).state === "malformed");
check("malformed missing report", summarizeMathVerificationArtifact({ kind: "math_verification", status: "completed" }).state === "malformed");
check("excerpt collapses whitespace", safeMathExcerpt("a\n   b\tc") === "a b c");
check("excerpt truncates", safeMathExcerpt("x".repeat(200), 12) === "xxxxxxxxx...");

if (failed) {
  console.error(`\nMath verification helper checks failed: ${failed}`);
  process.exit(1);
}

console.log("\nMath verification helper checks passed.");
