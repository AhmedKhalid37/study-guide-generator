// Plain-node harness for the JobDetails "Visual advisory" panel helpers (Slice 50).
//
// Run:
//
//   node scripts/verify-job-details-visual-advisory.mjs
//
// Exercises the pure summary functions over the advisory visual artifact chain
// (manifest → scoring → replacement plan). Asserts: missing/404 is normal, valid
// artifacts yield safe COUNT-only view models, priority/candidate counts surface
// from each summary, chandra_blocked presence is reported as a boolean without raw
// detail, malformed input degrades safely, and NO raw/sensitive content (captions,
// OCR text, provider payloads, paths, URLs, tokens, data URIs, base64, image bytes)
// can ride out through any view-model field.

import {
  VISUAL_MANIFEST_ARTIFACT,
  VISUAL_SCORING_ARTIFACT,
  VISUAL_PLAN_ARTIFACT,
  isArtifactMissing,
  safeToken,
  summarizeVisualManifest,
  summarizeVisualReplacementPlan,
  summarizeVisualScoring,
} from "../src/visualAdvisoryArtifacts.js";

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

// ---- exact artifact names -------------------------------------------------
check("manifest artifact name is exact", VISUAL_MANIFEST_ARTIFACT === "visual_assets_manifest.json");
check("scoring artifact name is exact", VISUAL_SCORING_ARTIFACT === "visual_asset_scoring.json");
check("plan artifact name is exact", VISUAL_PLAN_ARTIFACT === "visual_replacement_plan.json");

// ---- isArtifactMissing ----------------------------------------------------
check("404 is treated as missing", isArtifactMissing({ status: 404 }) === true);
check("500 is not missing", isArtifactMissing({ status: 500 }) === false);
check("null error is not missing", isArtifactMissing(null) === false);
check("undefined error is not missing", isArtifactMissing(undefined) === false);

// ---- safeToken allowlist --------------------------------------------------
check("safeToken passes closed token", safeToken("no_extraction_metadata") === "no_extraction_metadata");
check("safeToken rejects path", safeToken("/home/user/secret/doc.pdf") === "unavailable");
check("safeToken rejects spaces/free text", safeToken("the cat sat on the mat") === "unavailable");
check("safeToken rejects non-string", safeToken({ a: 1 }) === "unavailable");
check("safeToken rejects over-long token", safeToken("a".repeat(60)) === "unavailable");

// ---- manifest summary -----------------------------------------------------
const manifestCompleted = {
  version: 1,
  kind: "visual_assets_manifest",
  status: "completed",
  source: "extraction_metadata.json",
  assets: [
    { asset_id: "p1", caption: "SECRET CAPTION TEXT", ocr_text: "raw ocr leak", path: "/home/x/y.png" },
  ],
  summary: {
    asset_count: 4,
    pages_with_visual_signals: 3,
    extracted_figure_count: 2,
    source_providers: ["fitz_local"],
  },
  warnings: [],
};
const mView = summarizeVisualManifest(manifestCompleted);
check("manifest completed state", mView.state === "completed");
check("manifest assetCount", mView.assetCount === 4);
check("manifest pagesWithVisualSignals", mView.pagesWithVisualSignals === 3);
check("manifest extractedFigureCount", mView.extractedFigureCount === 2);

const manifestSkipped = {
  kind: "visual_assets_manifest",
  status: "skipped",
  reason: "no_extraction_metadata",
  assets: [],
  summary: { asset_count: 0 },
  warnings: [],
};
const mSkip = summarizeVisualManifest(manifestSkipped);
check("manifest skipped state", mSkip.state === "skipped");
check("manifest skipped reason closed-vocab", mSkip.reason === "no_extraction_metadata");
check("manifest skipped counts zero", mSkip.assetCount === 0);

check("manifest malformed (not object)", summarizeVisualManifest(null).state === "malformed");
check("manifest malformed (wrong kind)", summarizeVisualManifest({ kind: "other", status: "completed" }).state === "malformed");
check(
  "manifest malformed summary fields coerce to 0",
  (() => {
    const v = summarizeVisualManifest({ kind: "visual_assets_manifest", status: "completed", summary: { asset_count: "x", pages_with_visual_signals: -3 } });
    return v.assetCount === 0 && v.pagesWithVisualSignals === 0 && v.extractedFigureCount === 0;
  })()
);

