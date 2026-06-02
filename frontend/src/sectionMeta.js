// Canonical output-section + generation-axis metadata for the Builder (Slice C3).
//
// The single source of truth for the section KEYS and the AXIS values is the
// backend: `INCLUDE_SECTION_FRAGMENTS`, `OUTPUT_DEPTH_FRAGMENTS`, and
// `DIFFICULTY_FRAGMENTS` in `pipeline/orchestrator.py` (validated again there and
// in `pipeline/shortcut_store.py`). These tables only add display labels, UI
// grouping, and help text — they must never invent a key the backend does not
// accept. Keep the key sets in sync with the orchestrator; never widen them here.

// Output-section toggles, grouped only for readability. The `key` is the
// canonical backend key sent verbatim in `include_sections`; `label` is cosmetic.
export const SECTION_GROUPS = [
  {
    title: "Practice",
    keys: [
      { key: "mcqs_with_answers", label: "MCQs (with answers)", tip: "Adds multiple-choice questions WITH a separated answer key." },
      { key: "mcqs_without_answers", label: "MCQs (no answers)", tip: "Adds multiple-choice questions only — no answer key." },
      { key: "flashcards", label: "Flashcards", tip: "Adds front/back question-and-answer flashcard pairs." },
      { key: "solved_mock_exam", label: "Solved mock exam" },
      { key: "self_test_checklist", label: "Self-test checklist" },
      { key: "practice_problems", label: "Practice problems" },
    ],
  },
  {
    title: "Reference",
    keys: [
      { key: "glossary", label: "Glossary", tip: "Adds a glossary table of key terms with simple definitions." },
      { key: "definitions_cheat_sheet", label: "Definitions cheat sheet" },
      { key: "formula_sheet", label: "Formula sheet", tip: "Collects the key formulas with every symbol defined." },
      { key: "summary_tables", label: "Summary tables" },
      { key: "key_concepts", label: "Key concepts" },
      { key: "learning_objectives", label: "Learning objectives" },
      { key: "summary", label: "TL;DR summary" },
    ],
  },
  {
    title: "Exam help",
    keys: [
      { key: "cram_sheet", label: "Cram sheet" },
      { key: "common_mistakes", label: "Common mistakes" },
      { key: "exam_alerts", label: "Exam alerts" },
      { key: "worked_examples", label: "Worked examples", tip: "Adds step-by-step worked examples where the source has formulas or procedures." },
    ],
  },
  {
    title: "Source-aware",
    keys: [
      { key: "diagrams_figures", label: "Diagrams / figures" },
      { key: "citations_references", label: "Citations / source refs", tip: "Preserves citations and source references from the material." },
      { key: "slide_page_references", label: "Slide / page refs", tip: "Preserves useful slide/page references from the source." },
      { key: "instructor_notes", label: "Instructor notes" },
    ],
  },
];

// Flat list of every canonical section key the UI exposes, in group order. Used
// to validate / normalize an incoming dict (e.g. from a loaded shortcut) so only
// keys the Builder knows about are surfaced as toggles.
export const SECTION_KEYS = SECTION_GROUPS.flatMap((group) => group.keys.map((entry) => entry.key));
const SECTION_KEY_SET = new Set(SECTION_KEYS);

// Reduce any incoming `include_sections` shape (dict-of-bool) to a clean dict of
// only the ENABLED, KNOWN keys → true. Unknown/false keys are dropped, matching
// the backend whitelist convention. Returns {} for null/garbage input.
export function normalizeSectionState(sections) {
  const next = {};
  if (!sections || typeof sections !== "object") return next;
  Object.entries(sections).forEach(([key, on]) => {
    if (on && SECTION_KEY_SET.has(key)) next[key] = true;
  });
  return next;
}

// Whether at least one section is enabled (so the caller can omit the field).
export function hasEnabledSections(sections) {
  return Object.keys(normalizeSectionState(sections)).length > 0;
}

// ── Generation axes (global directives, NOT section adders) ──────────────────
// `value: ""` is the unset/default sentinel — when chosen, the field is omitted
// from the generate request and stored as null in a shortcut.
export const OUTPUT_DEPTH_OPTIONS = [
  { value: "", label: "Auto" },
  { value: "quick", label: "Quick" },
  { value: "balanced", label: "Balanced" },
  { value: "exhaustive", label: "Exhaustive" },
];

export const DIFFICULTY_OPTIONS = [
  { value: "", label: "Auto" },
  { value: "beginner", label: "Beginner" },
  { value: "normal", label: "Normal" },
  { value: "exam_level", label: "Exam-level" },
  { value: "advanced", label: "Advanced" },
];

export const OUTPUT_DEPTH_VALUES = OUTPUT_DEPTH_OPTIONS.map((o) => o.value).filter(Boolean);
export const DIFFICULTY_VALUES = DIFFICULTY_OPTIONS.map((o) => o.value).filter(Boolean);
