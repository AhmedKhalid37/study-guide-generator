// Pure display helpers for the Ask Your Guide workspace shell.
//
// The backend contracts intentionally return summaries only. These helpers keep
// the UI explicit about what is safe to render: counts, booleans, bounded labels,
// and defensive basenames for attachment names. They never render guide/source
// bodies, chunk text, raw URLs, or host paths.

export const READINESS_READY = "ready";
export const READINESS_NOT_READY = "not_ready";
export const READINESS_UNKNOWN = "unknown";

export const PREP_READY = "ready";
export const PREP_HIT = "hit";
export const PREP_BUILT = "built";
export const PREP_REBUILT = "rebuilt";
export const PREP_FAILED = "failed";
export const PREP_IDLE = "idle";

export const CHAT_READY = "ready";
export const CHAT_NO_GUIDE = "no_guide";
export const CHAT_CONTEXT_LOADING = "context_loading";
export const CHAT_CONTEXT_NOT_READY = "context_not_ready";
export const CHAT_PREPARE_REQUIRED = "prepare_required";
export const CHAT_LOCAL_LOADING = "local_loading";
export const CHAT_LOCAL_OFFLINE = "local_offline";
export const CHAT_SENDING = "sending";

const MAX_MESSAGE_CHARS = 12000;
const MAX_CITATIONS = 12;
const MAX_CHUNKS = 12;
const SECRET_RE = /\bsk-[A-Za-z0-9_-]{8,}\b/g;
const AUTH_RE = /\bAuthorization\s*:\s*Bearer\s+[A-Za-z0-9._-]+/gi;
const URL_RE = /https?:\/\/[^\s<>)"']+/g;
const POSIX_PATH_RE = /(?:\/(?:home|Users|mnt|tmp|var|private|workspace|app|root)\/[^\s<>)"']+)/g;
const WINDOWS_PATH_RE = /[A-Za-z]:\\[^\s<>)"']+/g;

export function safeText(value, fallback = "Unavailable") {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

export function safeDisplayText(value, fallback = "") {
  if (typeof value !== "string") return fallback;
  const text = value
    .replace(SECRET_RE, "[redacted-key]")
    .replace(AUTH_RE, "[redacted-authorization]")
    .replace(URL_RE, "[redacted-url]")
    .replace(WINDOWS_PATH_RE, "[redacted-path]")
    .replace(POSIX_PATH_RE, "[redacted-path]")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "")
    .trim();
  return text ? text.slice(0, MAX_MESSAGE_CHARS) : fallback;
}

export function safeInputText(value) {
  if (typeof value !== "string") return "";
  return value
    .replace(SECRET_RE, "[redacted-key]")
    .replace(AUTH_RE, "[redacted-authorization]")
    .replace(URL_RE, "[redacted-url]")
    .replace(WINDOWS_PATH_RE, "[redacted-path]")
    .replace(POSIX_PATH_RE, "[redacted-path]")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "")
    .slice(0, MAX_MESSAGE_CHARS);
}

export function safeFilename(value) {
  if (typeof value !== "string" || !value.trim()) return "attachment";
  const normalized = value.replace(/\\/g, "/");
  const name = normalized.split("/").filter(Boolean).pop() || "attachment";
  return name.replace(/[\u0000-\u001f]/g, "").slice(0, 120) || "attachment";
}

export function formatCount(value) {
  return Number.isFinite(value) && value >= 0 ? value.toLocaleString() : "0";
}

export function formatDate(value) {
  if (typeof value !== "string" || !value) return "Date unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function readinessState(context) {
  const readiness = context?.readiness;
  if (readiness?.ready === true || readiness?.status === READINESS_READY) return READINESS_READY;
  if (readiness?.ready === false || readiness?.status === READINESS_NOT_READY) return READINESS_NOT_READY;
  return READINESS_UNKNOWN;
}

export function readinessReasons(context) {
  const reasons = context?.readiness?.reasons;
  return Array.isArray(reasons) ? reasons.filter((r) => typeof r === "string" && r) : [];
}