// ---- scoring summary ------------------------------------------------------
const scoringCompleted = {
  version: 1,
  kind: "visual_asset_scoring",
  status: "completed",
  scores: [{ asset_id: "p1", priority: "high", caption: "LEAK" }],
  summary: {
    asset_count: 5,
    high_priority_count: 1,
    medium_priority_count: 2,
    low_priority_count: 1,
    unknown_priority_count: 1,
  },
  warnings: [],
};
const sView = summarizeVisualScoring(scoringCompleted);
check("scoring completed state", sView.state === "completed");
check("scoring scoreCount", sView.scoreCount === 5);
check("scoring highPriorityCount", sView.highPriorityCount === 1);
check("scoring mediumPriorityCount", sView.mediumPriorityCount === 2);
check("scoring lowPriorityCount", sView.lowPriorityCount === 1);
check("scoring unknownPriorityCount", sView.unknownPriorityCount === 1);

const scoringSkipped = { kind: "visual_asset_scoring", status: "skipped", reason: "manifest_unavailable", scores: [], summary: {}, warnings: [] };
const sSkip = summarizeVisualScoring(scoringSkipped);
check("scoring skipped state", sSkip.state === "skipped");
check("scoring skipped reason closed-vocab", sSkip.reason === "manifest_unavailable");
check("scoring malformed (wrong kind)", summarizeVisualScoring({ kind: "nope", status: "completed" }).state === "malformed");

// ---- replacement plan summary ---------------------------------------------
const planCompleted = {
  version: 1,
  kind: "visual_replacement_plan",
  status: "completed",
  items: [
    { asset_id: "p1", candidate_action: "candidate_include_as_figure", reasons: ["high_priority"], source_page: 2 },
    { asset_id: "p2", candidate_action: "review_only", reasons: ["chandra_blocked"], source_page: 4 },
  ],
  summary: {
    item_count: 6,
    candidate_include_as_figure_count: 2,
    candidate_convert_to_table_count: 1,
    candidate_summarize_as_text_count: 1,
    review_only_count: 1,
    unknown_count: 1,
  },
  warnings: [],
};
const pView = summarizeVisualReplacementPlan(planCompleted);
check("plan completed state", pView.state === "completed");
check("plan itemCount", pView.itemCount === 6);
check("plan includeAsFigureCount", pView.includeAsFigureCount === 2);
check("plan convertToTableCount", pView.convertToTableCount === 1);
check("plan summarizeAsTextCount", pView.summarizeAsTextCount === 1);
check("plan reviewOnlyCount", pView.reviewOnlyCount === 1);
check("plan unknownCount", pView.unknownCount === 1);
check("plan chandra_blocked present (item reason)", pView.chandraBlockedPresent === true);

const planNoChandra = {
  kind: "visual_replacement_plan",
  status: "completed",
  items: [{ asset_id: "p1", candidate_action: "review_only", reasons: ["low_priority"] }],
  summary: { item_count: 1 },
  warnings: [],
};
check("plan chandra_blocked absent", summarizeVisualReplacementPlan(planNoChandra).chandraBlockedPresent === false);

const planChandraWarning = {
  kind: "visual_replacement_plan",
  status: "completed",
  items: [],
  summary: { item_count: 0 },
  warnings: ["chandra_blocked"],
};
check("plan chandra_blocked present (top-level warning)", summarizeVisualReplacementPlan(planChandraWarning).chandraBlockedPresent === true);

const planSkipped = { kind: "visual_replacement_plan", status: "skipped", reason: "scoring_unavailable", items: [], summary: {}, warnings: [] };
const pSkip = summarizeVisualReplacementPlan(planSkipped);
check("plan skipped state", pSkip.state === "skipped");
check("plan skipped reason closed-vocab", pSkip.reason === "scoring_unavailable");
check("plan malformed (not object)", summarizeVisualReplacementPlan(42).state === "malformed");

// ---- no raw / sensitive content leaks anywhere ----------------------------
// Serialize every produced view model and assert no caption/OCR/path/url/etc.
const allViews = [mView, mSkip, sView, sSkip, pView, pSkip, summarizeVisualReplacementPlan(planChandraWarning)];
const blob = JSON.stringify(allViews);
const FORBIDDEN = [
  ["caption text", /SECRET CAPTION TEXT/i],
  ["raw ocr", /raw ocr leak/i],
  ["leak token", /\bLEAK\b/],
  ["absolute path", /\/home\/|\/usr\/|\/etc\/|\/var\//],
  ["url", /https?:\/\//],
  ["data uri", /data:[a-z]+\/[a-z0-9.+-]+;base64,/i],
  ["bearer/token", /authorization|bearer\s|sk-[a-z0-9]/i],
];
for (const [label, re] of FORBIDDEN) {
  check(`no leak: ${label}`, !re.test(blob), `matched in: ${blob.slice(0, 120)}`);
}

if (failed === 0) {
  console.log("\nAll visual-advisory helper checks passed.");
} else {
  console.error(`\n${failed} check(s) failed.`);
  process.exit(1);
}
