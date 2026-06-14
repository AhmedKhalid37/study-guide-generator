// Plain-node harness for the Slice 89 material coverage controls/warnings helpers.
//
// Run:
//
//   node scripts/verify-material-coverage-warnings.mjs
//
// Exercises the pure Builder summary + JobDetails notes builders. Asserts:
// inactive vs active summaries, correct attachment + total excluded page counts,
// invalid tokens produce a generic flag (never the raw token), the "cleared" state
// is empty/inactive and deterministic, notes reflect active selections / available
// visual plan / deferred table reconstruction / missing artifacts, and NO raw source
// detail (filenames, paths, page numbers, raw tokens, captions, OCR/source/table
// text, image/asset refs, data URIs, base64, provider payloads, tokens, full URLs)
// can ride out through the serialized summary or note objects.

import {
  NOTE_SELECTIONS_APPLIED,
  NOTE_VISUALS_PLANNED,
  NOTE_TABLE_DEFERRED,
  NOTE_ARTIFACTS_UNAVAILABLE,
  buildBuilderMaterialCoverageSummary,
  buildJobMaterialCoverageNotes,
} from "../src/materialCoverageWarnings.js";
import { buildMaterialCoverageDisplayModel } from "../src/materialCoverageDisplay.js";

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

// ---- Builder summary: inactive --------------------------------------------
const emptySummary = buildBuilderMaterialCoverageSummary({ exclusionInputs: [] });
check("no inputs -> inactive", emptySummary.active === false);
check("no inputs -> 0 attachments", emptySummary.attachmentsWithExclusions === 0);
check("no inputs -> 0 pages", emptySummary.totalExcludedPages === 0);
check("no inputs -> no invalid flag", emptySummary.hasInvalidTokens === false);

const blankSummary = buildBuilderMaterialCoverageSummary({ exclusionInputs: ["", "   ", ""] });
check("blank inputs -> inactive", blankSummary.active === false && blankSummary.attachmentsWithExclusions === 0);

const missingArg = buildBuilderMaterialCoverageSummary();
check("undefined arg -> inactive", missingArg.active === false && missingArg.totalExcludedPages === 0);

const nonArray = buildBuilderMaterialCoverageSummary({ exclusionInputs: "2, 4-6" });
check("non-array inputs tolerated -> inactive", nonArray.active === false);

// ---- Builder summary: single attachment -----------------------------------
const single = buildBuilderMaterialCoverageSummary({ exclusionInputs: ["2, 4-6, 10"] });
// pages: 2,4,5,6,10 => 5 pages
check("single attachment -> active", single.active === true);
check("single attachment -> 1 attachment", single.attachmentsWithExclusions === 1);
check("single attachment -> 5 pages", single.totalExcludedPages === 5);
check("single attachment -> no invalid flag", single.hasInvalidTokens === false);

// ---- Builder summary: multiple attachments --------------------------------
const multi = buildBuilderMaterialCoverageSummary({
  exclusionInputs: ["1-3", "", "5, 7", "  "],
});
// attachment 0: 1,2,3 (3 pages); attachment 2: 5,7 (2 pages); others blank
check("multiple attachments -> active", multi.active === true);
check("multiple attachments -> 2 with exclusions", multi.attachmentsWithExclusions === 2);
check("multiple attachments -> 5 total pages", multi.totalExcludedPages === 5);

// ---- Builder summary: invalid tokens --------------------------------------
const hostileToken = "DROP TABLE pages; /home/secret.pdf, data:image/png;base64,QQQQ, foo";
const invalid = buildBuilderMaterialCoverageSummary({ exclusionInputs: [hostileToken] });
check("invalid tokens -> flagged", invalid.hasInvalidTokens === true);
check("invalid-only -> inactive (no valid pages)", invalid.active === false && invalid.attachmentsWithExclusions === 0);
const invalidBlob = JSON.stringify(invalid);
check("invalid summary: no raw token echoed", !invalidBlob.includes("DROP TABLE") && !invalidBlob.includes("foo"));
check("invalid summary: no path canary", !invalidBlob.includes("/home/") && !invalidBlob.includes(".pdf"));
check("invalid summary: no data URI / base64 canary", !invalidBlob.includes("data:") && !invalidBlob.includes("base64"));