export function attachmentRows(contextOrJob) {
  const list = contextOrJob?.attachments;
  if (!Array.isArray(list)) return [];
  return list
    .filter((item) => item && typeof item === "object")
    .map((item) => ({
      filename: safeFilename(item.filename || item.name),
      mode: safeText(item.mode, "mode unavailable"),
      extractedChars: Number.isFinite(item.extracted_chars) ? item.extracted_chars : null,
      warnings: Array.isArray(item.warnings)
        ? item.warnings.filter((w) => typeof w === "string" && w)
        : [],
    }));
}

export function pageSelectionRows(context) {
  const selections = context?.page_selections;
  if (!selections || typeof selections !== "object" || Array.isArray(selections)) return [];
  return Object.entries(selections).map(([filename, ranges]) => ({
    filename: safeFilename(filename),
    ranges: Array.isArray(ranges)
      ? ranges
          .filter((range) => Array.isArray(range) && range.length >= 2)
          .map((range) => `${range[0]}-${range[1]}`)
      : [],
  }));
}

export function prepareState(result, loading = false, error = null) {
  if (loading) return "preparing";
  if (error) return PREP_FAILED;
  if (!result) return PREP_IDLE;
  if (result.ready === false) return PREP_FAILED;
  const status = result.cache_status;
  if (status === PREP_HIT) return PREP_HIT;
  if (status === PREP_BUILT) return PREP_BUILT;
  if (status === PREP_REBUILT) return PREP_REBUILT;
  if (result.ready === true) return PREP_READY;
  return PREP_IDLE;
}

export function prepareBadge(result, loading = false, error = null) {
  const state = prepareState(result, loading, error);
  const labels = {
    preparing: "Preparing",
    [PREP_IDLE]: "Not prepared",
    [PREP_HIT]: "Ready · cache hit",
    [PREP_BUILT]: "Ready · built",
    [PREP_REBUILT]: "Ready · rebuilt",
    [PREP_READY]: "Ready",
    [PREP_FAILED]: "Needs attention",
  };
  const tones = {
    preparing: "neutral",
    [PREP_IDLE]: "neutral",
    [PREP_HIT]: "ready",
    [PREP_BUILT]: "ready",
    [PREP_REBUILT]: "ready",
    [PREP_READY]: "ready",
    [PREP_FAILED]: "error",
  };
  return { state, label: labels[state] || labels[PREP_IDLE], tone: tones[state] || "neutral" };
}

export function citationSummary(result) {
  const guide = result?.citation_summary?.guide || {};
  const source = result?.citation_summary?.source || {};
  const headings = Array.isArray(guide.headings_sample)
    ? guide.headings_sample.filter((h) => typeof h === "string" && h).slice(0, 8)
    : [];
  const pages = Array.isArray(source.page_numbers_sample)
    ? source.page_numbers_sample.filter((p) => Number.isFinite(p)).slice(0, 12)
    : [];
  return {
    guideHeadingCount: Number.isFinite(guide.heading_count) ? guide.heading_count : 0,
    sourcePageCount: Number.isFinite(source.page_count) ? source.page_count : 0,
    headings,
    pages,
  };
}

export function safeCitationLabels(value, limit = MAX_CITATIONS) {
  if (!Array.isArray(value)) return [];
  const labels = [];
  const seen = new Set();
  value.forEach((item) => {
    const label = safeDisplayText(item);
    if (!label || seen.has(label)) return;
    seen.add(label);
    labels.push(label.slice(0, 180));
  });
  return labels.slice(0, limit);
}

export function retrievedChunkRows(value) {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item) => item && typeof item === "object")
    .map((item) => ({
      chunkId: safeDisplayText(item.chunk_id || item.chunkId || item.id || "", ""),
      sourceType: safeDisplayText(item.source_type || item.sourceType || "", "source"),
      label: safeDisplayText(item.label || "", "Citation"),
      page: Number.isFinite(item.page) ? item.page : null,
      approxTokens: Number.isFinite(item.approx_tokens)
        ? item.approx_tokens
        : Number.isFinite(item.approxTokens)
          ? item.approxTokens
          : null,
      score: Number.isFinite(item.score) ? item.score : null,
    }))
    .filter((item) => item.label)
    .slice(0, MAX_CHUNKS);
}

