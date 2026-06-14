// Plain-node harness for the JobDetails "Material coverage" display helpers (Slice 88).
//
// Run:
//
//   node scripts/verify-material-coverage-display.mjs
//
// Exercises the pure summary/model builders over the Full Material Coverage signals
// (job selection envelopes + source_coverage_report.json + visual_inclusion_plan.json).
// Asserts: exact artifact names, 404 is normal, missing reports yield a safe
// "unavailable" model, valid reports summarize counts correctly, malformed reports
// degrade safely, material selections count only safe positional attachment keys,
// hostile canaries never appear in the display model, and helpers are deterministic.
// NO raw/sensitive content (filenames, paths, captions, OCR/source/table text,
// image/asset refs, data URIs, base64, provider payloads, tokens, full URLs) can
// ride out through any view-model field.

import {
  SOURCE_COVERAGE_ARTIFACT,
  VISUAL_INCLUSION_PLAN_ARTIFACT,
  buildMaterialCoverageDisplayModel,
  isCoverageArtifactMissing,
  summarizeMaterialSelections,
  summarizeSourceCoverage,
  summarizeVisualInclusionPlan,
} from "../src/materialCoverageDisplay.js";

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
check("source coverage artifact name is exact", SOURCE_COVERAGE_ARTIFACT === "source_coverage_report.json");
check("visual inclusion plan artifact name is exact", VISUAL_INCLUSION_PLAN_ARTIFACT === "visual_inclusion_plan.json");

// ---- isCoverageArtifactMissing -------------------------------------------
check("404 is treated as missing", isCoverageArtifactMissing({ status: 404 }) === true);
check("500 is not missing", isCoverageArtifactMissing({ status: 500 }) === false);
check("null error is not missing", isCoverageArtifactMissing(null) === false);
check("undefined error is not missing", isCoverageArtifactMissing(undefined) === false);

// ---- material selections summary -----------------------------------------
const noJob = summarizeMaterialSelections(null);
check("null job -> inactive", noJob.status === "inactive" && noJob.attachmentsWithSelections === 0);

const inactiveJob = summarizeMaterialSelections({
  material_page_selections: { version: 1, attachments: {}, warnings: [] },
  material_page_selection: { version: 1, mode: "all", include_pages: [], exclude_pages: [], warnings: [] },
});
check("empty envelope -> inactive", inactiveJob.status === "inactive");
check("empty envelope -> 0 attachments", inactiveJob.attachmentsWithSelections === 0);
check("all-mode global -> not globalActive", inactiveJob.globalActive === false);

const activeJob = summarizeMaterialSelections({
  material_page_selections: {
    version: 1,
    attachments: {
      attachment_0: { version: 1, mode: "exclude", include_pages: [], exclude_pages: [2, 4, 5], warnings: [] },
      attachment_1: { version: 1, mode: "all", include_pages: [], exclude_pages: [], warnings: [] },
      attachment_2: { version: 1, mode: "include", include_pages: [3], exclude_pages: [], warnings: [] },
    },
    warnings: [],
  },
});
check("active envelope -> active", activeJob.status === "active");
check("active envelope counts only attachments with pages", activeJob.attachmentsWithSelections === 2);

const globalOnly = summarizeMaterialSelections({
  material_page_selection: { version: 1, mode: "exclude", include_pages: [], exclude_pages: [9], warnings: [] },
});
check("global exclude selection -> active", globalOnly.status === "active" && globalOnly.globalActive === true);

// Hostile / filename-like keys must NOT be counted and must not leak.
const hostileKeys = summarizeMaterialSelections({
  material_page_selections: {
    version: 1,
    attachments: {
      "private-source.pdf": { version: 1, mode: "exclude", include_pages: [], exclude_pages: [1], warnings: [] },
      "/home/example/secret.pdf": { version: 1, mode: "exclude", include_pages: [], exclude_pages: [2], warnings: [] },
      attachment_0: { version: 1, mode: "exclude", include_pages: [], exclude_pages: [3], warnings: [] },
    },
    warnings: ["attachment_key_invalid"],
  },
});
check("filename/path keys ignored, only safe key counted", hostileKeys.attachmentsWithSelections === 1);
check("hostile-key envelope reports hasWarnings", hostileKeys.hasWarnings === true);
const hostileKeysBlob = JSON.stringify(hostileKeys);
check("filename canary not in selections model", !hostileKeysBlob.includes("private-source.pdf"));
check("path canary not in selections model", !hostileKeysBlob.includes("/home/"));