// Mixed valid + invalid: valid pages still counted, invalid still flagged.
const mixed = buildBuilderMaterialCoverageSummary({ exclusionInputs: ["3, notapage, 6-2"] });
check("mixed -> 1 valid page", mixed.totalExcludedPages === 1 && mixed.attachmentsWithExclusions === 1);
check("mixed -> invalid flagged", mixed.hasInvalidTokens === true);

// ---- "Clear exclusions" semantics -----------------------------------------
// Clearing maps to an empty ordered-input array; the summary must be deterministic
// and identical to the no-input inactive state.
const clearedA = buildBuilderMaterialCoverageSummary({ exclusionInputs: [] });
const clearedB = buildBuilderMaterialCoverageSummary({ exclusionInputs: [] });
check("cleared state is inactive", clearedA.active === false && clearedA.totalExcludedPages === 0);
check("cleared state deterministic", JSON.stringify(clearedA) === JSON.stringify(clearedB));

// ---- Builder summary: positional only / no filename leakage ---------------
// The summary is positional (an ordered string array); even if a caller were to
// jam a filename-looking string in as an "input", it is parsed as page tokens and
// dropped — it can never become a key or value in the serialized summary.
const filenameCanary = buildBuilderMaterialCoverageSummary({
  exclusionInputs: ["private-source.pdf", "2-3"],
});
const filenameBlob = JSON.stringify(filenameCanary);
check("positional summary: filename canary not echoed", !filenameBlob.includes("private-source.pdf"));
check("positional summary: keys are not filenames", Object.keys(filenameCanary).every((k) => !k.includes(".")));
check("positional summary: counts only the valid attachment", filenameCanary.attachmentsWithExclusions === 1);

// ---- Determinism ----------------------------------------------------------
const detA = buildBuilderMaterialCoverageSummary({ exclusionInputs: ["1-3", "5"] });
const detB = buildBuilderMaterialCoverageSummary({ exclusionInputs: ["1-3", "5"] });
check("summary deterministic on repeat", JSON.stringify(detA) === JSON.stringify(detB));

// ---- JobDetails notes: active selections + available plan -----------------
const activeModel = buildMaterialCoverageDisplayModel({
  job: {
    material_page_selections: {
      version: 1,
      attachments: { attachment_0: { version: 1, mode: "exclude", include_pages: [], exclude_pages: [2], warnings: [] } },
      warnings: [],
    },
  },
  sourceCoverageReport: {
    kind: "source_coverage_report",
    status: "completed",
    summary: { source_count: 1, total_pages: 10, covered_pages: 9 },
  },
  visualInclusionPlan: {
    kind: "visual_inclusion_plan",
    status: "completed",
    summary: { source_count: 1, candidate_count: 4, non_table_planned_count: 2 },
  },
});
const activeNotes = buildJobMaterialCoverageNotes(activeModel);
const activeTokens = activeNotes.map((n) => n.token);
check("notes: selections applied", activeTokens.includes(NOTE_SELECTIONS_APPLIED));
check("notes: visuals planned", activeTokens.includes(NOTE_VISUALS_PLANNED));
check("notes: table deferred always present", activeTokens.includes(NOTE_TABLE_DEFERRED));
check("notes: artifacts available -> no unavailable note", !activeTokens.includes(NOTE_ARTIFACTS_UNAVAILABLE));
check("notes: each has static text + tone", activeNotes.every((n) => typeof n.text === "string" && n.text.length > 0 && typeof n.tone === "string"));
// Honest-copy guard: notes must not claim full insertion is enabled.
const activeNotesBlob = JSON.stringify(activeNotes).toLowerCase();
check("notes: do not claim inserted/enabled full insertion", !activeNotesBlob.includes("inserted into") && !activeNotesBlob.includes("fully inserted"));

