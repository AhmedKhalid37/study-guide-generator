import React, { useState } from "react";
import {
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Info,
  Loader2,
  Plus,
  Sparkles,
  Trash2,
  Wand2,
  X
} from "lucide-react";
import { generateOutline } from "../api/client";

export const OUTLINE_TEMPLATES = [
  {
    id: "exam",
    label: "Exam Study Guide",
    sections: ["Big Picture", "Key Definitions", "Core Concepts", "Worked Examples", "Common Mistakes", "Practice Questions", "Final Recap"]
  },
  {
    id: "report",
    label: "Report",
    sections: ["Executive Summary", "Background", "Findings", "Analysis", "Recommendations", "Conclusion"]
  },
  {
    id: "presentation",
    label: "Presentation",
    sections: ["Title & Goal", "Agenda", "Key Points", "Supporting Details", "Example / Visual", "Summary", "Q&A"]
  },
  {
    id: "revision",
    label: "Final Revision",
    sections: ["Quick Recap", "Must-Know Formulas", "Key Definitions", "Common Pitfalls", "Rapid Practice"]
  },
  {
    id: "mcq",
    label: "MCQ Practice",
    sections: ["Topic Overview", "Concept Check MCQs", "Application MCQs", "Tricky / Edge Cases", "Answer Key & Explanations"]
  },
  { id: "blank", label: "Blank", sections: [] }
];

function toSections(titles) {
  return titles.map((title) => ({ title, instructions: "" }));
}

