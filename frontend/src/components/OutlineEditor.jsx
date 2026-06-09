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
    <div className="sg-tab-stack">
      <SectionHeader
        eyebrow="Planning"
        title="Guide outline"
        description="Shape the sections before generating. The AI follows this structure in order."
      />

      {!isAi && (
        <div className="sg-info-banner">
          <Info />
          <span>Outline is applied when generating with AI. Paste / Upload render your Markdown as-is, so the outline won&apos;t change their output.</span>
        </div>
      )}

      <div className="sg-fpanel">
        <div className="sg-ol-head">
          <label className="sg-ol-check">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(event) => setEnabled(event.target.checked)}
            />
            Use this outline when generating
          </label>
          {sections.length > 0 && (
            <button type="button" onClick={clearOutline} className="sg-mini-btn">
              <X /> Clear
            </button>
          )}
        </div>

        <div style={{ marginTop: 12 }}>
          <FieldLabel>Quick templates</FieldLabel>
          <div className="sg-pill-row" style={{ marginTop: 6 }}>
            {OUTLINE_TEMPLATES.map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => applyTemplate(template)}
                className="sg-pill-toggle"
              >
                {template.label}
              </button>
            ))}
          </div>
        </div>

        {isAi && (
          <div style={{ marginTop: 12 }}>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={genLoading}
              className="sg-ghost-button accent"
            >
              {genLoading ? <Loader2 className="sg-spin" /> : <Wand2 />}
              {genLoading ? "Drafting outline…" : "Generate outline from topic"}
            </button>
            {genError && <p className="sg-ol-err">{genError}</p>}
          </div>
        )}
      </div>

      <div className="sg-fpanel">
        <div className="sg-fpanel-head">
          <FieldLabel>Sections {sections.length > 0 ? `(${sections.length})` : ""}</FieldLabel>
          <button type="button" onClick={addSection} className="sg-mini-btn">
            <Plus /> Add section
          </button>
        </div>

        {sections.length === 0 ? (
          <div className="sg-empty" style={{ marginTop: 12 }}>
            No outline yet. Pick a template, add sections, or generate one from your topic.
          </div>
        ) : (
          <div className="sg-ol-list">
            {sections.map((section, index) => (
              <div key={index} className="sg-ol-row">
                <div className="sg-ol-row-top">
                  <span className="sg-ol-num">{index + 1}</span>
                  <input
                    value={section.title}
                    onChange={(event) => updateSection(index, { title: event.target.value })}
                    placeholder="Section title…"
                    className="sg-ol-title-input"
                  />
                  <div className="sg-ol-row-ctl">
                    <IconBtn title="Move up" disabled={index === 0} onClick={() => moveSection(index, -1)}>
                      <ChevronUp />
                    </IconBtn>
                    <IconBtn title="Move down" disabled={index === sections.length - 1} onClick={() => moveSection(index, 1)}>
                      <ChevronDown />
                    </IconBtn>
                    <IconBtn title="Delete section" onClick={() => deleteSection(index)} danger>
                      <Trash2 />
                    </IconBtn>
                  </div>
                </div>
                <input
                  value={section.instructions}
                  onChange={(event) => updateSection(index, { instructions: event.target.value })}
                  placeholder="Optional: what this section should cover"
                  className="sg-ol-instr-input"
                />
              </div>
            ))}
          </div>
        )}

        {enabled && validTitleCount === 0 && (
          <p className="sg-ol-status warn">
            <AlertCircle />
            Add at least one section title — an empty outline is ignored during generation.
          </p>
        )}
        {enabled && validTitleCount > 0 && isAi && (
          <p className="sg-ol-status ok">
            <Sparkles />
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
      className={`sg-icon-btn${danger ? " danger" : ""}`}
    >
      {children}
    </button>
  );
}

function SectionHeader({ eyebrow, title, description }) {
  return (
    <div className="sg-shead">
      <div className="sg-shead-eyebrow">{eyebrow}</div>
      <h2 className="sg-shead-title">{title}</h2>
      <p className="sg-shead-desc">{description}</p>
    </div>
  );
}

function FieldLabel({ children }) {
  return <div className="sg-field-label">{children}</div>;
}
