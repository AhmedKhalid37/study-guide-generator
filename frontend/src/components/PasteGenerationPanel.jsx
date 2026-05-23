import React, { useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileCode2,
  FileJson,
  FileText,
  Loader2,
  Wand2
} from "lucide-react";
import { apiUrl, createPasteJob } from "../api/client";

const artifactLabels = {
  "final.pdf": { label: "PDF", icon: Download },
  "clean.md": { label: "Markdown", icon: FileText },
  "final.html": { label: "HTML", icon: FileCode2 },
  "validation.json": { label: "Validation", icon: FileJson },
  "render.log": { label: "Render log", icon: FileText }
};

export default function PasteGenerationPanel({ onJobCreated }) {
  const [inputMethod, setInputMethod] = useState("paste");
  const [text, setText] = useState("");
  const [strictMath, setStrictMath] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const artifactEntries = useMemo(() => {
    if (!result?.artifact_urls) {
      return [];
    }
    return Object.entries(result.artifact_urls).filter(([name]) => artifactLabels[name]);
  }, [result]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!text.trim()) {
      setError("No text provided.");
      setResult(null);
      return;
    }

    setIsGenerating(true);
    setError("");
    setResult(null);
    try {
      const job = await createPasteJob({
        text,
        theme: "claude_clean",
        strictMath
      });
      setResult(job);
      onJobCreated?.(job);
    } catch (generationError) {
      setError(generationError.message || "Could not generate guide.");
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <section className="mx-auto mt-10 w-full max-w-[1536px] rounded-2xl border border-white/10 bg-navy-900/80 p-5 shadow-navy backdrop-blur-xl">
      <div className="flex flex-col gap-2 border-b border-white/10 pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-ember-500">
            Create
          </p>
          <h2 className="mt-1 text-xl font-bold text-white">Generate from pasted text</h2>
        </div>
        <p className="text-sm text-slate-400">Paste Text is live; other methods stay disabled</p>
      </div>

      <form onSubmit={handleSubmit} className="mt-5 grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
        <div className="grid content-start gap-3">
          <label className="text-sm font-bold text-white" htmlFor="input-method">
            Input method
          </label>
          <select
            id="input-method"
            value={inputMethod}
            onChange={(event) => setInputMethod(event.target.value)}
            className="h-11 rounded-xl border border-white/10 bg-[#071426] px-3 text-sm font-bold text-white outline-none transition focus:border-ember-500"
          >
            <option value="paste">Paste Text</option>
            <option value="upload" disabled>
              Upload Markdown
            </option>
            <option value="llm" disabled>
              Generate with LLM
            </option>
          </select>

          <label className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm font-bold text-slate-100">
            <input
              type="checkbox"
              checked={strictMath}
              onChange={(event) => setStrictMath(event.target.checked)}
              className="h-4 w-4 accent-ember-500"
            />
            Strict math
          </label>

          <button
            type="submit"
            disabled={isGenerating || inputMethod !== "paste"}
            className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-ember-500 to-ember-700 px-4 text-sm font-extrabold text-white shadow-ember transition disabled:cursor-not-allowed disabled:opacity-55"
          >
            {isGenerating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating guide...
              </>
            ) : (
              <>
                <Wand2 className="h-4 w-4" />
                Generate PDF
              </>
            )}
          </button>
        </div>

        <div>
          <label className="text-sm font-bold text-white" htmlFor="paste-text">
            Source text
          </label>
          <textarea
            id="paste-text"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="# Chapter notes&#10;&#10;Paste Markdown or plain text here."
            className="mt-3 min-h-[280px] w-full resize-y rounded-2xl border border-white/10 bg-[#071426] p-4 text-sm leading-6 text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-ember-500"
          />

          {error && (
            <div className="mt-4 flex items-start gap-3 rounded-xl border border-red-400/30 bg-red-400/10 p-4 text-sm text-red-100">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {result && (
            <div className="mt-4 rounded-xl border border-emerald-400/30 bg-emerald-400/10 p-4">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-200" />
                <div className="min-w-0">
                  <p className="font-bold text-emerald-100">Guide generated</p>
                  <p className="mt-1 break-all font-mono text-xs text-emerald-100/80">
                    {result.job_id}
                  </p>
                  <p className="mt-1 text-sm text-emerald-100/80">
                    Status: {result.status || "unknown"}
                  </p>
                </div>
              </div>

              {artifactEntries.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {artifactEntries.map(([name, url]) => {
                    const artifact = artifactLabels[name];
                    const Icon = artifact.icon;
                    return (
                      <a
                        key={name}
                        href={apiUrl(url)}
                        className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.08] px-3 py-2 text-xs font-bold text-white transition hover:border-emerald-200/60"
                      >
                        <Icon className="h-4 w-4" />
                        {artifact.label}
                      </a>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </form>
    </section>
  );
}
