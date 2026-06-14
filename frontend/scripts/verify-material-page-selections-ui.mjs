// Plain-node harness for the Builder's per-attachment page/slide exclusions
// (Slice 87).
//
// Run:
//
//   node scripts/verify-material-page-selections-ui.mjs
//
// Exercises the pure helpers (src/materialPageSelections.js) the Builder uses to
// turn per-attachment "exclude pages/slides" text into the safe backend
// `material_page_selections` envelope. Asserts: parsing of integers + simple
// ranges, dedupe/sort, closed-vocabulary warnings (never the raw token), that
// attachment keys are ALWAYS `attachment_<index>` (never a filename/path),
// attachments with no exclusions are omitted, the field is gated on active
// exclusions, determinism on repeat, and that no filename / path / token / URL /
// data-URI / base64 can ride out through a serialized payload.

import {
  MATERIAL_PAGE_SELECTIONS_VERSION,
  WARN_TOKEN_INVALID,
  WARN_RANGE_INVALID,
  WARN_RANGE_REVERSED,
  WARN_NUMBER_INVALID,
  parsePageListInput,
  buildMaterialPageSelections,
  hasActiveMaterialSelections
} from "../src/materialPageSelections.js";

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// ---- parsePageListInput ----------------------------------------------------
check("empty string -> no pages, no warnings", eq(parsePageListInput(""), { pages: [], warnings: [] }));
check("whitespace only -> no pages", eq(parsePageListInput("   "), { pages: [], warnings: [] }));
check("null/undefined safe", eq(parsePageListInput(null), { pages: [], warnings: [] }) && eq(parsePageListInput(undefined), { pages: [], warnings: [] }));

check("'2,4-6,10' -> [2,4,5,6,10]", eq(parsePageListInput("2,4-6,10").pages, [2, 4, 5, 6, 10]));
check("spaces tolerated '2, 4 - 6, 10'", eq(parsePageListInput("2, 4 - 6, 10").pages, [2, 4, 5, 6, 10]));
check("single page '5' -> [5]", eq(parsePageListInput("5").pages, [5]));

// dedupe + sort
check("duplicates deduped/sorted '10,2,2,4-5,5'", eq(parsePageListInput("10, 2, 2, 4-5, 5").pages, [2, 4, 5, 10]));
check("overlapping ranges merge cleanly '1-3,2-4'", eq(parsePageListInput("1-3, 2-4").pages, [1, 2, 3, 4]));

// invalid tokens -> closed warnings, never raw value, not in pages
const bad = parsePageListInput("abc, 3, !!, x-y");
check("invalid tokens dropped from pages", eq(bad.pages, [3]));
check("invalid tokens warn token_invalid/range_invalid", bad.warnings.includes(WARN_TOKEN_INVALID) && bad.warnings.includes(WARN_RANGE_INVALID));
check("raw invalid token NOT echoed in warnings", !JSON.stringify(bad.warnings).includes("abc") && !JSON.stringify(bad.warnings).includes("x-y"));

// reversed range warns and is ignored
const rev = parsePageListInput("6-2, 5");
check("reversed range ignored from pages", eq(rev.pages, [5]));
check("reversed range warns range_reversed", eq(rev.warnings, [WARN_RANGE_REVERSED]));

// zero / negative-ish
const zero = parsePageListInput("0, 3");
check("page 0 ignored", eq(zero.pages, [3]));
check("page 0 warns number_invalid", eq(zero.warnings, [WARN_NUMBER_INVALID]));
const zeroRange = parsePageListInput("0-3");
check("range starting at 0 ignored", eq(zeroRange.pages, []));
check("range starting at 0 warns range_invalid", eq(zeroRange.warnings, [WARN_RANGE_INVALID]));

// malformed range shapes
check("'2-' warns range_invalid", eq(parsePageListInput("2-"), { pages: [], warnings: [WARN_RANGE_INVALID] }));
check("'-2' warns range_invalid", eq(parsePageListInput("-2"), { pages: [], warnings: [WARN_RANGE_INVALID] }));

// warnings are deduped to canonical order
const dupWarn = parsePageListInput("abc, def, ghi");
check("repeated invalid tokens collapse to one token_invalid", eq(dupWarn.warnings, [WARN_TOKEN_INVALID]));

// ---- buildMaterialPageSelections -------------------------------------------
check("non-array input -> empty envelope", eq(buildMaterialPageSelections(null), { version: 1, attachments: {}, warnings: [] }));
check("all-empty inputs -> no attachments", eq(buildMaterialPageSelections(["", "  ", ""]), { version: 1, attachments: {}, warnings: [] }));