export function normalizeAskHistory(value) {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item) => item && typeof item === "object")
    .map((item, index) => {
      const role = item.role === "assistant" ? "assistant" : item.role === "user" ? "user" : null;
      if (!role) return null;
      const content = safeDisplayText(item.content);
      if (!content) return null;
      return {
        id: safeDisplayText(item.id || `${role}-${item.created_at || index}`, `${role}-${index}`),
        role,
        content,
        createdAt: typeof item.created_at === "string" ? item.created_at : null,
        citations: role === "assistant" ? safeCitationLabels(item.citations) : [],
        retrievedChunks: role === "assistant" ? retrievedChunkRows(item.retrieved_chunks) : [],
      };
    })
    .filter(Boolean);
}

export function normalizeAskSessionPayload(value) {
  const session = value?.session && typeof value.session === "object" ? value.session : {};
  const sessionId = typeof session.session_id === "string" ? session.session_id : null;
  const jobId = typeof session.job_id === "string" ? session.job_id : null;
  return {
    session: sessionId
      ? {
          sessionId,
          jobId,
          title: safeDisplayText(session.title || "", ""),
          createdAt: typeof session.created_at === "string" ? session.created_at : null,
          updatedAt: typeof session.updated_at === "string" ? session.updated_at : null,
          provider: "local",
          retrieval: {
            maxChunks: Number.isFinite(session.settings?.retrieval?.max_chunks)
              ? session.settings.retrieval.max_chunks
              : null,
            tokenBudget: Number.isFinite(session.settings?.retrieval?.token_budget)
              ? session.settings.retrieval.token_budget
              : null,
          },
        }
      : null,
    history: normalizeAskHistory(value?.history),
  };
}

export function normalizeAskMessageResponse(value, fallbackUserMessage = "", keySeed = "current") {
  const status = safeDisplayText(value?.status || "", "error");
  const error = value?.error && typeof value.error === "object" ? value.error : null;
  const answer = safeDisplayText(value?.answer || "");
  return {
    sessionId: typeof value?.session_id === "string" ? value.session_id : null,
    status,
    answer,
    citations: safeCitationLabels(value?.citations),
    retrievedChunks: retrievedChunkRows(value?.retrieved_chunks),
    localModel:
      value?.local_model && typeof value.local_model === "object"
        ? {
            provider: "local",
            configured: Boolean(value.local_model.configured),
            reachable: Boolean(value.local_model.reachable),
            model: safeDisplayText(value.local_model.model || "", ""),
            modelCount: Number.isFinite(value.local_model.model_count) ? value.local_model.model_count : null,
            baseUrlHost: safeDisplayText(value.local_model.base_url_host || "", ""),
          }
        : null,
    error: error
      ? {
          category: safeDisplayText(error.category || "", "ask_error"),
          message: safeDisplayText(error.message || "", "Ask message failed."),
        }
      : null,
    messages:
      status === "answered" && answer
        ? [
            { id: `user-${keySeed}`, role: "user", content: safeDisplayText(fallbackUserMessage), citations: [], retrievedChunks: [] },
            {
              id: `assistant-${keySeed}`,
              role: "assistant",
              content: answer,
              citations: safeCitationLabels(value?.citations),
              retrievedChunks: retrievedChunkRows(value?.retrieved_chunks),
            },
          ]
        : [],
  };
}

export function chatReadiness({
  hasJob,
  contextLoading,
  contextReady,
  prepReady,
  localLoading,
  localReachable,
  sending,
}) {
  if (!hasJob) return { state: CHAT_NO_GUIDE, enabled: false, label: "Select a guide" };
  if (contextLoading) return { state: CHAT_CONTEXT_LOADING, enabled: false, label: "Loading context" };
  if (!contextReady) return { state: CHAT_CONTEXT_NOT_READY, enabled: false, label: "Guide context unavailable" };
  if (!prepReady) return { state: CHAT_PREPARE_REQUIRED, enabled: false, label: "Prepare context first" };
  if (localLoading) return { state: CHAT_LOCAL_LOADING, enabled: false, label: "Checking local model" };
  if (!localReachable) return { state: CHAT_LOCAL_OFFLINE, enabled: false, label: "Local model offline" };
  if (sending) return { state: CHAT_SENDING, enabled: false, label: "Sending" };
  return { state: CHAT_READY, enabled: true, label: "Ask your guide" };
}
