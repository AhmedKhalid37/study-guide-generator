// Plain-node harness for the JobDetails "Guide Quality" panel helpers (Slice 104).
//
// Run:
//
//   node scripts/verify-guide-quality-panel.mjs
//
// Exercises the pure summarizers + composite panel-model builder over the safe
// exact-name guide-quality artifacts (QA gate, prompt-contract lint, guide quality
// report v2, math verification, source coverage report). Asserts: exact artifact
// names, valid artifacts summarize counts/statuses, missing/malformed artifacts
// degrade to calm "unavailable"/"malformed" states, hostile canaries never survive
// into the serialized display model, artifact links are fixed exact-name labels
// only, math verification is summarized as COUNTS only (no formulas/values/claim
// text), and output is deterministic. NO raw/sensitive content (filenames, paths,
// source titles, guide excerpts, formulas, numeric values, OCR/caption/table text,
// image/asset refs, data URIs, base64, provider payloads, tokens, full URLs, raw
// errors) can ride out through any view-model field.

import {
  GUIDE_QUALITY_QA_GATE_ARTIFACT,
  GUIDE_QUALITY_CONTRACT_LINT_ARTIFACT,
  GUIDE_QUALITY_REPORT_V2_ARTIFACT,
  GUIDE_QUALITY_RUBRIC_SCORE_ARTIFACT,
  MATH_VERIFICATION_ARTIFACT,
  SOURCE_COVERAGE_ARTIFACT,
  GUIDE_QUALITY_ARTIFACT_LABELS,
  summarizeGuideQualityQaGate,
  summarizeGuideQualityContractLint,
  summarizeMathVerificationArtifact,
  summarizeGuideQualityRubricScore,
  summarizeGuideQualityPanelModel,
} from "../src/guideQualityDisplay.js";

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
check("qa gate artifact name is exact", GUIDE_QUALITY_QA_GATE_ARTIFACT === "guide_quality_qa_gate.json");
check("contract lint artifact name is exact", GUIDE_QUALITY_CONTRACT_LINT_ARTIFACT === "guide_quality_contract_lint.json");
check("report v2 artifact name is exact", GUIDE_QUALITY_REPORT_V2_ARTIFACT === "guide_quality_report_v2.json");
check("rubric score artifact name is exact", GUIDE_QUALITY_RUBRIC_SCORE_ARTIFACT === "guide_quality_rubric_score.json");
check("math verification artifact name is exact", MATH_VERIFICATION_ARTIFACT === "math_verification.json");
check("source coverage artifact name is exact", SOURCE_COVERAGE_ARTIFACT === "source_coverage_report.json");

// ---- hostile canaries embedded into every string-bearing input position ----
const CANARY_FILENAME = "private-source.pdf";
const CANARY_TITLE = "Quarterly Private Plan";
const CANARY_FORMULA = "E=mc^2_private";
const CANARY_VALUE = "42.0000001_secret";
const CANARY_ERROR = "Traceback (most recent call last): boom at /home/secret/x.py";
const CANARY_KEY = "sk_guidequalitypanelcanary1234567890";
const CANARY_URL = "https://secret.example.com/leak";
const CANARY_OCR = "private OCR dump words";
const CANARY_TABLE = "private table cell";
const CANARY_CAPTION = "private figure caption";
const CANARY_SPEC = "uploaded quality spec evidence";
const FORBIDDEN_CANARIES = [
  CANARY_FILENAME, CANARY_TITLE, CANARY_FORMULA, CANARY_VALUE, CANARY_ERROR, CANARY_KEY, CANARY_URL,
  CANARY_OCR, CANARY_TABLE, CANARY_CAPTION, CANARY_SPEC,
];

