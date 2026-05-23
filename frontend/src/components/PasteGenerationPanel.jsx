import React, { useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileCode2,
  FileJson,
  FileText,
  Upload,
  Loader2,
  Wand2
} from "lucide-react";
import { apiUrl, createLlmJob, createPasteJob, createUploadMarkdownJob } from "../api/client";

const artifactLabels = {
  "final.pdf": { label: "PDF", icon: Download },
  "clean.md": { label: "Markdown", icon: FileText },
  "final.html": { label: "HTML", icon: FileCode2 },
  "validation.json": { label: "Validation", icon: FileJson },
  "render.log": { label: "Render log", icon: FileText }
};

const styles = [
  { label: "Basic study guide", promptName: "basic_study_guide" },
  { label: "Baby-step explanation", promptName: "baby_steps" },
  { label: "Exam cram", promptName: "exam_cram" },
  { label: "MCQ training", promptName: "mcq_training" },
  { label: "Final solution", promptName: "final_solution" },
  { label: "Claude-style study guide", promptName: "claude_study_guide" },
  { label: "Master-level longform guide", promptName: "master_longform" }
];

const modelsByProvider = {
  DeepSeek: ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"],
  Qwen: ["qwen3.7-max", "qwen3.6-plus", "qwen3-max", "qwen3.6-max-preview", "qwen-plus", "qwen-max"]
};

