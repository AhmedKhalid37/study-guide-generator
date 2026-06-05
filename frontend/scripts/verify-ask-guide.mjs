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
  answerBlocks,
  answerTextTokens,
  attachmentRows,
  chatReadiness,
  citationWarningText,
  citationSummary,
  formatAttachmentSummary,
  formatCount,
  guideSourceSummary,
  normalizeAskMessageResponse,
  normalizeAskSessionList,
  normalizeAskSessionPayload,
  normalizeAskSessionSummary,
  nextSessionAfterDelete,
  pageSelectionRows,
  prepareBadge,
  readinessReasons,
  readinessState,
  retrievedChunkRows,
  safeDisplayText,
  safeFilename,
  safeInputText,
  sessionMetaLabel,
  sessionShortLabel,
  sessionStatusLabel,
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
check(
  "formatAttachmentSummary avoids object string",
  formatAttachmentSummary({ count: 2, warning_count: 1, total_extracted_chars: 1234 }) ===
    "2 attachments · 1,234 extracted chars · 1 warning"
);
check(
  "guideSourceSummary formats object metadata",
  guideSourceSummary({ source_available: false, attachment_summary: { count: 1 } }) === "Guide only · 1 attachment"
);
check("guideSourceSummary never renders object blob", !guideSourceSummary({ attachment_summary: { count: 1 } }).includes("[object Object]"));
check(
  "sessionStatusLabel hides technical id",
  sessionStatusLabel({ sessionId: "ask_1234567890abcdef" }) === "Local chat session active · abcdef"
);
check("sessionShortLabel uses suffix", sessionShortLabel({ sessionId: "ask_1234567890abcdef" }) === "Chat abcdef");

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

const unsafe = "Ask with sk-live-abc123456789 Authorization: Bearer abcdef https://secret.example/v1 /home/user/jobs/a C:\\Users\\Ahmed\\x.txt";
const safe = safeDisplayText(unsafe);
check("safeDisplayText redacts key", !safe.includes("sk-live"));
check("safeDisplayText redacts auth", !safe.includes("Authorization"));
check("safeDisplayText redacts URL", !safe.includes("https://"));
check("safeDisplayText redacts POSIX path", !safe.includes("/home/user"));
check("safeDisplayText redacts Windows path", !safe.includes("C:\\"));
check("safeInputText preserves typing whitespace", safeInputText("  hello  ") === "  hello  ");

const sessionPayload = {
  session: {
    session_id: "ask_123",
    job_id: "job-a",
    title: "Alpha https://secret.example/v1",
    created_at: "2026-06-05T10:00:00Z",
    updated_at: "2026-06-05T10:01:00Z",
    settings: { provider: "local", retrieval: { max_chunks: 8, token_budget: 3100 } },
  },
  history: [
    { role: "user", content: "What is alpha?", created_at: "2026-06-05T10:02:00Z" },
    { role: "assistant", content: "Alpha is covered. https://secret.example", citations: ["Guide Alpha", "https://raw.example"] },
    { role: "system", content: "raw prompt" },
  ],
};
const normalizedSession = normalizeAskSessionPayload(sessionPayload);
check("normalizeAskSessionPayload keeps session id", normalizedSession.session.sessionId === "ask_123");
check("normalizeAskSessionPayload redacts title URL", normalizedSession.session.title === "Alpha [redacted-url]");
check("normalizeAskSessionPayload bounds roles", normalizedSession.history.length === 2);
check("normalizeAskSessionPayload redacts assistant URL", !normalizedSession.history[1].content.includes("https://"));
check("normalizeAskSessionPayload normalizes citations", normalizedSession.history[1].citations.includes("Guide Alpha"));
check("normalizeAskSessionPayload redacts citation URL", normalizedSession.history[1].citations.includes("[redacted-url]"));

const sessionList = normalizeAskSessionList({
  sessions: [
    {
      session_id: "ask_old",
      job_id: "job-a",
      title: "Old https://secret.example/v1",
      created_at: "2026-06-05T09:00:00Z",
      updated_at: "2026-06-05T09:01:00Z",
      message_count: 2,
      last_message: { role: "assistant", snippet: "Use /home/user/source.txt" },
    },
    {
      session_id: "ask_new",
      job_id: "job-a",
      created_at: "2026-06-05T10:00:00Z",
      updated_at: "2026-06-05T10:05:00Z",
      message_count: 4,
      last_message: { role: "user", snippet: "Authorization: Bearer abc https://secret.example" },
      raw_prompt: "MUST NOT SURVIVE",
      text: "RAW CHUNK TEXT MUST NOT SURVIVE",
    },
  ],
});
check("normalizeAskSessionList sorts newest first", sessionList[0].sessionId === "ask_new");
check("normalizeAskSessionList redacts last snippet", !JSON.stringify(sessionList).includes("Authorization"));
check("normalizeAskSessionList omits raw prompt", !JSON.stringify(sessionList).includes("MUST NOT SURVIVE"));
check("normalizeAskSessionList omits chunk text", !JSON.stringify(sessionList).includes("RAW CHUNK TEXT"));
check("normalizeAskSessionSummary redacts title", normalizeAskSessionSummary({ session_id: "ask_x", title: "A https://x.test" }).title === "A [redacted-url]");
check("sessionMetaLabel includes count", sessionMetaLabel(sessionList[0]).includes("4 messages"));
check("nextSessionAfterDelete selects next", nextSessionAfterDelete(sessionList, "ask_new").sessionId === "ask_old");
check("nextSessionAfterDelete returns null when empty", nextSessionAfterDelete(sessionList, "ask_new")?.sessionId === "ask_old" && nextSessionAfterDelete([], "ask_new") === null);