// ---- JobDetails notes: no selections, missing artifacts -------------------
const emptyModel = buildMaterialCoverageDisplayModel({ job: null, sourceCoverageReport: null, visualInclusionPlan: null });
const emptyNotes = buildJobMaterialCoverageNotes(emptyModel);
const emptyTokens = emptyNotes.map((n) => n.token);
check("empty model: no selections note", !emptyTokens.includes(NOTE_SELECTIONS_APPLIED));
check("empty model: no visuals planned note", !emptyTokens.includes(NOTE_VISUALS_PLANNED));
check("empty model: table deferred still present", emptyTokens.includes(NOTE_TABLE_DEFERRED));
check("empty model: artifacts unavailable note", emptyTokens.includes(NOTE_ARTIFACTS_UNAVAILABLE));

// ---- JobDetails notes: malformed plan -> no overpromise -------------------
const malformedPlanModel = buildMaterialCoverageDisplayModel({
  job: null,
  sourceCoverageReport: { kind: "source_coverage_report", status: "completed", summary: {} },
  visualInclusionPlan: { kind: "WRONG_KIND" },
});
const malformedNotes = buildJobMaterialCoverageNotes(malformedPlanModel).map((n) => n.token);
check("malformed plan: no visuals planned note", !malformedNotes.includes(NOTE_VISUALS_PLANNED));
check("malformed plan: source available -> no unavailable note", !malformedNotes.includes(NOTE_ARTIFACTS_UNAVAILABLE));

// ---- JobDetails notes: malformed/empty model tolerated --------------------
check("notes tolerate undefined model", Array.isArray(buildJobMaterialCoverageNotes(undefined)));
check("notes tolerate string model", Array.isArray(buildJobMaterialCoverageNotes("nope")));
const nullModelNotes = buildJobMaterialCoverageNotes(null).map((n) => n.token);
check("null model: table deferred present", nullModelNotes.includes(NOTE_TABLE_DEFERRED));
check("null model: artifacts unavailable present", nullModelNotes.includes(NOTE_ARTIFACTS_UNAVAILABLE));

// ---- JobDetails notes: hostile model never leaks --------------------------
// Even if a hostile/raw display model were passed, notes are a CLOSED set of static
// strings — no input field ever appears in the output.
const hostileModel = {
  selections: { status: "active" },
  visualCoverage: { state: "available" },
  artifacts: { sourceCoverageReportAvailable: true, visualInclusionPlanAvailable: true },
  // hostile extras that must never ride out:
  leak: { caption: "secret caption text", path: "/home/example/private-source.pdf", url: "https://evil.example/x", token: "sk-canary1234567890", data: "data:image/png;base64,QQQQ" },
};
const hostileNotesBlob = JSON.stringify(buildJobMaterialCoverageNotes(hostileModel));
check("hostile model: no caption text", !hostileNotesBlob.includes("secret caption text"));
check("hostile model: no path/filename canary", !hostileNotesBlob.includes("/home/") && !hostileNotesBlob.includes("private-source.pdf"));
check("hostile model: no url canary", !hostileNotesBlob.includes("https://evil.example"));
check("hostile model: no token canary", !hostileNotesBlob.includes("sk-canary1234567890"));
check("hostile model: no data URI / base64 canary", !hostileNotesBlob.includes("data:") && !hostileNotesBlob.includes("base64"));

// ---- Determinism: notes ---------------------------------------------------
const notesA = buildJobMaterialCoverageNotes(activeModel);
const notesB = buildJobMaterialCoverageNotes(activeModel);
check("notes deterministic on repeat", JSON.stringify(notesA) === JSON.stringify(notesB));

if (failed > 0) {
  console.error(`\n${failed} material-coverage-warnings check(s) failed.`);
  process.exit(1);
}
console.log("\nAll material-coverage-warnings helper checks passed.");
