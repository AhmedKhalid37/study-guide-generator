// Plain-node harness for the JobDetails FINAL "Material coverage" helpers (Slice 97).
//
// Run:
//
//   node scripts/verify-material-coverage-final-panel.mjs
//
// Exercises the new pure summarizers + composite final-model builder over the safe
// exact-name coverage artifacts (table candidates manifest, table reconstruction
// policy, guide quality report v2) on top of the Slice 88/89 source/visual model.
// Asserts: exact artifact names, valid artifacts summarize counts/statuses, the
// screenshot-insert count is always 0/"not used", guide-quality check statuses are
// summarized without exposing image refs, malformed/missing artifacts degrade to
// calm unavailable states, hostile canaries never survive into the serialized model,
// artifact links are fixed exact-name URLs only, the older Slice 88/89 model still
// works, and output is deterministic. NO raw/sensitive content (filenames, paths,
// source titles, document/OCR/caption/table text, image/asset refs, data URIs,
// base64, provider payloads, tokens, full URLs, raw errors) can ride out through any
// view-model field.

import {
  SOURCE_COVERAGE_ARTIFACT,
  VISUAL_INCLUSION_PLAN_ARTIFACT,
  TABLE_CANDIDATES_MANIFEST_ARTIFACT,
  TABLE_RECONSTRUCTION_POLICY_ARTIFACT,
  GUIDE_QUALITY_REPORT_V2_ARTIFACT,
  buildMaterialCoverageDisplayModel,
  buildMaterialCoverageFinalModel,
  summarizeTableCandidatesManifest,
  summarizeTableReconstructionPolicy,
  summarizeGuideQualityReportV2,
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
check("table candidates manifest artifact name is exact", TABLE_CANDIDATES_MANIFEST_ARTIFACT === "table_candidates_manifest.json");
check("table reconstruction policy artifact name is exact", TABLE_RECONSTRUCTION_POLICY_ARTIFACT === "table_reconstruction_policy.json");
check("guide quality report v2 artifact name is exact", GUIDE_QUALITY_REPORT_V2_ARTIFACT === "guide_quality_report_v2.json");

// ---- synthetic artifact builders (mirror the sanitized backend shapes) -----
function tableManifest(overrides = {}) {
  return {
    version: 1,
    kind: "table_candidates_manifest",
    status: "completed",
    summary: {
      source_count: 1,
      candidate_count: 9,
      table_like_candidate_count: 4,
      skipped_non_table_count: 5,
      unsafe_or_incomplete_skipped_count: 1,
      page_count_with_table_candidates: 3,
      ...overrides,
    },
    candidates: [],
    warnings: [],
  };
}

function tablePolicy(overrides = {}) {
  return {
    version: 1,
    kind: "table_reconstruction_policy",
    status: "completed",
    summary: {
      candidate_count: 4,
      policy_item_count: 4,
      reconstruct_with_original_count: 1,
      simplify_only_count: 1,
      defer_count: 1,
      skip_unreadable_count: 1,
      skip_unsafe_count: 0,
      screenshot_insert_count: 0,
      ...overrides,
    },
    items: [],
    warnings: [],
  };
}

function guideQuality(overrides = {}) {
  const summary = {
    guide_present: true,
    source_page_signal_count: 7,
    unique_source_page_signal_count: 5,
    safe_image_ref_count: 3,
    planned_visual_count: 4,
    table_candidate_count: 4,
    table_policy_item_count: 4,
    missing_material_item_count: 2,
    coverage_signal_count: 6,
    warning_count: 1,
    ...(overrides.summary || {}),
  };
  return {
    version: 2,
    kind: "guide_quality_report",
    status: overrides.status || "completed",
    summary,
    checks: overrides.checks || [
      { check_id: "guide_quality_check_0001", kind: "source_pages", status: "passed", observed_count: 7, expected_count: 5, instruction: "secret instruction text", warnings: [] },
      { check_id: "guide_quality_check_0002", kind: "visuals", status: "warning", observed_count: 3, expected_count: 4, instruction: "secret instruction text", warnings: ["visual_signal_missing"] },
      { check_id: "guide_quality_check_0003", kind: "tables", status: "passed", observed_count: 1, expected_count: 4, instruction: "secret instruction text", warnings: [] },
      { check_id: "guide_quality_check_0004", kind: "missing_material", status: "not_applicable", observed_count: 0, expected_count: 0, instruction: "secret instruction text", warnings: [] },
      { check_id: "guide_quality_check_0005", kind: "coverage", status: "passed", observed_count: 6, expected_count: 6, instruction: "secret instruction text", warnings: [] },
    ],
    warnings: overrides.warnings || ["visual_signal_missing"],
  };
}

// ---- table candidates manifest summary ------------------------------------
const tcView = summarizeTableCandidatesManifest(tableManifest());
check("manifest available", tcView.state === "available" && tcView.status === "completed");
check("manifest table-like count", tcView.tableLikeCandidateCount === 4);
check("manifest candidate count", tcView.candidateCount === 9);
check("manifest skipped non-table count", tcView.skippedNonTableCount === 5);
check("manifest unsafe/incomplete count", tcView.unsafeOrIncompleteSkippedCount === 1);
check("manifest pages with candidates", tcView.pagesWithTableCandidates === 3);

const tcSkipped = summarizeTableCandidatesManifest(tableManifest({}) && { ...tableManifest(), status: "skipped" });
check("manifest skipped -> skipped state", tcSkipped.state === "skipped");

const tcWrongKind = summarizeTableCandidatesManifest({ kind: "nope", status: "completed", summary: {} });
check("manifest wrong kind -> malformed", tcWrongKind.state === "malformed" && tcWrongKind.status === "unknown");

const tcNull = summarizeTableCandidatesManifest(null);
check("manifest null -> malformed, zero counts", tcNull.state === "malformed" && tcNull.tableLikeCandidateCount === 0);

// Hostile counts must clamp, hostile status must degrade.
const tcHostile = summarizeTableCandidatesManifest({
  kind: "table_candidates_manifest",
  status: "DROP TABLE; /home/secret.pdf",
  summary: { table_like_candidate_count: -3, candidate_count: "9; rm -rf" },
});
check("manifest hostile status -> unknown", tcHostile.status === "unknown");
check("manifest negative count clamped", tcHostile.tableLikeCandidateCount === 0);
check("manifest non-numeric count clamped", tcHostile.candidateCount === 0);
check("manifest hostile status not echoed", !JSON.stringify(tcHostile).includes("DROP TABLE") && !JSON.stringify(tcHostile).includes("/home/"));

// ---- table reconstruction policy summary ----------------------------------
const tpView = summarizeTableReconstructionPolicy(tablePolicy());
check("policy available", tpView.state === "available" && tpView.status === "completed");
check("policy item count", tpView.policyItemCount === 4);
check("policy reconstruct count", tpView.reconstructWithOriginalCount === 1);
check("policy simplify count", tpView.simplifyOnlyCount === 1);
check("policy defer count", tpView.deferCount === 1);
check("policy skip unreadable count", tpView.skipUnreadableCount === 1);
check("policy skip unsafe count", tpView.skipUnsafeCount === 0);
check("policy screenshot insert count is 0", tpView.screenshotInsertCount === 0);

// Even a tampered screenshot count must never display > 0 as a negative; a positive
// tampered value clamps to a non-negative int (the panel still labels it honestly).
const tpTampered = summarizeTableReconstructionPolicy(tablePolicy({ screenshot_insert_count: -5 }));
check("policy tampered negative screenshot clamps to 0", tpTampered.screenshotInsertCount === 0);

const tpWrongKind = summarizeTableReconstructionPolicy({ kind: "nope", status: "completed", summary: {} });
check("policy wrong kind -> malformed", tpWrongKind.state === "malformed");

const tpNull = summarizeTableReconstructionPolicy(undefined);
check("policy undefined -> malformed, zero counts", tpNull.state === "malformed" && tpNull.policyItemCount === 0 && tpNull.screenshotInsertCount === 0);

// ---- guide quality report v2 summary --------------------------------------
const gqView = summarizeGuideQualityReportV2(guideQuality());
check("guide quality available", gqView.state === "available" && gqView.status === "completed");
check("guide quality guidePresent", gqView.guidePresent === true);
check("guide quality warning count", gqView.warningCount === 1);
check("guide quality observed image ref count", gqView.safeImageRefCount === 3);
check("guide quality planned visual count", gqView.plannedVisualCount === 4);
check("guide quality missing-material item count", gqView.missingMaterialItemCount === 2);
check("guide quality coverage signal count", gqView.coverageSignalCount === 6);
check("guide quality source-pages check", gqView.checks.source_pages === "passed");
check("guide quality visuals check (warning)", gqView.checks.visuals === "warning");
check("guide quality tables check", gqView.checks.tables === "passed");
check("guide quality missing-material check", gqView.checks.missing_material === "not_applicable");
check("guide quality coverage check", gqView.checks.coverage === "passed");

// The report's per-check `instruction` strings and `check_id`s must NOT ride out.
const gqBlob = JSON.stringify(gqView);
check("guide quality: no instruction text surfaced", !gqBlob.includes("secret instruction text") && !gqBlob.includes("instruction"));
check("guide quality: no check_id surfaced", !gqBlob.includes("guide_quality_check_"));

// Observed/expected visual counts come from the report without exposing image refs.
const gqWithRefs = summarizeGuideQualityReportV2(
  guideQuality({
    summary: { safe_image_ref_count: 2 },
    checks: [
      { check_id: "guide_quality_check_0002", kind: "visuals", status: "passed", observed_count: 2, expected_count: 2, instruction: "x" },
    ],
  })
);
check("guide quality observed refs from report (count only)", gqWithRefs.safeImageRefCount === 2);
const gqRefsBlob = JSON.stringify(gqWithRefs);
check("guide quality: no asset/image ref string", !gqRefsBlob.includes("assets/") && !gqRefsBlob.includes(".png"));

// Skipped/malformed guide-quality reports degrade safely.
const gqSkipped = summarizeGuideQualityReportV2(guideQuality({ status: "skipped" }));
check("guide quality skipped -> skipped state", gqSkipped.state === "skipped");
const gqWrongKind = summarizeGuideQualityReportV2({ kind: "nope", status: "completed", summary: {} });
check("guide quality wrong kind -> malformed", gqWrongKind.state === "malformed");
check("guide quality malformed -> all checks unknown", gqWrongKind.checks.source_pages === "unknown" && gqWrongKind.checks.coverage === "unknown");
const gqNoChecks = summarizeGuideQualityReportV2({ kind: "guide_quality_report", status: "completed", summary: { warning_count: 0 } });
check("guide quality missing checks -> all unknown", gqNoChecks.checks.visuals === "unknown" && gqNoChecks.checks.tables === "unknown");

// Hostile check kind / status values must not leak and must degrade.
const gqHostile = summarizeGuideQualityReportV2({
  kind: "guide_quality_report",
  status: "completed",
  summary: { warning_count: -2, safe_image_ref_count: "3; rm -rf" },
  checks: [
    { kind: "visuals", status: "data:image/png;base64,QQQ" },
    { kind: "../escape", status: "passed" },
  ],
});
check("guide quality hostile warning count clamped", gqHostile.warningCount === 0);
check("guide quality hostile image ref count clamped", gqHostile.safeImageRefCount === 0);
check("guide quality hostile check status -> unknown", gqHostile.checks.visuals === "unknown");
const gqHostileBlob = JSON.stringify(gqHostile);
check("guide quality hostile: no data URI", !gqHostileBlob.includes("data:") && !gqHostileBlob.includes("base64"));
check("guide quality hostile: no traversal token", !gqHostileBlob.includes("../escape"));

// ---- composite FINAL model -------------------------------------------------
const fullModel = buildMaterialCoverageFinalModel({
  job: {
    material_page_selections: {
      version: 1,
      attachments: { attachment_0: { mode: "exclude", exclude_pages: [2], warnings: [] } },
      warnings: [],
    },
  },
  sourceCoverageReport: { kind: "source_coverage_report", status: "completed", summary: { total_pages: 5, covered_pages: 5 } },
  visualInclusionPlan: { kind: "visual_inclusion_plan", status: "completed", summary: { candidate_count: 3, non_table_planned_count: 2 } },
  tableCandidatesManifest: tableManifest(),
  tableReconstructionPolicy: tablePolicy(),
  guideQualityReportV2: guideQuality(),
});
check("final model: selections active", fullModel.selections.status === "active");
check("final model: source coverage available", fullModel.sourceCoverage.state === "available");
check("final model: visual coverage available", fullModel.visualCoverage.state === "available");
check("final model: table candidates available", fullModel.tableCandidates.state === "available");
check("final model: table policy available", fullModel.tableReconstructionPolicy.state === "available");
check("final model: guide quality available", fullModel.guideQuality.state === "available");
check("final model: screenshot insert is 0", fullModel.tableReconstructionPolicy.screenshotInsertCount === 0);
check("final model: artifact flags set", fullModel.artifacts.tableCandidatesManifestAvailable === true && fullModel.artifacts.tableReconstructionPolicyAvailable === true && fullModel.artifacts.guideQualityReportV2Available === true);
// Slice 88 fields preserved (backward compat).
check("final model: keeps Slice 88 tablePolicy note", fullModel.tablePolicy && fullModel.tablePolicy.state === "core_available");
check("final model: keeps Slice 88 artifact flags", fullModel.artifacts.sourceCoverageReportAvailable === true && fullModel.artifacts.visualInclusionPlanAvailable === true);

// All artifacts missing -> stable model with calm unavailable states.
const emptyFinal = buildMaterialCoverageFinalModel({});
check("empty final: selections inactive", emptyFinal.selections.status === "inactive");
check("empty final: source coverage unavailable", emptyFinal.sourceCoverage.state === "unavailable");
check("empty final: visual coverage unavailable", emptyFinal.visualCoverage.state === "unavailable");
check("empty final: table candidates unavailable", emptyFinal.tableCandidates.state === "unavailable");
check("empty final: table policy unavailable", emptyFinal.tableReconstructionPolicy.state === "unavailable");
check("empty final: guide quality unavailable", emptyFinal.guideQuality.state === "unavailable");
check("empty final: artifact flags false", emptyFinal.artifacts.tableCandidatesManifestAvailable === false && emptyFinal.artifacts.guideQualityReportV2Available === false);

// Malformed artifacts degrade safely inside the final model.
const malformedFinal = buildMaterialCoverageFinalModel({
  tableCandidatesManifest: { kind: "nope" },
  tableReconstructionPolicy: 12345,
  guideQualityReportV2: ["nope"],
});
check("malformed final: table candidates malformed", malformedFinal.tableCandidates.state === "malformed");
check("malformed final: table policy malformed", malformedFinal.tableReconstructionPolicy.state === "malformed");
check("malformed final: guide quality malformed", malformedFinal.guideQuality.state === "malformed");

// ---- hostile canaries never survive the serialized final model ------------
const hostileFinal = buildMaterialCoverageFinalModel({
  job: {
    material_page_selections: {
      version: 1,
      attachments: { "private-source.pdf": { mode: "exclude", exclude_pages: [1] } },
      warnings: ["attachment_key_invalid"],
    },
  },
  sourceCoverageReport: {
    kind: "source_coverage_report",
    status: "completed",
    summary: { total_pages: 2, covered_pages: 2 },
    sources: [{ title: "/home/example/private-source.pdf", caption: "data:image/png;base64,QQQQ" }],
    warnings: ["https://evil.example/leak"],
  },
  tableCandidatesManifest: {
    kind: "table_candidates_manifest",
    status: "completed",
    summary: { table_like_candidate_count: 1 },
    candidates: [{ table_text: "secret table cell text", caption: "leaky caption" }],
    warnings: ["sk-canarytoken1234567890"],
  },
  tableReconstructionPolicy: {
    kind: "table_reconstruction_policy",
    status: "completed",
    summary: { policy_item_count: 1, screenshot_insert_count: 0 },
    items: [{ original_text: "raw table contents here", source_filename: "private-source.pdf" }],
    warnings: ["/etc/passwd"],
  },
  guideQualityReportV2: {
    kind: "guide_quality_report",
    status: "completed",
    summary: { warning_count: 1, safe_image_ref_count: 1 },
    checks: [{ kind: "visuals", status: "warning", instruction: "leaky instruction", check_id: "guide_quality_check_0002", warnings: ["visual_signal_missing"] }],
    warnings: ["assets/secret-figure.png"],
  },
});
const hostileBlob = JSON.stringify(hostileFinal);
check("hostile final: no filename canary", !hostileBlob.includes("private-source.pdf"));
check("hostile final: no path canary", !hostileBlob.includes("/home/") && !hostileBlob.includes("/etc/passwd"));
check("hostile final: no data URI canary", !hostileBlob.includes("data:") && !hostileBlob.includes("base64"));
check("hostile final: no URL canary", !hostileBlob.includes("https://") && !hostileBlob.includes("evil.example"));
check("hostile final: no token canary", !hostileBlob.includes("sk-canarytoken1234567890"));
check("hostile final: no table text", !hostileBlob.includes("secret table cell text") && !hostileBlob.includes("raw table contents"));
check("hostile final: no caption text", !hostileBlob.includes("leaky caption"));
check("hostile final: no instruction text", !hostileBlob.includes("leaky instruction") && !hostileBlob.includes("instruction"));
check("hostile final: no asset/image ref", !hostileBlob.includes("assets/secret-figure.png") && !hostileBlob.includes(".png"));
check("hostile final: no check_id", !hostileBlob.includes("guide_quality_check_"));
check("hostile final: still summarizes safe counts", hostileFinal.tableCandidates.tableLikeCandidateCount === 1 && hostileFinal.guideQuality.safeImageRefCount === 1);

// Closed-types-only deep walk: no leaky string values anywhere in the model.
const LEAKY = [/\/home\//, /\/etc\//, /https?:\/\//, /data:/, /base64/, /\.png/, /\.pdf/, /sk-/, /instruction/, /guide_quality_check_/];
function walk(node, path, leaks) {
  if (node === null) return;
  if (typeof node === "string") {
    for (const rx of LEAKY) {
      if (rx.test(node)) leaks.push(`${path}: ${node.slice(0, 40)}`);
    }
  } else if (Array.isArray(node)) {
    node.forEach((v, i) => walk(v, `${path}[${i}]`, leaks));
  } else if (typeof node === "object") {
    for (const [k, v] of Object.entries(node)) walk(v, `${path}.${k}`, leaks);
  }
}
const deepLeaks = [];
walk(hostileFinal, "model", deepLeaks);
check("hostile final: deep walk no leaks", deepLeaks.length === 0, deepLeaks.slice(0, 4).join("; "));

// ---- older Slice 88/89 model behaviour still works ------------------------
const legacy = buildMaterialCoverageDisplayModel({
  job: null,
  sourceCoverageReport: { kind: "source_coverage_report", status: "completed", summary: { total_pages: 3, covered_pages: 3 } },
  visualInclusionPlan: null,
});
check("legacy model still builds", legacy.sourceCoverage.state === "available" && legacy.visualCoverage.state === "unavailable");
check("legacy model has Slice 88 tablePolicy note", legacy.tablePolicy.state === "core_available");

// ---- determinism ----------------------------------------------------------
const args = {
  job: { material_page_selections: { version: 1, attachments: { attachment_0: { mode: "exclude", exclude_pages: [1] } }, warnings: [] } },
  sourceCoverageReport: { kind: "source_coverage_report", status: "completed", summary: { total_pages: 4, covered_pages: 4 } },
  visualInclusionPlan: { kind: "visual_inclusion_plan", status: "completed", summary: { candidate_count: 2, non_table_planned_count: 1 } },
  tableCandidatesManifest: tableManifest(),
  tableReconstructionPolicy: tablePolicy(),
  guideQualityReportV2: guideQuality(),
};
const once = JSON.stringify(buildMaterialCoverageFinalModel(args));
const twice = JSON.stringify(buildMaterialCoverageFinalModel(args));
check("deterministic identical final model on repeat", once === twice);

if (failed > 0) {
  console.error(`\n${failed} material-coverage-final-panel check(s) failed.`);
  process.exit(1);
}
console.log("\nAll material-coverage-final-panel helper checks passed.");