const KEYLIKE = /(sk-|sk_)[A-Za-z0-9_\-]{16,}/;
const PATHLIKE = /(\/home\/|\/usr\/|\/etc\/|\/var\/|\/tmp\/|[A-Za-z]:\\)/;
const URLLIKE = /https?:\/\//;
const DATA_OR_BASE64 = /(data:|base64|[A-Za-z0-9+/]{120,}={0,2})/;
const FORBIDDEN_KEYS = new Set([
  "filename", "path", "title", "text", "ocr_text", "caption", "table_text",
  "image_ref", "asset_ref", "url", "argv", "socket", "bytes", "excerpt",
  "formula", "claims", "claim", "expression", "reason", "claimed", "computed",
  "note", "raw", "instruction", "instructions", "description", "warnings", "message", "error",
]);

function scanForLeak(node, path = "") {
  if (node && typeof node === "object" && !Array.isArray(node)) {
    for (const [key, value] of Object.entries(node)) {
      if (FORBIDDEN_KEYS.has(String(key).toLowerCase())) {
        return `${path}.${key} (forbidden field name)`;
      }
      const found = scanForLeak(value, `${path}.${key}`);
      if (found) return found;
    }
  } else if (Array.isArray(node)) {
    for (let i = 0; i < node.length; i += 1) {
      const found = scanForLeak(node[i], `${path}[${i}]`);
      if (found) return found;
    }
  } else if (typeof node === "string") {
    for (const canary of FORBIDDEN_CANARIES) {
      if (node.includes(canary)) return `${path} (canary: ${canary})`;
    }
    for (const [label, re] of [
      ["keylike", KEYLIKE], ["pathlike", PATHLIKE], ["urllike", URLLIKE], ["data/base64", DATA_OR_BASE64],
    ]) {
      if (re.test(node)) return `${path} (${label}: ${node.slice(0, 40)})`;
    }
  }
  return null;
}

function noLeak(name, model) {
  const found = scanForLeak(model);
  check(`${name}: no leak`, found === null, found ? `leak at ${found}` : "");
}

// ---- synthetic artifact builders (mirror sanitized backend shapes) ---------
function qaGate({ status = "passed", checks, summary } = {}) {
  return {
    version: 1,
    kind: "guide_quality_qa_gate",
    status,
    summary: summary || {
      comprehensive: true,
      check_count: 5,
      passed_count: 3,
      warning_count: 1,
      unknown_count: 1,
      blocking: false,
    },
    checks: checks || [
      { check_id: "guide_quality_gate_check_0001", kind: "reasoning_leak", status: "passed", observed_count: 0, expected_count: 0, instruction: CANARY_FORMULA },
      { check_id: "guide_quality_gate_check_0002", kind: "required_structure", status: "warning", observed_count: 6, expected_count: 10, instruction: CANARY_VALUE },
      { check_id: "guide_quality_gate_check_0003", kind: "math_verification", status: "passed", observed_count: 0, expected_count: 0, instruction: CANARY_ERROR },
      { check_id: "guide_quality_gate_check_0004", kind: "source_coverage", status: "unknown", observed_count: 0, expected_count: 0 },
      { check_id: "guide_quality_gate_check_0005", kind: "quality_report_v2", status: "passed", observed_count: 0, expected_count: 0 },
    ],
    warnings: ["required_sections_missing", CANARY_KEY],
  };
}

function contractLint({ comprehensive = true, leaks = 0, present = 10, total = 10, warnings = 0 } = {}) {
  return {
    version: 1,
    kind: "guide_quality_contract_lint",
    status: "completed",
    summary: {
      comprehensive,
      reasoning_leak_count: leaks,
      required_section_count: total,
      required_section_present_count: present,
      exam_alert_count: 3,
      table_count: 4,
      warning_count: warnings,
      note: CANARY_ERROR,
    },
    checks: [{ instruction: CANARY_FORMULA, excerpt: CANARY_VALUE }],
    warnings: [CANARY_KEY],
  };
}