export default function OutlineEditor({
  enabled,
  setEnabled,
  sections,
  setSections,
  source,
  text,
  title,
  provider,
  model
}) {
  const [genLoading, setGenLoading] = useState(false);
  const [genError, setGenError] = useState(null);

  const validTitleCount = sections.filter((section) => section.title.trim()).length;
  const isAi = source === "llm";

  function applyTemplate(template) {
    const next = template.id === "blank" ? [{ title: "", instructions: "" }] : toSections(template.sections);
    setSections(next);
    setEnabled(true);
  }

  function addSection() {
    setSections([...sections, { title: "", instructions: "" }]);
    setEnabled(true);
  }

  function updateSection(index, patch) {
    setSections(sections.map((section, i) => (i === index ? { ...section, ...patch } : section)));
  }

  function deleteSection(index) {
    setSections(sections.filter((_, i) => i !== index));
  }

  function moveSection(index, delta) {
    const target = index + delta;
    if (target < 0 || target >= sections.length) return;
    const next = [...sections];
    [next[index], next[target]] = [next[target], next[index]];
    setSections(next);
  }

  function clearOutline() {
    setSections([]);
    setEnabled(false);
    setGenError(null);
  }

  async function handleGenerate() {
    const topic = text.trim();
    if (!topic && !title.trim()) {
      setGenError("Add a topic or source text first.");
      return;
    }
    setGenLoading(true);
    setGenError(null);
    try {
      const result = await generateOutline({ sourceText: topic, title, provider, model });
      const drafted = (result.sections ?? [])
        .filter((section) => section.title?.trim())
        .map((section) => ({ title: section.title, instructions: section.instructions || "" }));
      if (drafted.length === 0) {
        setGenError("The model did not return a usable outline. Try again.");
      } else {
        setSections(drafted);
        setEnabled(true);
      }
    } catch (err) {
      setGenError(err.message || "Could not generate an outline.");
    } finally {
      setGenLoading(false);
    }
  }

  return (
    <div className="grid gap-4">
      <SectionHeader
        eyebrow="Planning"
        title="Guide outline"
        description="Shape the sections before generating. The AI follows this structure in order."
      />

      {!isAi && (
        <div className="flex items-start gap-2 rounded-xl border border-sky-400/25 bg-sky-400/[0.07] p-3 text-[12.5px] leading-5 text-sky-100">
          <Info className="mt-0.5 h-4 w-4 shrink-0" />
          <span>Outline is applied when generating with AI. Paste / Upload render your Markdown as-is, so the outline won&apos;t change their output.</span>
        </div>
      )}

      <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label className="inline-flex items-center gap-2 text-[13px] font-semibold text-[#F4F4F5]">
            <input
              type="checkbox"
              className="h-4 w-4 accent-[#F97316]"
              checked={enabled}
              onChange={(event) => setEnabled(event.target.checked)}
            />
            Use this outline when generating
          </label>
          {sections.length > 0 && (
            <button
              type="button"
              onClick={clearOutline}
              className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/[0.08] bg-white/[0.03] px-2.5 text-[12px] font-semibold text-[#9098A8] transition hover:text-[#F4F4F5]"
            >
              <X className="h-3.5 w-3.5" /> Clear
            </button>
          )}
        </div>

        <div className="mt-3">
          <FieldLabel>Quick templates</FieldLabel>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {OUTLINE_TEMPLATES.map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => applyTemplate(template)}
                className="inline-flex h-8 items-center rounded-full border border-white/[0.08] bg-white/[0.03] px-3 text-[12px] font-semibold text-[#D4D4D8] transition hover:border-[rgba(249,115,22,0.45)] hover:text-white"
              >
                {template.label}
              </button>
            ))}
          </div>
        </div>

        {isAi && (
          <div className="mt-3">
            <button
              type="button"
              onClick={handleGenerate}
              disabled={genLoading}
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-[rgba(168,85,247,0.4)] bg-[rgba(168,85,247,0.12)] px-3 text-[12.5px] font-semibold text-[#D8B4FE] transition hover:border-[rgba(168,85,247,0.6)] disabled:opacity-50"
            >
              {genLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
              {genLoading ? "Drafting outline…" : "Generate outline from topic"}
            </button>
            {genError && <p className="mt-1.5 text-[11.5px] text-red-300">{genError}</p>}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
        <div className="flex items-center justify-between">
          <FieldLabel>Sections {sections.length > 0 ? `(${sections.length})` : ""}</FieldLabel>
          <button
            type="button"
            onClick={addSection}
            className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/[0.08] bg-white/[0.03] px-2.5 text-[12px] font-semibold text-[#D4D4D8] transition hover:border-[rgba(249,115,22,0.45)] hover:text-white"
          >
            <Plus className="h-3.5 w-3.5" /> Add section
          </button>
        </div>

        {sections.length === 0 ? (
          <div className="mt-3 rounded-[10px] border border-dashed border-white/[0.1] bg-[#070B14] p-4 text-center text-[12.5px] leading-5 text-[#9098A8]">
            No outline yet. Pick a template, add sections, or generate one from your topic.
          </div>
        ) : (
          <div className="mt-2.5 grid gap-2">
            {sections.map((section, index) => (
              <div key={index} className="rounded-[10px] border border-white/[0.07] bg-[#070B14] p-2.5">
                <div className="flex items-center gap-2">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-[rgba(249,115,22,0.12)] font-mono text-[11px] font-bold text-[#FB923C]">
                    {index + 1}
                  </span>
                  <input
                    value={section.title}
                    onChange={(event) => updateSection(index, { title: event.target.value })}
                    placeholder="Section title…"
                    className="h-8 min-w-0 flex-1 rounded-md border border-white/[0.08] bg-white/[0.03] px-2.5 text-[13px] font-semibold text-[#F4F4F5] outline-none focus:border-[rgba(249,115,22,0.45)]"
                  />
                  <div className="flex shrink-0 items-center gap-0.5">
                    <IconBtn title="Move up" disabled={index === 0} onClick={() => moveSection(index, -1)}>
                      <ChevronUp className="h-3.5 w-3.5" />
                    </IconBtn>
                    <IconBtn title="Move down" disabled={index === sections.length - 1} onClick={() => moveSection(index, 1)}>
                      <ChevronDown className="h-3.5 w-3.5" />
                    </IconBtn>
                    <IconBtn title="Delete section" onClick={() => deleteSection(index)} danger>
                      <Trash2 className="h-3.5 w-3.5" />
                    </IconBtn>
                  </div>
                </div>
                <input
                  value={section.instructions}
                  onChange={(event) => updateSection(index, { instructions: event.target.value })}
                  placeholder="Optional: what this section should cover"
                  className="mt-1.5 h-8 w-full rounded-md border border-white/[0.06] bg-transparent px-2.5 text-[12px] text-[#D4D4D8] outline-none placeholder:text-[#6B7185] focus:border-[rgba(249,115,22,0.35)]"
                />
              </div>
            ))}
          </div>
        )}

        {enabled && validTitleCount === 0 && (
          <p className="mt-2 inline-flex items-center gap-1.5 text-[11.5px] text-amber-200">
            <AlertCircle className="h-3.5 w-3.5" />
            Add at least one section title — an empty outline is ignored during generation.
          </p>
        )}
        {enabled && validTitleCount > 0 && isAi && (
          <p className="mt-2 inline-flex items-center gap-1.5 text-[11.5px] text-emerald-200/80">
            <Sparkles className="h-3.5 w-3.5" />
            {validTitleCount} section{validTitleCount === 1 ? "" : "s"} will guide AI generation.
          </p>
        )}
      </div>
    </div>
  );
}

function IconBtn({ children, onClick, title, disabled = false, danger = false }) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={`grid h-7 w-7 place-items-center rounded-md border border-white/[0.08] bg-white/[0.03] transition disabled:opacity-30 ${
        danger ? "text-[#9098A8] hover:text-red-300" : "text-[#9098A8] hover:text-[#F4F4F5]"
      }`}
    >
      {children}
    </button>
  );
}

function SectionHeader({ eyebrow, title, description }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
      <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-[#F97316]">{eyebrow}</div>
      <h2 className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-[#F4F4F5]">{title}</h2>
      <p className="mt-1 max-w-2xl text-[12.5px] leading-5 text-[#9098A8]">{description}</p>
    </div>
  );
}

function FieldLabel({ children }) {
  return (
    <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#9098A8]">{children}</div>
  );
}
