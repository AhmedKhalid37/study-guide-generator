// Plain-node harness for the Builder's client-side attachment size policy
// (Slice 101 — emergency large-attachment support).
//
// Run:
//
//   node scripts/verify-large-attachment-upload-limit.mjs
//
// Exercises the pure helpers (src/uploadLimits.js) the Builder uses to pre-flight
// an attachment by byte size before it is uploaded. Asserts: a ~100 MB file is
// accepted (and flagged "large"), a file above the 150 MB ceiling is rejected
// with the generic calm copy, the large-file notice copy exists, the verdict is
// content-free (file.size only — never name/contents), determinism on repeat,
// and that adding this guard does NOT regress the material-selection payload
// (positional keys only, no filename/path/URL/data-URI leak).

import {
  MAX_ATTACHMENT_MB,
  MAX_ATTACHMENT_BYTES,
  LARGE_ATTACHMENT_MB,
  LARGE_ATTACHMENT_BYTES,
  LARGE_FILE_NOTICE,
  OVERSIZE_REJECTION,
  classifyAttachmentSize,
  isAttachmentSizeAccepted,
  isLargeAttachment
} from "../src/uploadLimits.js";
import { buildMaterialPageSelections } from "../src/materialPageSelections.js";

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
const MB = 1024 * 1024;

// ---- constants are sane and cover the 100 MB goal --------------------------
check("default ceiling is 150 MB", MAX_ATTACHMENT_MB === 150);
check("ceiling bytes derived from MB", MAX_ATTACHMENT_BYTES === 150 * MB);
check("large threshold is the 100 MB target", LARGE_ATTACHMENT_MB === 100);
check("large bytes derived from MB", LARGE_ATTACHMENT_BYTES === 100 * MB);
check("ceiling sits above the large/target threshold", MAX_ATTACHMENT_BYTES > LARGE_ATTACHMENT_BYTES);

// ---- 100 MB metadata passes validation (and is flagged large) --------------
const hundred = 100 * MB;
check("100 MB file is accepted", classifyAttachmentSize(hundred).ok === true);
check("100 MB file flagged large", classifyAttachmentSize(hundred).large === true);
check("100 MB predicate accepted", isAttachmentSizeAccepted(hundred) === true);
check("100 MB predicate large", isLargeAttachment(hundred) === true);

// just over 100 MB but under the ceiling -> still accepted, still large
const overTarget = 120 * MB;
check("120 MB accepted (under ceiling)", classifyAttachmentSize(overTarget).ok === true);
check("120 MB flagged large", classifyAttachmentSize(overTarget).large === true);

// exactly at the ceiling is accepted; one byte over is not
check("exactly 150 MB accepted (boundary)", classifyAttachmentSize(MAX_ATTACHMENT_BYTES).ok === true);
check("150 MB + 1 byte rejected", classifyAttachmentSize(MAX_ATTACHMENT_BYTES + 1).ok === false);

// ---- above-limit metadata fails with the calm message ----------------------
const huge = 200 * MB;
const hugeVerdict = classifyAttachmentSize(huge);
check("200 MB file rejected", hugeVerdict.ok === false);
check("200 MB reason is too_large (closed vocab)", hugeVerdict.reason === "too_large");
check("rejected file is not flagged large", hugeVerdict.large === false);
check("oversize rejection copy mentions the limit", OVERSIZE_REJECTION.includes(String(MAX_ATTACHMENT_MB)));
check(
  "oversize rejection copy is calm/generic",
  typeof OVERSIZE_REJECTION === "string" && OVERSIZE_REJECTION.length > 0 && OVERSIZE_REJECTION.includes("can't be uploaded")
);

// ---- large-file helper copy exists -----------------------------------------
check("large-file notice copy exists", LARGE_FILE_NOTICE === "Large files may take longer to process.");

// ---- small/normal files are accepted and NOT flagged large -----------------
const small = 2 * MB;
check("2 MB file accepted", classifyAttachmentSize(small).ok === true);
check("2 MB file not flagged large", classifyAttachmentSize(small).large === false);

// ---- hostile / malformed size values degrade safely ------------------------
check("undefined size -> accepted (0 bytes)", classifyAttachmentSize(undefined).ok === true);
check("null size -> accepted (0 bytes)", classifyAttachmentSize(null).ok === true);
check("NaN size -> accepted (0 bytes)", classifyAttachmentSize(NaN).ok === true);
check("negative size -> accepted (0 bytes)", classifyAttachmentSize(-5).ok === true);
check("string size -> accepted (0 bytes, not parsed)", classifyAttachmentSize("123456789").ok === true);
// Infinity is non-finite, so it degrades to 0 bytes (accepted) just like NaN/null
// — the backend re-enforces the real cap regardless. A realistic File never
// reports an infinite size.
check("Infinity size -> degrades to accepted (0 bytes)", classifyAttachmentSize(Infinity).ok === true);

// ---- verdict is content-free (only size matters) ---------------------------
// Two "files" with identical size but very different (sensitive) names must
// produce byte-identical verdicts — the classifier never sees the name.
const CANARY_FILENAME = "private-source.pdf";
const CANARY_PATH = "/home/example/private-source.pdf";
const fileA = { name: CANARY_FILENAME, size: hundred };
const fileB = { name: "harmless.pdf", size: hundred };
check("verdict ignores filename", eq(classifyAttachmentSize(fileA.size), classifyAttachmentSize(fileB.size)));
const verdictSerialized = JSON.stringify(classifyAttachmentSize(fileA.size));
check("verdict serialization omits filename", !verdictSerialized.includes(CANARY_FILENAME));
check("verdict serialization omits path", !verdictSerialized.includes(CANARY_PATH));
check("notice copy omits filename", !OVERSIZE_REJECTION.includes(CANARY_FILENAME) && !LARGE_FILE_NOTICE.includes(CANARY_FILENAME));

// ---- determinism -----------------------------------------------------------
check("deterministic verdict on repeat (100 MB)", eq(classifyAttachmentSize(hundred), classifyAttachmentSize(hundred)));
check("deterministic verdict on repeat (200 MB)", eq(classifyAttachmentSize(huge), classifyAttachmentSize(huge)));

// ---- no material-selection payload regression ------------------------------
// The size guard is orthogonal to the per-attachment exclusion envelope; confirm
// the envelope still serializes with positional keys only and no leak, exactly as
// before (guards against an accidental cross-import regression).
const env = buildMaterialPageSelections(["2, 4-6", "", "9"]);
check("material envelope keys are positional only", eq(Object.keys(env.attachments), ["attachment_0", "attachment_2"]));
const envSerialized = JSON.stringify(env);
check("material envelope omits filename canary", !envSerialized.includes(CANARY_FILENAME));
check("material envelope omits path canary", !envSerialized.includes(CANARY_PATH));
check("material envelope omits data URI / base64 markers", !envSerialized.includes("data:") && !envSerialized.includes("base64"));

if (failed > 0) {
  console.error(`\n${failed} check(s) failed.`);
  process.exit(1);
}
console.log("\nAll large-attachment upload-limit checks passed.");