function mathVerification({ total = 5, ok = 5, mismatch = 0, unparseable = 0, status = "completed" } = {}) {
  return {
    version: 1,
    kind: "math_verification",
    status,
    source: "clean.md",
    report: {
      version: 1,
      source_name: "clean.md",
      summary: { total, ok, mismatch, unparseable },
      // Canary-laden claim list MUST never reach the display model.
      claims: [{ id: "claim_0001", status: "mismatch", expression: CANARY_FORMULA, claimed: CANARY_VALUE, computed: CANARY_VALUE, reason: CANARY_ERROR, text: CANARY_TITLE }],
    },
  };
}

function reportV2({ warnings = 0 } = {}) {
  return {
    version: 2,
    kind: "guide_quality_report",
    status: "completed",
    summary: {
      guide_present: true,
      warning_count: warnings,
      source_page_signal_count: 7,
      coverage_signal_count: 3,
      raw: CANARY_FORMULA,
    },
    checks: [{ kind: "structure", status: "passed", excerpt: CANARY_VALUE }],
    warnings: [CANARY_KEY],
  };
}

function sourceCoverage({ status = "completed", unreadablePages = 0, unreadableSources = 0 } = {}) {
  return {
    version: 1,
    kind: "source_coverage_report",
    status,
    summary: {
      source_count: 1,
      total_pages: 10,
      covered_pages: 10 - unreadablePages,
      empty_or_unreadable_pages: unreadablePages,
      unreadable_source_count: unreadableSources,
      path: CANARY_FILENAME,
    },
    sources: [{ title: CANARY_TITLE, path: CANARY_FILENAME }],
    warnings: [CANARY_URL],
  };
}

function rubricScore({ status = "completed", warnings = 1, axes } = {}) {
  return {
    version: 1,
    kind: "guide_quality_rubric_score",
    status,
    blocking: true,
    summary: {
      score_total: 16,
      score_possible: 16,
      known_axis_count: 8,
      unknown_axis_count: 2,
      warning_axis_count: warnings,
      rubric_axis_count: 10,
      raw: CANARY_FORMULA,
    },
    axes: axes || [
      { axis_id: "rubric_axis_0001", kind: "reasoning_hygiene", status: "passed", score: 2, max_score: 2, confidence: "deterministic", reason: CANARY_ERROR, signals: { formula: CANARY_FORMULA } },
      { axis_id: "rubric_axis_0002", kind: "required_structure", status: "warning", score: 1, max_score: 2, confidence: "advisory", description: CANARY_SPEC },
      { axis_id: "rubric_axis_0003", kind: "exam_focus", status: "passed", score: 2, max_score: 2, confidence: "deterministic", caption: CANARY_CAPTION },
      { axis_id: "rubric_axis_0004", kind: "reference_tables", status: "passed", score: 2, max_score: 2, confidence: "deterministic", table_text: CANARY_TABLE },
      { axis_id: "rubric_axis_0005", kind: "math_verification", status: "passed", score: 2, max_score: 2, confidence: "deterministic", expression: CANARY_FORMULA },
      { axis_id: "rubric_axis_0006", kind: "source_coverage", status: "passed", score: 2, max_score: 2, confidence: "deterministic", path: CANARY_FILENAME },
      { axis_id: "rubric_axis_0007", kind: "coverage_signal_alignment", status: "passed", score: 2, max_score: 2, confidence: "deterministic", ocr_text: CANARY_OCR },
      { axis_id: "rubric_axis_0008", kind: "visual_table_honesty", status: "passed", score: 2, max_score: 2, confidence: "advisory", image_ref: CANARY_URL },
      { axis_id: "rubric_axis_0009", kind: "beginner_scaffolding", status: "unknown", score: null, max_score: null, confidence: "unsupported", reason: "semantic_axis_not_deterministically_measured" },
      { axis_id: "rubric_axis_0010", kind: "worked_example_completeness", status: "unknown", score: null, max_score: null, confidence: "unsupported", reason: "semantic_axis_not_deterministically_measured" },
    ],
    warnings: ["semantic_axis_not_deterministically_measured", CANARY_KEY],
  };
}