const malformedSelections = summarizeMaterialSelections({ material_page_selections: "nope", material_page_selection: 42 });
check("malformed selection fields -> inactive", malformedSelections.status === "inactive");

// ---- source coverage summary ---------------------------------------------
const coverageReport = {
  version: 1,
  kind: "source_coverage_report",
  status: "partial",
  summary: {
    source_count: 2,
    pdf_source_count: 1,
    total_pages: 12,
    covered_pages: 9,
    embedded_text_pages: 7,
    ocr_pages: 2,
    empty_or_unreadable_pages: 3,
    anchor_pages: 4,
    visual_candidate_pages: 5,
  },
  sources: [],
  warnings: [],
};
const coverageView = summarizeSourceCoverage(coverageReport);
check("coverage state available", coverageView.state === "available");
check("coverage status passthrough (partial)", coverageView.status === "partial");
check("coverage tone warn for partial", coverageView.tone === "warn");
check("coverage total pages", coverageView.totalPages === 12);
check("coverage covered pages", coverageView.coveredPages === 9);
check("coverage embedded text pages", coverageView.embeddedTextPages === 7);
check("coverage ocr pages", coverageView.ocrPages === 2);
check("coverage unreadable pages", coverageView.unreadablePages === 3);
check("coverage visual candidate pages", coverageView.visualCandidatePages === 5);
check("coverage source count", coverageView.sourceCount === 2);

const completedCoverage = summarizeSourceCoverage({ ...coverageReport, status: "completed" });
check("coverage completed -> good tone", completedCoverage.tone === "good");

const skippedCoverage = summarizeSourceCoverage({ ...coverageReport, status: "skipped" });
check("coverage skipped -> skipped state", skippedCoverage.state === "skipped");

const wrongKind = summarizeSourceCoverage({ kind: "something_else", status: "completed", summary: {} });
check("coverage wrong kind -> malformed", wrongKind.state === "malformed" && wrongKind.status === "unknown");

const malformedCoverage = summarizeSourceCoverage(null);
check("coverage null -> malformed, zero counts", malformedCoverage.state === "malformed" && malformedCoverage.totalPages === 0);

// Hostile status string + negative/garbage counts must degrade, not echo.
const hostileCoverage = summarizeSourceCoverage({
  kind: "source_coverage_report",
  status: "DROP TABLE pages; /home/secret.pdf",
  summary: { total_pages: -5, covered_pages: "9; rm -rf", ocr_pages: 3.9 },
});
check("hostile coverage status -> unknown", hostileCoverage.status === "unknown");
check("negative count clamped to 0", hostileCoverage.totalPages === 0);
check("non-numeric count clamped to 0", hostileCoverage.coveredPages === 0);
check("float count floored", hostileCoverage.ocrPages === 3);
const hostileCoverageBlob = JSON.stringify(hostileCoverage);
check("hostile coverage status text not echoed", !hostileCoverageBlob.includes("DROP TABLE") && !hostileCoverageBlob.includes("/home/"));

// ---- visual inclusion plan summary ----------------------------------------
const plan = {
  version: 1,
  kind: "visual_inclusion_plan",
  status: "completed",
  summary: {
    source_count: 1,
    candidate_count: 10,
    planned_count: 6,
    non_table_planned_count: 6,
    table_like_skipped_count: 3,
    unsafe_or_incomplete_skipped_count: 1,
    page_count_with_planned_visuals: 4,
  },
  items: [],
  warnings: [],
};
const planView = summarizeVisualInclusionPlan(plan);
check("plan state available", planView.state === "available");
check("plan completed -> good tone", planView.tone === "good");
check("plan candidate count", planView.candidateCount === 10);
check("plan planned useful count", planView.plannedUsefulCount === 6);
check("plan table-like skipped count", planView.tableLikeSkippedCount === 3);
check("plan unsafe skipped count", planView.unsafeSkippedCount === 1);
check("plan pages with planned visuals", planView.pagesWithPlannedVisuals === 4);
check("plan source count", planView.sourceCount === 1);

const skippedPlan = summarizeVisualInclusionPlan({ ...plan, status: "skipped" });
check("plan skipped -> skipped state", skippedPlan.state === "skipped");

const wrongPlanKind = summarizeVisualInclusionPlan({ kind: "nope", status: "completed", summary: {} });
check("plan wrong kind -> malformed", wrongPlanKind.state === "malformed");

const malformedPlan = summarizeVisualInclusionPlan(undefined);
check("plan undefined -> malformed, zero counts", malformedPlan.state === "malformed" && malformedPlan.candidateCount === 0);

