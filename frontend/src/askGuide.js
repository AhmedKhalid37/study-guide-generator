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

export function safeText(value, fallback = "Unavailable") {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
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