const env = buildMaterialPageSelections(["2, 4-6", "", "0, abc"]);
check("envelope version is 1", env.version === MATERIAL_PAGE_SELECTIONS_VERSION && env.version === 1);
check("attachment_0 present with parsed pages", eq(env.attachments.attachment_0, {
  version: 1,
  mode: "exclude",
  include_pages: [],
  exclude_pages: [2, 4, 5, 6],
  warnings: []
}));
check("attachment_1 omitted (empty input)", !("attachment_1" in env.attachments));
check("attachment_2 omitted (no valid pages from '0, abc')", !("attachment_2" in env.attachments));

// keys are positional, never filenames
const keys = Object.keys(buildMaterialPageSelections(["1", "2", "3"]).attachments);
check("keys are attachment_0/1/2", eq(keys, ["attachment_0", "attachment_1", "attachment_2"]));
check("keys match attachment_<index> shape", keys.every((k) => /^attachment_\d+$/.test(k)));

// index follows upload order even when earlier attachments have no exclusions
const sparse = buildMaterialPageSelections(["", "5", "", "9"]);
check("sparse: only attachment_1 and attachment_3", eq(Object.keys(sparse.attachments), ["attachment_1", "attachment_3"]));
check("sparse: attachment_1 -> [5]", eq(sparse.attachments.attachment_1.exclude_pages, [5]));
check("sparse: attachment_3 -> [9]", eq(sparse.attachments.attachment_3.exclude_pages, [9]));

// ---- hasActiveMaterialSelections -------------------------------------------
check("empty envelope is inactive", hasActiveMaterialSelections(buildMaterialPageSelections([])) === false);
check("null is inactive", hasActiveMaterialSelections(null) === false);
check("envelope with exclusions is active", hasActiveMaterialSelections(env) === true);

// ---- determinism -----------------------------------------------------------
const a1 = buildMaterialPageSelections(["3,1,2", "10-12"]);
const a2 = buildMaterialPageSelections(["3,1,2", "10-12"]);
check("deterministic identical serialization on repeat", eq(a1, a2));

// ---- no-leak: filename/path canaries never appear in payload ----------------
// Simulate the Builder mapping attachments (with sensitive filenames) -> ordered
// raw inputs by upload order; the envelope must carry ONLY positional keys.
const CANARY_FILENAME = "private-source.pdf";
const CANARY_PATH = "/home/example/private-source.pdf";
const CANARY_URL = "https://evil.example/leak";
const CANARY_DATA_URI = "data:image/png;base64,QQQQ";
const fakeFiles = [
  { name: CANARY_FILENAME },
  { name: "deck.pptx" }
];
const orderedInputs = fakeFiles.map(() => "2, 4-6");
const leakEnv = buildMaterialPageSelections(orderedInputs);
const serialized = JSON.stringify(leakEnv);
check("serialized payload omits filename", !serialized.includes(CANARY_FILENAME));
check("serialized payload omits path", !serialized.includes(CANARY_PATH));
check("serialized payload omits URL", !serialized.includes(CANARY_URL));
check("serialized payload omits data URI", !serialized.includes("data:"));
check("serialized payload omits base64 marker", !serialized.includes("base64"));
check("serialized payload keys are positional only", eq(Object.keys(leakEnv.attachments), ["attachment_0", "attachment_1"]));

// raw invalid tokens never reach a serialized backend payload
const hostile = buildMaterialPageSelections([`${CANARY_PATH}, 3`, `${CANARY_URL}`]);
const hostileSerialized = JSON.stringify(hostile);
check("hostile input: only valid page survives", eq(hostile.attachments.attachment_0.exclude_pages, [3]));
check("hostile input: raw path not in payload", !hostileSerialized.includes("/home/"));
check("hostile input: raw URL not in payload", !hostileSerialized.includes("http"));

// ---- request-wiring shape (mirrors createLlmJob multipart stringify) --------
// The multipart submit path JSON.stringifies the object envelope under the exact
// field name; verify the serialized form is the safe envelope and nothing else.
const wired = JSON.stringify(buildMaterialPageSelections(["2, 4-6, 10"]));
check("wired field serializes to safe envelope", wired === JSON.stringify({
  version: 1,
  attachments: {
    attachment_0: { version: 1, mode: "exclude", include_pages: [], exclude_pages: [2, 4, 5, 6, 10], warnings: [] }
  },
  warnings: []
}));

if (failed > 0) {
  console.error(`\n${failed} check(s) FAILED`);
  process.exit(1);
}
console.log("\nAll material-page-selections UI helper checks passed.");
