// Unit harness for Ask Your Guide workspace-shell helpers.
//
// Plain Node, no test runner dependency. Proves that the UI helpers render only
// safe summaries: readiness state, prepare cache badges, citation samples, and
// attachment/page-selection basenames instead of full paths.

import {
  PREP_BUILT,
  PREP_FAILED,
  PREP_HIT,
  READINESS_NOT_READY,
  READINESS_READY,
  attachmentRows,
  citationSummary,
  formatCount,
  pageSelectionRows,
  prepareBadge,
  readinessReasons,
  readinessState,
  safeFilename,
} from "../src/askGuide.js";

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

const context = {
  readiness: { status: "ready", ready: true, reasons: [] },
  attachments: [
    { filename: "/home/user/course/chapter1.pdf", mode: "ocr", extracted_chars: 1234, warnings: ["low OCR confidence"] },
    { filename: "C:\\Users\\Ahmed\\notes.md", mode: "text" },
  ],
  page_selections: {
    "/private/course/chapter1.pdf": [[1, 5], [9, 9]],
  },
};

check("ready context -> ready", readinessState(context) === READINESS_READY);
check(
  "not-ready context -> not_ready",
  readinessState({ readiness: { ready: false } }) === READINESS_NOT_READY
);
check(
  "reasons filter strings",
  readinessReasons({ readiness: { reasons: ["missing guide", null, 7, "source optional"] } }).join("|") ===
    "missing guide|source optional"
);

check("safeFilename strips POSIX path", safeFilename("/tmp/jobs/abc/source.pdf") === "source.pdf");
check("safeFilename strips Windows path", safeFilename("C:\\tmp\\jobs\\abc\\source.pdf") === "source.pdf");
check("safeFilename fallback", safeFilename("") === "attachment");

const rows = attachmentRows(context);
check("attachmentRows has two rows", rows.length === 2);
check("attachmentRows strips first path", rows[0].filename === "chapter1.pdf");
check("attachmentRows strips second path", rows[1].filename === "notes.md");
check("attachmentRows keeps warning summaries", rows[0].warnings.length === 1);

const selections = pageSelectionRows(context);
check("pageSelectionRows strips path", selections[0].filename === "chapter1.pdf");
check("pageSelectionRows formats ranges", selections[0].ranges.join(",") === "1-5,9-9");

check("formatCount formats finite counts", formatCount(12345) === "12,345");
check("formatCount rejects garbage", formatCount("123") === "0");

const built = {
  ready: true,
  cache_status: "built",
  total_chunk_count: 10,
  guide_chunk_count: 6,
  source_chunk_count: 4,
  citation_summary: {
    guide: { heading_count: 3, headings_sample: ["Intro", "Terms", 5, "Exam focus"] },
    source: { page_count: 2, page_numbers_sample: [1, 4, "x"] },
  },
};
check("prepareBadge built", prepareBadge(built).state === PREP_BUILT);
check("prepareBadge hit", prepareBadge({ ready: true, cache_status: "hit" }).state === PREP_HIT);
check("prepareBadge loading", prepareBadge(null, true).label === "Preparing");
check("prepareBadge error", prepareBadge(null, false, "failed").state === PREP_FAILED);

const summary = citationSummary(built);
check("citationSummary guide count", summary.guideHeadingCount === 3);
check("citationSummary filters heading samples", summary.headings.join(",") === "Intro,Terms,Exam focus");
check("citationSummary filters page samples", summary.pages.join(",") === "1,4");

if (failed) {
  console.error(`\n${failed} ask-guide check(s) failed.`);
  process.exit(1);
}
console.log("\nAll ask-guide checks passed.");