// ============================================================================
// 1. All artifacts missing → stable model, calm unavailable states
// ============================================================================
{
  const model = summarizeGuideQualityPanelModel();
  check("all-missing: qaGate unavailable", model.qaGateAvailable === false && model.qaGate.state === "unavailable");
  check("all-missing: lint unavailable", model.contractLintAvailable === false);
  check("all-missing: math unavailable", model.mathVerificationAvailable === false);
  check("all-missing: coverage unavailable", model.sourceCoverageAvailable === false && model.sourceCoverage === null);
  check("all-missing: report v2 unavailable", model.guideQualityReportV2Available === false);
  check("all-missing: rubric unavailable", model.rubricScoreAvailable === false && model.rubricScore.state === "unavailable");
  check("all-missing: no quality checks", model.qualityChecks.length === 0);
  check("all-missing: 6 fixed artifact links", model.artifactLinks.length === 6);
  noLeak("all-missing", model);
}

// ============================================================================
// 2. Valid QA gate → status + check counts summarized
// ============================================================================
{
  const gate = summarizeGuideQualityQaGate(qaGate());
  check("gate status passed", gate.status === "passed");
  check("gate blocking false", gate.blocking === false);
  check("gate check count", gate.checkCount === 5);
  check("gate passed count", gate.passedCount === 3);
  check("gate warning count", gate.warningCount === 1);
  check("gate checks closed-kind only", gate.checks.every((c) =>
    ["reasoning_leak", "required_structure", "math_verification", "source_coverage", "quality_report_v2"].includes(c.kind)));
  check("gate check statuses closed", gate.checks.every((c) =>
    ["passed", "warning", "unknown", "not_applicable"].includes(c.status)));
  check("gate has no instruction/warnings field", !("instruction" in gate) && !("warnings" in gate));
  noLeak("valid gate", gate);

  // gate with hostile/unknown extra status falls back safely
  const bad = summarizeGuideQualityQaGate(qaGate({ status: CANARY_ERROR }));
  check("gate hostile status → skipped", bad.status === "skipped");
  noLeak("hostile gate status", bad);
}

// ============================================================================
// 3. Contract lint → reasoning / structure / exam-alert / table counts
// ============================================================================
{
  const clean = summarizeGuideQualityContractLint(contractLint());
  check("lint clean status passed", clean.status === "passed");
  check("lint reasoning leak status passed", clean.reasoningLeakStatus === "passed");
  check("lint required structure passed", clean.requiredStructureStatus === "passed");
  check("lint exam alerts", clean.examAlertCount === 3);
  check("lint tables", clean.tableCount === 4);
  noLeak("lint clean", clean);

  const leaky = summarizeGuideQualityContractLint(contractLint({ leaks: 2, present: 6, total: 10, warnings: 3 }));
  check("lint leaks → warning status", leaky.status === "warning");
  check("lint reasoning leak count", leaky.reasoningLeakCount === 2);
  check("lint required structure warning", leaky.requiredStructureStatus === "warning");
  check("lint required present/total", leaky.requiredSectionPresentCount === 6 && leaky.requiredSectionCount === 10);
  check("lint warning count", leaky.warningCount === 3);
  noLeak("lint leaky", leaky);

  const short = summarizeGuideQualityContractLint(contractLint({ comprehensive: false, present: 0, total: 0 }));
  check("lint short → structure not_applicable", short.requiredStructureStatus === "not_applicable");
  noLeak("lint short", short);
}

// ============================================================================
// 4. Math verification → safe counts only, no formulas / claim text
// ============================================================================
{
  const clean = summarizeMathVerificationArtifact(mathVerification());
  check("math clean status completed", clean.status === "completed");
  check("math checked count", clean.checkedCount === 5);
  check("math ok count", clean.okCount === 5);
  check("math mismatch 0", clean.mismatchCount === 0);
  check("math tone good", clean.tone === "good");
  noLeak("math clean", clean);

  const bad = summarizeMathVerificationArtifact(mathVerification({ total: 5, ok: 3, mismatch: 2 }));
  check("math mismatch counts", bad.mismatchCount === 2 && bad.tone === "bad");
  // Critically: claim text/expression/values must not appear anywhere.
  noLeak("math mismatch", bad);

  const skipped = summarizeMathVerificationArtifact({ kind: "math_verification", status: "skipped", reason: CANARY_ERROR });
  check("math skipped state", skipped.state === "skipped" && skipped.status === "skipped");
  noLeak("math skipped", skipped);
}