const messageResponse = {
  session_id: "ask_123",
  status: "answered",
  answer: "Use citrate. /home/user/source.txt",
  citations: ["Source Page 4", "Guide Alpha"],
  retrieved_chunks: [
    {
      chunk_id: "source-1",
      source_type: "source",
      label: "Source Page 4",
      page: 4,
      approx_tokens: 120,
      score: 9.5,
      text: "RAW CHUNK TEXT MUST NOT SURVIVE",
    },
  ],
  local_model: { configured: true, reachable: true, model: "local-model", model_count: 1, base_url_host: "host.docker.internal" },
};
const normalizedMessage = normalizeAskMessageResponse(messageResponse, "Explain alpha");
check("normalizeAskMessageResponse answered", normalizedMessage.status === "answered");
check("normalizeAskMessageResponse appends user+assistant", normalizedMessage.messages.length === 2);
check("normalizeAskMessageResponse redacts answer path", !normalizedMessage.answer.includes("/home/user"));
check("normalizeAskMessageResponse keeps citations", normalizedMessage.citations.join(",") === "Source Page 4,Guide Alpha");
check("normalizeAskMessageResponse omits chunk text", !JSON.stringify(normalizedMessage).includes("RAW CHUNK TEXT"));
check("retrievedChunkRows normalizes metadata", retrievedChunkRows(messageResponse.retrieved_chunks)[0].label === "Source Page 4");

const citationChecked = normalizeAskMessageResponse(
  {
    session_id: "ask_123",
    status: "answered",
    answer: "Alpha [Source Page 4]",
    citations_allowed: ["Source Page 4", "Guide Alpha"],
    citations_used: ["Source Page 4"],
    citations_unsupported: ["Guide Fake"],
    citation_validation: { ok: false, unsupported_count: 1 },
    retrieved_chunks: messageResponse.retrieved_chunks,
  },
  "Explain alpha"
);
check("normalizeAskMessageResponse uses citations_used chips", citationChecked.citations.join(",") === "Source Page 4");
check("unsupported citation warning handled", citationWarningText(citationChecked).includes("removed"));
check("unsupported citations not trusted chips", !citationChecked.citations.includes("Guide Fake"));

const blocks = answerBlocks("### Title\n\n**Bold** text\n\n1. First\n2. Second\n\n\\$c\\$");
check("answerBlocks converts heading", blocks[0].type === "heading" && blocks[0].segments[0].text === "Title");
check("answerBlocks converts bold segment", blocks[1].segments.some((segment) => segment.type === "strong" && segment.text === "Bold"));
check("answerBlocks converts numbered lists", blocks[2].type === "list" && blocks[2].items.length === 2);
check("answerBlocks cleans escaped math dollars", JSON.stringify(blocks).includes('"type":"math","text":"c"'));
check("answerBlocks returns inert data only", !JSON.stringify(blocks).includes("dangerouslySetInnerHTML"));
check("retrieved chunk disclosure helper omits text", !JSON.stringify(retrievedChunkRows(messageResponse.retrieved_chunks)).includes("RAW CHUNK TEXT"));

const mathBlocks = answerBlocks("Use \\(x^2 + y^2 = z^2\\).\n\n$$\na^2+b^2=c^2\n$$\n\nThen \\[E = mc^2\\].");
check("answerBlocks converts inline paren math", mathBlocks[0].segments.some((segment) => segment.type === "math" && segment.text === "x^2 + y^2 = z^2"));
check("answerBlocks preserves display dollar math block", mathBlocks.some((block) => block.type === "math" && block.text === "a^2+b^2=c^2"));
check("answerBlocks preserves bracket display math block", mathBlocks.some((block) => block.type === "math" && block.text === "E = mc^2"));
check("answerTextTokens separates display math", answerTextTokens("Before\n\\[x=1\\]\nAfter").filter((token) => token.type === "display_math").length === 1);
check("retrievedChunkRows keeps score metadata", retrievedChunkRows(messageResponse.retrieved_chunks)[0].score === 9.5);

const offline = normalizeAskMessageResponse({
  status: "local_offline",
  error: { category: "local_offline", message: "Offline at https://secret.example/v1" },
});
check("local offline category preserved", offline.error.category === "local_offline");
check("local offline message redacted", offline.error.message === "Offline at [redacted-url]");

check("chat readiness no guide", chatReadiness({ hasJob: false }).enabled === false);
check(
  "chat readiness requires prepare",
  chatReadiness({ hasJob: true, contextReady: true, prepReady: false, localReachable: true }).state === "prepare_required"
);
check(
  "chat readiness blocks local offline",
  chatReadiness({ hasJob: true, contextReady: true, prepReady: true, localReachable: false }).state === "local_offline"
);
check(
  "chat readiness ready",
  chatReadiness({ hasJob: true, contextReady: true, prepReady: true, localReachable: true }).enabled === true
);

if (failed) {
  console.error(`\n${failed} ask-guide check(s) failed.`);
  process.exit(1);
}
console.log("\nAll ask-guide checks passed.");