export default function PasteGenerationPanel({ onJobCreated }) {
  const [inputMethod, setInputMethod] = useState("paste");
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [llmTitle, setLlmTitle] = useState("Generated Study Guide");
  const [llmMode, setLlmMode] = useState("exam");
  const [llmStyle, setLlmStyle] = useState("basic_study_guide");
  const [provider, setProvider] = useState("DeepSeek");
  const [model, setModel] = useState(modelsByProvider.DeepSeek[0]);
  const [qwenThinking, setQwenThinking] = useState(true);
  const [strictMath, setStrictMath] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("Generating guide...");
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

    if (inputMethod === "paste" && !text.trim()) {
      setError("No text provided.");
      setResult(null);
      return;
    }
    if (inputMethod === "upload") {
      if (!file) {
        setError("No file selected.");
        setResult(null);
        return;
      }
      if (!isMarkdownFile(file)) {
        setError("Upload a .md or .markdown file.");
        setResult(null);
        return;
      }
    }
    if (inputMethod === "llm") {
      if (!text.trim()) {
        setError("No source text provided.");
        setResult(null);
        return;
      }
      if (!llmTitle.trim()) {
        setError("No title provided.");
        setResult(null);
        return;
      }
    }

    setIsGenerating(true);
    setLoadingMessage(loadingMessageFor(inputMethod));
    setError("");
    setResult(null);
    try {
      const job = await createJob();
      setResult(job);
      onJobCreated?.(job);
    } catch (generationError) {
      setError(generationError.message || "Could not generate guide.");
    } finally {
      setIsGenerating(false);
    }
  }

  function createJob() {
    if (inputMethod === "upload") {
      return createUploadMarkdownJob({
        file,
        theme: "claude_clean",
        strictMath
      });
    }
    if (inputMethod === "llm") {
      return createLlmJob({
        source_text: text,
        title: llmTitle,
        mode: llmMode,
        prompt_name: llmStyle,
        provider,
        model,
        theme: "claude_clean",
        strict_math: strictMath,
        qwen_thinking: qwenThinking
      });
    }
    return createPasteJob({
      text,
      theme: "claude_clean",
      strictMath
    });
  }

  function handleInputMethodChange(event) {
    setInputMethod(event.target.value);
    setError("");
    setResult(null);
  }

  function handleFileChange(event) {
    const nextFile = event.target.files?.[0] ?? null;
    setFile(nextFile);
    setError("");
    setResult(null);
  }

  function handleProviderChange(event) {
    const nextProvider = event.target.value;
    setProvider(nextProvider);
    setModel(modelsByProvider[nextProvider][0]);
    setError("");
    setResult(null);
  }

  return (
    <section className="mx-auto mt-10 w-full max-w-[1536px] rounded-2xl border border-white/10 bg-navy-900/80 p-5 shadow-navy backdrop-blur-xl">
      <div className="flex flex-col gap-2 border-b border-white/10 pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-ember-500">
            Create
          </p>
          <h2 className="mt-1 text-xl font-bold text-white">Generate a PDF guide</h2>
        </div>
        <p className="text-sm text-slate-400">Paste Text, Upload Markdown, and LLM are live</p>
      </div>

      <form onSubmit={handleSubmit} className="mt-5 grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
        <div className="grid content-start gap-3">
          <label className="text-sm font-bold text-white" htmlFor="input-method">
            Input method
          </label>
          <select
            id="input-method"
            value={inputMethod}
            onChange={handleInputMethodChange}
            className="h-11 rounded-xl border border-white/10 bg-[#071426] px-3 text-sm font-bold text-white outline-none transition focus:border-ember-500"
          >
            <option value="paste">Paste Text</option>
            <option value="upload">Upload Markdown</option>
            <option value="llm">Generate with LLM</option>
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
            disabled={isGenerating}
            className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-ember-500 to-ember-700 px-4 text-sm font-extrabold text-white shadow-ember transition disabled:cursor-not-allowed disabled:opacity-55"
          >
            {isGenerating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {loadingMessage}
              </>
            ) : (
              <>
                <Wand2 className="h-4 w-4" />
                {inputMethod === "llm" ? "Generate Study Guide PDF" : "Generate PDF"}
              </>
            )}
          </button>
        </div>

        <div>
          {inputMethod === "paste" && (
            <>
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
            </>
          )}

          {inputMethod === "llm" && (
            <div>
              <div className="grid gap-4 lg:grid-cols-2">
                <label className="grid gap-2 text-sm font-bold text-white">
                  Title
                  <input
                    value={llmTitle}
                    onChange={(event) => setLlmTitle(event.target.value)}
                    className="h-11 rounded-xl border border-white/10 bg-[#071426] px-3 text-sm font-medium text-white outline-none transition focus:border-ember-500"
                  />
                </label>

                <label className="grid gap-2 text-sm font-bold text-white">
                  Mode
                  <select
                    value={llmMode}
                    onChange={(event) => setLlmMode(event.target.value)}
                    className="h-11 rounded-xl border border-white/10 bg-[#071426] px-3 text-sm font-medium text-white outline-none transition focus:border-ember-500"
                  >
                    <option value="exam">exam</option>
                    <option value="theory">theory</option>
                    <option value="quick">quick</option>
                    <option value="deep">deep</option>
                  </select>
                </label>

                <label className="grid gap-2 text-sm font-bold text-white">
                  Style
                  <select
                    value={llmStyle}
                    onChange={(event) => setLlmStyle(event.target.value)}
                    className="h-11 rounded-xl border border-white/10 bg-[#071426] px-3 text-sm font-medium text-white outline-none transition focus:border-ember-500"
                  >
                    {styles.map((style) => (
                      <option key={style.promptName} value={style.promptName}>
                        {style.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="grid gap-2 text-sm font-bold text-white">
                  Provider
                  <select
                    value={provider}
                    onChange={handleProviderChange}
                    className="h-11 rounded-xl border border-white/10 bg-[#071426] px-3 text-sm font-medium text-white outline-none transition focus:border-ember-500"
                  >
                    <option value="DeepSeek">DeepSeek</option>
                    <option value="Qwen">Qwen</option>
                  </select>
                </label>

                <label className="grid gap-2 text-sm font-bold text-white lg:col-span-2">
                  Model
                  <select
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                    className="h-11 rounded-xl border border-white/10 bg-[#071426] px-3 text-sm font-medium text-white outline-none transition focus:border-ember-500"
                  >
                    {modelsByProvider[provider].map((modelId) => (
                      <option key={modelId} value={modelId}>
                        {modelId}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {provider === "Qwen" && (
                <label className="mt-4 flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm font-bold text-slate-100">
                  <input
                    type="checkbox"
                    checked={qwenThinking}
                    onChange={(event) => setQwenThinking(event.target.checked)}
                    className="h-4 w-4 accent-ember-500"
                  />
                  Enable thinking mode
                </label>
              )}

              <label className="mt-4 block text-sm font-bold text-white" htmlFor="llm-source-text">
                Source text
              </label>
              <textarea
                id="llm-source-text"
                value={text}
                onChange={(event) => setText(event.target.value)}
                placeholder="Paste source notes, chapter text, or topic details for the AI-generated guide."
                className="mt-3 min-h-[220px] w-full resize-y rounded-2xl border border-white/10 bg-[#071426] p-4 text-sm leading-6 text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-ember-500"
              />
            </div>
          )}

          {inputMethod === "upload" && (
            <div>
              <label className="text-sm font-bold text-white" htmlFor="markdown-file">
                Markdown file
              </label>
              <label className="mt-3 flex min-h-[280px] cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-white/15 bg-[#071426] p-6 text-center transition hover:border-ember-500/70">
                <Upload className="h-10 w-10 text-ember-500" />
                <span className="mt-4 text-sm font-bold text-white">
                  {file ? file.name : "Choose a .md or .markdown file"}
                </span>
                <span className="mt-2 text-sm text-slate-400">
                  Markdown uploads use the existing PDF pipeline
                </span>
                <input
                  id="markdown-file"
                  type="file"
                  accept=".md,.markdown"
                  onChange={handleFileChange}
                  className="sr-only"
                />
              </label>
            </div>
          )}

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

function isMarkdownFile(file) {
  const name = file.name.toLowerCase();
  return name.endsWith(".md") || name.endsWith(".markdown");
}

function loadingMessageFor(inputMethod) {
  if (inputMethod === "upload") {
    return "Uploading markdown...";
  }
  if (inputMethod === "llm") {
    return "Generating with AI...";
  }
  return "Generating guide...";
}