// ============================================================================
// 5. Report v2 + source coverage → coverage / completeness signals
// ============================================================================
{
  const rubric = summarizeGuideQualityRubricScore(rubricScore());
  check("rubric status completed", rubric.status === "completed");
  check("rubric blocking false", rubric.blocking === false);
  check("rubric score totals", rubric.scoreTotal === 16 && rubric.scorePossible === 16);
  check("rubric axis counts", rubric.knownAxisCount === 8 && rubric.unknownAxisCount === 2 && rubric.rubricAxisCount === 10);
  check("rubric closed axis kinds", rubric.axes.every((axis) => [
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
  ].includes(axis.kind)));
  check("rubric closed axis statuses", rubric.axes.every((axis) => ["passed", "warning", "unknown", "not_applicable"].includes(axis.status)));
  check("rubric closed confidence", rubric.axes.every((axis) => ["deterministic", "advisory", "unsupported"].includes(axis.confidence)));
  check("rubric score values closed", rubric.axes.every((axis) => axis.score === 0 || axis.score === 1 || axis.score === 2 || axis.score === null));
  check("rubric unsupported semantic axes stay unknown", rubric.axes.slice(-2).every((axis) => axis.status === "unknown" && axis.score === null && axis.confidence === "unsupported"));
  check("rubric drops raw warnings/reasons/descriptions", !("warnings" in rubric) && rubric.axes.every((axis) => !("reason" in axis) && !("description" in axis)));
  noLeak("valid rubric", rubric);

  const hostile = summarizeGuideQualityRubricScore(rubricScore({
    status: CANARY_ERROR,
    axes: [
      { kind: CANARY_TITLE, status: CANARY_ERROR, score: 99, confidence: CANARY_URL, reason: CANARY_SPEC },
      { kind: "math_verification", status: CANARY_ERROR, score: CANARY_VALUE, confidence: CANARY_KEY },
    ],
  }));
  check("rubric hostile status → skipped", hostile.status === "skipped");
  check("rubric hostile unknown kind dropped", hostile.axes.length === 1 && hostile.axes[0].kind === "math_verification");
  check("rubric hostile axis values degraded", hostile.axes[0].status === "unknown" && hostile.axes[0].score === null && hostile.axes[0].confidence === "unsupported");
  noLeak("hostile rubric", hostile);
}

// ============================================================================
// 5. Report v2 + source coverage → coverage / completeness signals
// ============================================================================
{
  const model = summarizeGuideQualityPanelModel({
    qaGate: qaGate(),
    contractLint: contractLint(),
    guideQualityReportV2: reportV2({ warnings: 2 }),
    mathVerification: mathVerification(),
    sourceCoverageReport: sourceCoverage({ status: "partial", unreadablePages: 3, unreadableSources: 1 }),
    rubricScore: rubricScore(),
  });
  check("coverage available", model.sourceCoverageAvailable === true);
  check("coverage unreadable pages", model.sourceCoverage.unreadablePages === 3);
  check("coverage unreadable sources", model.unreadableSourceCount === 1);
  check("report v2 available", model.guideQualityReportV2Available === true);
  check("report v2 warning count", model.guideQualityReportV2.warningCount === 2);
  check("report v2 source page signals", model.guideQualityReportV2.sourcePageSignalCount === 7);
  check("rubric available in composite", model.rubricScoreAvailable === true && model.rubricScore.scoreTotal === 16);
  check("quality checks from gate", model.qualityChecks.length === 5);
  check("artifact links fixed exact-name labels", JSON.stringify(model.artifactLinks) === JSON.stringify(GUIDE_QUALITY_ARTIFACT_LABELS.map((e) => ({ ...e }))));
  check("fixed rubric artifact label appears", model.artifactLinks.some((entry) => entry.artifact === GUIDE_QUALITY_RUBRIC_SCORE_ARTIFACT && entry.label === "Guide Quality Rubric Score"));
  noLeak("full model", model);
}