// ---- composite display model ----------------------------------------------
const fullModel = buildMaterialCoverageDisplayModel({
  job: activeJob && {
    material_page_selections: {
      version: 1,
      attachments: { attachment_0: { version: 1, mode: "exclude", include_pages: [], exclude_pages: [2], warnings: [] } },
      warnings: [],
    },
  },
  sourceCoverageReport: coverageReport,
  visualInclusionPlan: plan,
});
check("model has selections section", fullModel.selections.status === "active");
check("model has source coverage section", fullModel.sourceCoverage.state === "available");
check("model has visual coverage section", fullModel.visualCoverage.state === "available");
check("model table policy is deferred/core_available", fullModel.tablePolicy.state === "core_available");
check("model table policy note is static safe text", fullModel.tablePolicy.note === "Policy core available; table reconstruction not yet enabled.");
check("model marks coverage artifact available", fullModel.artifacts.sourceCoverageReportAvailable === true);
check("model marks plan artifact available", fullModel.artifacts.visualInclusionPlanAvailable === true);

const emptyModel = buildMaterialCoverageDisplayModel({});
check("empty model selections inactive", emptyModel.selections.status === "inactive");
check("empty model source coverage unavailable", emptyModel.sourceCoverage.state === "unavailable");
check("empty model visual coverage unavailable", emptyModel.visualCoverage.state === "unavailable");
check("empty model coverage artifact flag false", emptyModel.artifacts.sourceCoverageReportAvailable === false);
check("empty model plan artifact flag false", emptyModel.artifacts.visualInclusionPlanAvailable === false);

// Missing reports (404 → null passed in) are NEVER errors, just unavailable.
const partialModel = buildMaterialCoverageDisplayModel({ job: null, sourceCoverageReport: coverageReport, visualInclusionPlan: null });
check("partial model: coverage available", partialModel.sourceCoverage.state === "available");
check("partial model: plan unavailable", partialModel.visualCoverage.state === "unavailable");

// Hostile canaries embedded in fake reports must not surface in the model.
const hostileModel = buildMaterialCoverageDisplayModel({
  job: {
    material_page_selections: {
      version: 1,
      attachments: { "leak.pdf": { mode: "exclude", exclude_pages: [1], warnings: [] } },
      warnings: [],
    },
  },
  sourceCoverageReport: {
    kind: "source_coverage_report",
    status: "completed",
    summary: { total_pages: 3, covered_pages: 3 },
    sources: [{ caption: "data:image/png;base64,QQQQ", title: "/home/example/private-source.pdf" }],
    warnings: ["https://evil.example/leak"],
  },
  visualInclusionPlan: {
    kind: "visual_inclusion_plan",
    status: "completed",
    summary: { candidate_count: 1, non_table_planned_count: 1 },
    items: [{ caption: "secret caption text", source_filename: "private-source.pdf" }],
    warnings: ["sk-canarytoken1234567890"],
  },
});
const hostileModelBlob = JSON.stringify(hostileModel);
check("hostile model: no filename canary", !hostileModelBlob.includes("private-source.pdf") && !hostileModelBlob.includes("leak.pdf"));
check("hostile model: no path canary", !hostileModelBlob.includes("/home/"));
check("hostile model: no data URI canary", !hostileModelBlob.includes("data:") && !hostileModelBlob.includes("base64"));
check("hostile model: no URL canary", !hostileModelBlob.includes("https://") && !hostileModelBlob.includes("evil.example"));
check("hostile model: no token canary", !hostileModelBlob.includes("sk-canarytoken1234567890"));
check("hostile model: no caption text", !hostileModelBlob.includes("secret caption text"));
check("hostile model: still summarizes safe counts", hostileModel.sourceCoverage.totalPages === 3 && hostileModel.visualCoverage.candidateCount === 1);

// ---- determinism ----------------------------------------------------------
const once = JSON.stringify(buildMaterialCoverageDisplayModel({ job: { material_page_selections: { version: 1, attachments: { attachment_0: { mode: "exclude", exclude_pages: [1] } }, warnings: [] } }, sourceCoverageReport: coverageReport, visualInclusionPlan: plan }));
const twice = JSON.stringify(buildMaterialCoverageDisplayModel({ job: { material_page_selections: { version: 1, attachments: { attachment_0: { mode: "exclude", exclude_pages: [1] } }, warnings: [] } }, sourceCoverageReport: coverageReport, visualInclusionPlan: plan }));
check("deterministic identical model on repeat", once === twice);

if (failed > 0) {
  console.error(`\n${failed} material-coverage-display check(s) failed.`);
  process.exit(1);
}
console.log("\nAll material-coverage-display helper checks passed.");
