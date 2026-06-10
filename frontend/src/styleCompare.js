// Pure, React-free helpers for the Styles workspace "Compare styles" feature
// (Slice 14). Kept dependency-free so it can be unit-tested with plain node via
// scripts/verify-style-compare.mjs. Nothing here touches the network, the DOM,
// or generation behaviour — it only derives deterministic, display-only stats
// from a style's prompt text and manages the compare-selection set.

export const MIN_COMPARE_STYLES = 2;
export const MAX_COMPARE_STYLES = 4;

// Add/remove an id from the compare selection. Returns a NEW array (never
// mutates the input). At capacity, adding a new id is a no-op; toggling an
// already-selected id always removes it (even at capacity).
export function toggleCompareSelection(ids, id, max = MAX_COMPARE_STYLES) {
  const list = Array.isArray(ids) ? ids.slice() : [];
  if (list.includes(id)) {
    return list.filter((value) => value !== id);
  }
  if (list.length >= max) {
    return list;
  }
  return [...list, id];
}

const MATH_PATTERNS = [/\bmath/, /\bequations?\b/, /\bformulae?s?\b/, /\blatex\b/, /\bkatex\b/, /\$/];
const QUIZ_PATTERNS = [/\bmcq\b/, /multiple[\s-]?choice/, /\bquiz/, /\bquestions?\b/, /flash\s?card/];
const CONCISE_PATTERNS = [/\bconcise\b/, /\bcram\b/, /cheat[\s-]?sheet/, /\bcondensed\b/, /one[\s-]?page/, /\bbrief\b/];

function matchesAny(haystack, patterns) {
  return patterns.some((pattern) => pattern.test(haystack));
}

// Deterministic, display-only stats for one prompt body. No LLM, no semantic
// analysis. `content` may be undefined (still loading) — treated as empty.
export function stylePromptStats(content) {
  const text = typeof content === "string" ? content : "";
  const trimmed = text.trim();
  const words = trimmed ? trimmed.split(/\s+/).filter(Boolean) : [];
  const lines = text.split(/\r?\n/);
  // Markdown ATX headings: up to three leading spaces, 1–6 '#', then content.
  const headingCount = lines.filter((line) => /^ {0,3}#{1,6}\s+\S/.test(line)).length;
  const lower = text.toLowerCase();
  return {
    charCount: text.length,
    wordCount: words.length,
    headingCount,
    hasMath: matchesAny(lower, MATH_PATTERNS),
    hasQuiz: matchesAny(lower, QUIZ_PATTERNS),
    hasConcise: matchesAny(lower, CONCISE_PATTERNS),
  };
}