// ============================================================================
// 6. Malformed inputs degrade safely (never throw)
// ============================================================================
for (const bad of [12.5, "string", true, [1, 2, 3], {}, { kind: "wrong" }, null, undefined]) {
  const gate = summarizeGuideQualityQaGate(bad);
  check(`malformed gate (${JSON.stringify(bad)}) → object`, gate && typeof gate === "object");
  check(`malformed gate (${JSON.stringify(bad)}) blocking false`, gate.blocking === false);
  const lint = summarizeGuideQualityContractLint(bad);
  check(`malformed lint (${JSON.stringify(bad)}) → object`, lint && typeof lint === "object");
  const math = summarizeMathVerificationArtifact(bad);
  check(`malformed math (${JSON.stringify(bad)}) → object`, math && typeof math === "object");
  const rubric = summarizeGuideQualityRubricScore(bad);
  check(`malformed rubric (${JSON.stringify(bad)}) → object`, rubric && typeof rubric === "object");
  noLeak("malformed gate", gate);
  noLeak("malformed lint", lint);
  noLeak("malformed math", math);
  noLeak("malformed rubric", rubric);
}
{
  // Composite over fully malformed inputs still yields a stable model.
  const model = summarizeGuideQualityPanelModel({
    qaGate: 12.5,
    contractLint: "x",
    guideQualityReportV2: [1],
    mathVerification: true,
    sourceCoverageReport: { kind: "wrong" },
    rubricScore: { kind: "wrong", reason: CANARY_ERROR },
  });
  check("malformed composite → object", model && typeof model === "object");
  check("malformed composite 6 artifact links", model.artifactLinks.length === 6);
  noLeak("malformed composite", model);
}

// ============================================================================
// 7. Hostile canaries in EVERY input do not survive the serialized model
// ============================================================================
{
  const model = summarizeGuideQualityPanelModel({
    qaGate: qaGate({ status: "warning" }),
    contractLint: contractLint({ leaks: 2, warnings: 3 }),
    guideQualityReportV2: reportV2({ warnings: 4 }),
    mathVerification: mathVerification({ mismatch: 2, ok: 3 }),
    sourceCoverageReport: sourceCoverage({ status: "unreadable", unreadablePages: 2, unreadableSources: 1 }),
    rubricScore: rubricScore({ warnings: 2 }),
  });
  const flat = JSON.stringify(model);
  for (const canary of FORBIDDEN_CANARIES) {
    check(`hostile model drops ${canary.slice(0, 16)}`, !flat.includes(canary));
  }
  noLeak("hostile model", model);
  // Still produces real signal.
  check("hostile model still reports counts", model.contractLint.reasoningLeakCount === 2 && model.mathVerification.mismatchCount === 2 && model.rubricScore.warningAxisCount === 2);
}

// ============================================================================
// 8. Determinism
// ============================================================================
{
  const args = {
    qaGate: qaGate(),
    contractLint: contractLint({ leaks: 1 }),
    guideQualityReportV2: reportV2({ warnings: 1 }),
    mathVerification: mathVerification({ mismatch: 1, ok: 4 }),
    sourceCoverageReport: sourceCoverage({ unreadablePages: 1 }),
    rubricScore: rubricScore({ warnings: 1 }),
  };
  const first = JSON.stringify(summarizeGuideQualityPanelModel(args));
  const second = JSON.stringify(summarizeGuideQualityPanelModel(args));
  check("deterministic repeated model", first === second);
}

if (failed > 0) {
  console.error(`\n${failed} guide-quality-panel check(s) failed.`);
  process.exit(1);
}
console.log("\nAll guide-quality-panel helper checks passed.");
