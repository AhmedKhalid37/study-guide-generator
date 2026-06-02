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
// Tooltip policy (C4b): help text is reserved for the LESS obvious sections.
// Obvious controls (MCQs, Flashcards, Glossary) carry no tip — their label already
// says what they do — so the hints draw attention to the sections that genuinely
// need explanation (TL;DR, cram sheet, exam alerts, common mistakes, diagrams, …).
export const SECTION_GROUPS = [
  {
    title: "Practice",
    keys: [
      { key: "mcqs_with_answers", label: "MCQs (with answers)" },
      { key: "mcqs_without_answers", label: "MCQs (no answers)" },
      { key: "flashcards", label: "Flashcards" },
      { key: "solved_mock_exam", label: "Solved mock exam", tip: "A full mock exam followed by complete worked solutions." },
      { key: "self_test_checklist", label: "Self-test checklist", tip: "A 'can you do X?' checklist to gauge readiness before the exam." },
      { key: "practice_problems", label: "Practice problems" },
    ],
  },
  {
    title: "Reference",
    keys: [
      { key: "glossary", label: "Glossary" },
      { key: "definitions_cheat_sheet", label: "Definitions cheat sheet", tip: "A compact lookup list of key terms and their definitions." },
      { key: "formula_sheet", label: "Formula sheet", tip: "Collects the key formulas with every symbol defined." },
      { key: "summary_tables", label: "Summary tables", tip: "Condenses comparable items into at-a-glance comparison tables." },
      { key: "key_concepts", label: "Key concepts" },
      { key: "learning_objectives", label: "Learning objectives" },
      { key: "summary", label: "TL;DR summary", tip: "A short, high-yield recap of the whole guide up front." },
    ],
  },
  {
    title: "Exam help",
    keys: [
      { key: "cram_sheet", label: "Cram sheet", tip: "A dense one-page sheet of the highest-yield facts for last-minute review." },
      { key: "common_mistakes", label: "Common mistakes", tip: "Calls out frequent errors and misconceptions so you can avoid them." },
      { key: "exam_alerts", label: "Exam alerts", tip: "Flags likely exam traps and points that are commonly tested." },
      { key: "worked_examples", label: "Worked examples", tip: "Adds step-by-step worked examples where the source has formulas or procedures." },
    ],
  },
  {
    title: "Source-aware",
    keys: [
      { key: "diagrams_figures", label: "Diagrams / figures", tip: "Recreates or describes key diagrams and figures where the source supports them." },
      { key: "citations_references", label: "Citations / source refs", tip: "Preserves citations and source references from the material." },
      { key: "slide_page_references", label: "Slide / page refs", tip: "Preserves useful slide/page references from the source." },
      { key: "instructor_notes", label: "Instructor notes", tip: "Surfaces instructor asides and emphasis flagged in the source." },
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
