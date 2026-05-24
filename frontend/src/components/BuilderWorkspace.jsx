import React, { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Check,
  ChevronRight,
  Download,
  FileCode2,
  FileJson,
  FileText,
  Leaf,
  ListChecks,
  Loader2,
  Save,
  Share2,
  Sparkles,
  Trophy,
  Upload,
  Wand2,
  Zap
} from "lucide-react";
import { apiUrl, createLlmJob, createPasteJob, createUploadMarkdownJob } from "../api/client";

const sourceTabs = [
  { id: "paste", label: "Paste text" },
  { id: "upload", label: "Upload .md" },
  { id: "llm", label: "AI prompt" },
  { id: "url", label: "URL", disabled: true }
];

const styleChips = [
  { label: "Baby", promptName: "baby_steps", icon: Leaf },
  { label: "Cram", promptName: "exam_cram", icon: Zap },
  { label: "MCQ", promptName: "mcq_training", icon: ListChecks },
  { label: "Final", promptName: "final_solution", icon: Trophy },
  { label: "Editorial", promptName: "claude_study_guide", icon: Sparkles },
  { label: "Master", promptName: "master_longform", icon: Wand2 }
];

const lengthOptions = [
  { id: "short", label: "Short", meta: "~10 pages" },
  { id: "medium", label: "Medium", meta: "~20 pages" },
  { id: "long", label: "Long", meta: "~30+ pages" }
];

const includeOptions = [
  "Key concepts",
  "Mnemonics",
  "Examples",
  "Diagrams",
  "MCQ practice",
  "Glossary",
  "TL;DR"
];

const modelsByProvider = {
  DeepSeek: ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"],
  Qwen: ["qwen3.7-max", "qwen3.6-plus", "qwen3-max", "qwen3.6-max-preview", "qwen-plus", "qwen-max"]
};

const artifactLabels = {
  "final.pdf": { label: "PDF", icon: Download },
  "clean.md": { label: "Markdown", icon: FileText },
  "final.html": { label: "HTML", icon: FileCode2 },
  "validation.json": { label: "validation.json", icon: FileJson },
  "render.log": { label: "render.log", icon: FileText }
};

export default function BuilderWorkspace({
  initialSource = "paste",
  selectedStyle = "exam_cram",
  onSelectStyle,
  latestJob,
  onJobCreated
}) {
  const [source, setSource] = useState(initialSource);
  const [title, setTitle] = useState("Calculus I - Limits & Continuity");
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [mode, setMode] = useState("exam");
  const [provider, setProvider] = useState("DeepSeek");
  const [model, setModel] = useState(modelsByProvider.DeepSeek[0]);
  const [qwenThinking, setQwenThinking] = useState(true);
  const [strictMath, setStrictMath] = useState(true);
  const [length, setLength] = useState("medium");
  const [includes, setIncludes] = useState(["Key concepts", "Mnemonics", "Examples", "Diagrams"]);
  const [result, setResult] = useState(latestJob);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setSource(initialSource);
  }, [initialSource]);

  useEffect(() => {
    if (latestJob) {
      setResult(latestJob);
    }
  }, [latestJob]);

  const artifactEntries = useMemo(() => {
    if (!result?.artifact_urls) {
      return [];
    }
    return Object.entries(result.artifact_urls).filter(([name]) => artifactLabels[name]);
  }, [result]);

  async function handleSubmit(event) {
    event.preventDefault();
    const validation = validateInputs();
    if (validation) {
      setError({ message: validation });
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const job = await createJob();
      setResult(job);
      onJobCreated?.(job);
    } catch (requestError) {
      setError(normalizeError(requestError));
    } finally {
      setLoading(false);
    }
  }

  function validateInputs() {
    if (source === "paste" && !text.trim()) {
      return "No text provided.";
    }
    if (source === "upload") {
      if (!file) {
        return "No file selected.";
      }
      if (!isMarkdownFile(file)) {
        return "Upload a .md or .markdown file.";
      }
    }
    if (source === "llm") {
      if (!title.trim()) {
        return "No title provided.";
      }
      if (!text.trim()) {
        return "No source text provided.";
      }
    }
    return "";
  }

  function createJob() {
    if (source === "upload") {
      return createUploadMarkdownJob({ file, theme: "claude_clean", strictMath });
    }
    if (source === "llm") {
      return createLlmJob({
        source_text: augmentSourceText(text, length, includes),
        title,
        mode,
        prompt_name: selectedStyle,
        provider,
        model,
        theme: "claude_clean",
        strict_math: strictMath,
        qwen_thinking: qwenThinking
      });
    }
    return createPasteJob({ text, theme: "claude_clean", strictMath });
  }

  function handleProviderChange(event) {
    const nextProvider = event.target.value;
    setProvider(nextProvider);
    setModel(modelsByProvider[nextProvider][0]);
  }

  function toggleInclude(option) {
    setIncludes((current) =>
      current.includes(option)
        ? current.filter((item) => item !== option)
        : [...current, option]
    );
  }

  return (
    <div className="overflow-hidden rounded-[22px] border border-white/[0.06] bg-[#0A0F1A] text-[#F4F4F5]">
      <div className="flex h-11 items-center gap-[18px] border-b border-white/[0.05] px-7">
        {["Builder", "Outline", "Style", "Preview"].map((tab, index) => (
          <button
            key={tab}
            type="button"
            className={`h-11 border-b-2 px-0.5 text-[13px] font-medium ${
              index === 0
                ? "border-[#F97316] text-[#F4F4F5]"
                : "border-transparent text-[#9098A8]"
            }`}
          >
            {tab}
          </button>
        ))}
        <div className="flex-1" />
        <span className="inline-flex h-[26px] items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 text-[11.5px] font-medium text-[#F4F4F5]">
          <span className="h-1.5 w-1.5 rounded-full bg-[#22C55E]" />
          Auto-saved · 2s ago
        </span>
      </div>

      <div className="flex min-h-[720px]">
        <form
          onSubmit={handleSubmit}
          className="flex min-w-0 flex-1 flex-col gap-[22px] overflow-auto border-r border-white/[0.05] px-9 py-7"
        >
          <div>
            <FieldLabel>Title</FieldLabel>
            <input value={title} onChange={(event) => setTitle(event.target.value)} className={fieldClass} />
          </div>

          <div>
            <FieldLabel>Source</FieldLabel>
            <div className="mt-1.5 flex w-fit gap-1 rounded-[10px] border border-white/[0.06] bg-white/[0.03] p-1">
              {sourceTabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  disabled={tab.disabled}
                  onClick={() => {
                    setSource(tab.id);
                    setError(null);
                  }}
                  className={`h-8 rounded-[7px] border-0 px-3 text-[12.5px] font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
                    source === tab.id
                      ? "bg-gradient-to-b from-[#FB923C] to-[#EA580C] font-semibold text-[#1A1206] shadow-[inset_0_1px_0_rgba(255,255,255,0.3)]"
                      : "bg-transparent text-[#D4D4D8] hover:bg-white/[0.04]"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <SourceEditor
              source={source}
              text={text}
              setText={setText}
              file={file}
              setFile={setFile}
              setError={setError}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
            <div>
              <FieldLabel>Style</FieldLabel>
              <div className="mt-1.5 grid grid-cols-3 gap-1.5 sm:grid-cols-6">
                {styleChips.map((style) => (
                  <MiniStyle
                    key={style.promptName}
                    style={style}
                    active={selectedStyle === style.promptName}
                    onClick={() => onSelectStyle?.(style.promptName)}
                  />
                ))}
              </div>
            </div>
            <div>
              <FieldLabel>Length</FieldLabel>
              <div className="mt-1.5 grid grid-cols-3 gap-1.5">
                {lengthOptions.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setLength(option.id)}
                    className={`rounded-[9px] border px-1.5 py-2 text-center ${
                      length === option.id
                        ? "border-[rgba(249,115,22,0.45)] bg-[rgba(249,115,22,0.12)]"
                        : "border-white/[0.08] bg-transparent"
                    }`}
                  >
                    <div className="text-[12.5px] font-semibold">{option.label}</div>
                    <div className="text-[10.5px] text-[#9098A8]">{option.meta}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <FieldLabel>Include</FieldLabel>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {includeOptions.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => toggleInclude(option)}
                  className={`inline-flex h-7 items-center gap-1.5 rounded-full border px-3 text-xs font-medium ${
                    includes.includes(option)
                      ? "border-[rgba(249,115,22,0.35)] bg-[rgba(249,115,22,0.10)] text-[#FB923C]"
                      : "border-white/10 bg-white/[0.04] text-[#F4F4F5]"
                  }`}
                >
                  {includes.includes(option) && <span className="text-[10px]">✓</span>}
                  {option}
                </button>
              ))}
            </div>
          </div>

          {source === "llm" && (
            <div className="grid gap-3 rounded-xl border border-white/[0.06] bg-white/[0.025] p-3 xl:grid-cols-2">
              <label>
                <FieldLabel>Mode</FieldLabel>
                <select value={mode} onChange={(event) => setMode(event.target.value)} className={selectClass}>
                  <option value="exam">exam</option>
                  <option value="theory">theory</option>
                  <option value="quick">quick</option>
                  <option value="deep">deep</option>
                </select>
              </label>
              <label>
                <FieldLabel>Provider</FieldLabel>
                <select value={provider} onChange={handleProviderChange} className={selectClass}>
                  <option value="DeepSeek">DeepSeek</option>
                  <option value="Qwen">Qwen</option>
                </select>
              </label>
              <label className="xl:col-span-2">
                <FieldLabel>Model</FieldLabel>
                <select value={model} onChange={(event) => setModel(event.target.value)} className={selectClass}>
                  {modelsByProvider[provider].map((modelId) => (
                    <option key={modelId} value={modelId}>
                      {modelId}
                    </option>
                  ))}
                </select>
              </label>
              {provider === "Qwen" && (
                <Toggle label="Qwen thinking mode" checked={qwenThinking} onChange={setQwenThinking} />
              )}
              <Toggle label="Strict math" checked={strictMath} onChange={setStrictMath} />
            </div>
          )}

          {source !== "llm" && <Toggle label="Strict math" checked={strictMath} onChange={setStrictMath} />}
          {error && <ErrorMessage error={error} />}

          <div className="mt-auto flex items-center gap-3 border-t border-white/[0.05] pt-[18px]">
            <div className="flex items-center gap-2.5 rounded-[10px] border border-white/[0.06] bg-white/[0.03] px-3 py-2">
              <span className="h-2 w-2 rounded-full bg-[#F97316] shadow-[0_0_8px_rgba(249,115,22,0.8)]" />
              <span className="text-[12.5px] font-medium">Best for accuracy</span>
              <ChevronRight className="h-3.5 w-3.5 text-[#9098A8]" />
            </div>
            <div className="flex-1" />
            <button
              type="button"
              className="inline-flex h-10 items-center gap-2 rounded-[10px] border border-white/10 bg-transparent px-4 text-[13px] font-medium text-[#D4D4D8]"
            >
              <Save className="h-4 w-4" />
              Save draft
            </button>
            <button
              type="submit"
              disabled={loading}
              className="relative inline-flex h-10 w-[200px] items-center justify-center gap-2 rounded-[10px] border-0 bg-gradient-to-b from-[#FB923C] via-[#F97316] to-[#EA580C] text-sm font-semibold text-[#1A1206] shadow-[inset_0_1px_0_rgba(255,255,255,0.35),inset_0_-1px_0_rgba(0,0,0,0.18),0_12px_28px_-8px_rgba(249,115,22,0.55),0_0_0_1px_rgba(0,0,0,0.4)] disabled:opacity-60"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-[18px] w-[18px]" />}
              {loading ? "Generating..." : "Generate Guide"}
            </button>
          </div>
        </form>

        <LivePreviewPanel result={result} artifacts={artifactEntries} selectedStyle={selectedStyle} length={length} />
      </div>
    </div>
  );
}

function SourceEditor({ source, text, setText, file, setFile, setError }) {
  if (source === "upload") {
    return (
      <label className="mt-2.5 flex min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-white/[0.08] bg-[#070B14] p-5 text-center">
        <Upload className="h-9 w-9 text-[#F97316]" />
        <span className="mt-3 text-[12.5px] font-semibold text-[#F4F4F5]">
          {file ? file.name : "Choose a .md or .markdown file"}
        </span>
        <span className="mt-1 text-[11px] text-[#6B7185]">Upload Markdown and generate a PDF-ready guide.</span>
        <input
          type="file"
          accept=".md,.markdown"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
            setError(null);
          }}
          className="sr-only"
        />
      </label>
    );
  }

  return (
    <div className="relative mt-2.5 min-h-[200px] rounded-xl border border-white/[0.08] bg-[#070B14] p-3.5">
      {!text && (
        <div className="pointer-events-none absolute inset-3.5 font-mono text-[12.5px] leading-[1.7]">
          <div className="text-[#F97316]"># Limits & Continuity</div>
          <div className="text-[#6B7185]">A limit describes the value a function approaches as the</div>
          <div className="text-[#6B7185]">input approaches some value. Formally, lim x→c f(x) = L if...</div>
          <div className="mt-2 text-[#F97316]">## Definitions</div>
          <div className="text-[#D4D4D8]">- One-sided limits: lim x→c⁻ f(x) and lim x→c⁺ f(x)</div>
          <div className="text-[#D4D4D8]">- Two-sided: equal one-sided limits</div>
        </div>
      )}
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        aria-label={source === "llm" ? "AI prompt and source material" : "Pasted source text"}
        className="relative z-10 min-h-[172px] w-full resize-y bg-transparent font-mono text-[12.5px] leading-[1.7] text-[#D4D4D8] caret-[#F97316] outline-none placeholder:text-[#6B7185]"
      />
      <div className="absolute bottom-2 right-3 font-sans text-[11px] text-[#6B7185]">
        {text.length.toLocaleString()} / 50,000 chars
      </div>
    </div>
  );
}

function MiniStyle({ style, active, onClick }) {
  const Icon = style.icon;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex flex-col items-center gap-1 rounded-lg border px-1 py-1.5 ${
        active
          ? "border-[rgba(249,115,22,0.45)] bg-[rgba(249,115,22,0.12)]"
          : "border-white/[0.06] bg-white/[0.02]"
      }`}
    >
      <span
        className={`grid h-[26px] w-[26px] place-items-center rounded-[7px] border ${
          active
            ? "border-[rgba(255,180,120,0.4)] bg-gradient-to-br from-[#FB923C] via-[#F97316] to-[#C2410C] text-[#1B0F03]"
            : "border-[rgba(255,180,120,0.18)] bg-gradient-to-br from-[#1F2A40] to-[#131B2C] text-[#F97316]"
        }`}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="text-[10.5px] font-medium">{style.label}</span>
    </button>
  );
}

function LivePreviewPanel({ result, artifacts, selectedStyle, length }) {
  const primaryPdf = artifacts.find(([name]) => name === "final.pdf");
  const title = result?.title || "Limits & Continuity";
  const styleLabel = styleChips.find((style) => style.promptName === selectedStyle)?.label?.toUpperCase() || "EXAM CRAM";
  const lengthLabel = lengthOptions.find((option) => option.id === length)?.label?.toUpperCase() || "MEDIUM";

  return (
    <aside className="flex w-[420px] shrink-0 flex-col gap-3.5 bg-gradient-to-b from-[#060A12] to-[#0A0F1A] px-6 py-6">
      <div className="flex items-center justify-between">
        <div className="text-[12.5px] font-semibold text-[#D4D4D8]">Live preview</div>
        <div className="flex gap-1">
          <PreviewBtn>1×</PreviewBtn>
          <PreviewBtn active>2×</PreviewBtn>
          <PreviewBtn>Fit</PreviewBtn>
        </div>
      </div>

      <div className="relative flex-1 overflow-hidden rounded-lg bg-[#FAF7F2] p-[22px] font-serif text-[#1F1A14] shadow-[0_30px_60px_rgba(0,0,0,0.5),0_0_0_1px_rgba(255,255,255,0.06)]">
        <div className="font-mono text-[9px] tracking-[0.15em] text-[#A78050]">
          {styleLabel} · {lengthLabel}
        </div>
        <div className="mt-1.5 text-[22px] font-bold leading-[1.1] tracking-[-0.02em]">
          {title}
        </div>
        <div className="mt-1 font-sans text-[10.5px] text-[#6B5A3F]">
          {result ? `${result.status || "generated"} · ${result.job_id}` : "Calculus I · Chapter 2 · 18 min read"}
        </div>
        <div className="mt-3.5 h-px bg-gradient-to-r from-[#C2410C] to-transparent" />

        {result ? (
          <GeneratedPreview result={result} artifacts={artifacts} />
        ) : (
          <SamplePreview />
        )}

        <div className="absolute bottom-4 left-[22px] right-[22px] flex justify-between font-mono text-[9px] text-[#A78050]">
          <span>STUDY GUIDE</span>
          <span>{result ? "READY" : "03 / 20"}</span>
        </div>
      </div>

      <div className="flex gap-2">
        <a
          href={primaryPdf ? apiUrl(primaryPdf[1]) : undefined}
          className={`flex h-9 flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-[12.5px] font-medium text-[#D4D4D8] ${
            primaryPdf ? "" : "pointer-events-none opacity-55"
          }`}
        >
          <Download className="h-4 w-4" />
          <span className="ml-2">Export PDF</span>
        </a>
        <button
          type="button"
          className="flex h-9 flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-[12.5px] font-medium text-[#D4D4D8]"
        >
          <Share2 className="h-3.5 w-3.5" />
          <span className="ml-2">Share</span>
        </button>
      </div>
    </aside>
  );
}

function SamplePreview() {
  return (
    <>
      <div className="mt-3.5 text-[13px] font-bold">1 · Definitions</div>
      <div className="mt-1.5 font-sans text-[10.5px] leading-[1.55] text-[#3A3528]">
        A limit describes the value a function approaches as its input approaches some value c.
      </div>
      <div className="mt-2.5 border-l-2 border-[#F97316] bg-[rgba(249,115,22,0.07)] px-3 py-2.5 font-mono text-[10.5px] text-[#7A4A1C]">
        lim x→c f(x) = L
      </div>
      <div className="mt-3.5 text-[13px] font-bold">2 · Continuity</div>
      <div className="mt-1.5 font-sans text-[10.5px] leading-[1.55] text-[#3A3528]">
        f is continuous at c if lim x→c f(x) = f(c). Three conditions must hold:
      </div>
      <ul className="mt-1.5 list-disc pl-[18px] font-sans text-[10.5px] text-[#3A3528]">
        <li>f(c) is defined</li>
        <li>The limit exists</li>
        <li>They are equal</li>
      </ul>
      <div className="mt-3.5 rounded-md border border-dashed border-[rgba(194,65,12,0.4)] bg-[rgba(249,115,22,0.10)] p-2.5">
        <div className="font-mono text-[9px] tracking-[0.1em] text-[#A78050]">MEMORY CUE</div>
        <div className="mt-0.5 font-sans text-[11px] text-[#3A3528]">
          <strong>D-L-E</strong>: Defined · Limit exists · Equal
        </div>
      </div>
    </>
  );
}

function GeneratedPreview({ result, artifacts }) {
  return (
    <div className="mt-3.5 font-sans">
      <div className="grid grid-cols-2 gap-2 text-[10.5px]">
        <PreviewMeta label="Status" value={result.status || "unknown"} />
        <PreviewMeta label="Model" value={result.model || "pipeline"} />
      </div>
      <div className="mt-3.5 text-[13px] font-bold font-serif">Exports</div>
      <div className="mt-2 grid gap-1.5">
        {artifacts.length === 0 && (
          <div className="rounded-md bg-[rgba(249,115,22,0.07)] p-2 text-[10.5px] text-[#6B5A3F]">
            No artifacts available yet.
          </div>
        )}
        {artifacts.map(([name, url]) => {
          const artifact = artifactLabels[name];
          const Icon = artifact.icon;
          return (
            <a
              key={name}
              href={apiUrl(url)}
              className="flex items-center justify-between rounded-md border border-[#E9DDCD] bg-white/60 px-2.5 py-2 text-[10.5px] font-bold text-[#3A3528]"
            >
              <span>{artifact.label}</span>
              <Icon className="h-3.5 w-3.5 text-[#C2410C]" />
            </a>
          );
        })}
      </div>
    </div>
  );
}

function PreviewMeta({ label, value }) {
  return (
    <div className="rounded-md bg-[rgba(249,115,22,0.07)] p-2">
      <div className="font-mono text-[8.5px] tracking-[0.1em] text-[#A78050]">{label.toUpperCase()}</div>
      <div className="mt-0.5 truncate text-[10.5px] font-semibold text-[#3A3528]">{value}</div>
    </div>
  );
}

function FieldLabel({ children }) {
  return (
    <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-[#9098A8]">
      {children}
    </div>
  );
}

function PreviewBtn({ children, active }) {
  return (
    <button
      type="button"
      className={`h-6 rounded-md border px-2 text-[11px] font-medium ${
        active
          ? "border-[rgba(249,115,22,0.4)] bg-[rgba(249,115,22,0.14)] text-[#F97316]"
          : "border-white/[0.08] bg-transparent text-[#9098A8]"
      }`}
    >
      {children}
    </button>
  );
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 rounded-[10px] border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-[12.5px] font-medium text-[#D4D4D8]">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 accent-[#F97316]"
      />
      {label}
    </label>
  );
}

function ErrorMessage({ error }) {
  return (
    <div className="rounded-xl border border-red-400/30 bg-red-400/10 p-3 text-[12.5px] text-red-100">
      <div className="flex items-start gap-2.5">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-semibold">{error.message || "Could not generate guide."}</p>
          {error.details && (
            <details className="mt-2 text-red-100/80">
              <summary className="cursor-pointer font-semibold">Details</summary>
              <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap rounded-lg bg-black/20 p-2 text-[11px]">
                {error.details}
              </pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}

const fieldClass =
  "h-11 w-full rounded-[10px] border border-white/[0.08] bg-white/[0.03] px-3.5 text-base font-medium tracking-[-0.01em] text-[#F4F4F5] outline-none transition focus:border-[rgba(249,115,22,0.45)]";

const selectClass =
  "h-9 w-full rounded-[10px] border border-white/[0.08] bg-[#070B14] px-3 text-[13.5px] font-medium text-[#F4F4F5] outline-none";

function isMarkdownFile(file) {
  const name = file.name.toLowerCase();
  return name.endsWith(".md") || name.endsWith(".markdown");
}

function normalizeError(error) {
  const message = error?.message || "Could not generate guide.";
  if (message.startsWith("{") || message.includes("Traceback") || message.length > 180) {
    return { message: "Could not generate guide.", details: message };
  }
  return { message };
}

function augmentSourceText(text, length, includes) {
  const lengthLabel = lengthOptions.find((option) => option.id === length)?.meta || "~20 pages";
  return `${text.trim()}\n\nAdditional builder instructions:\nRequested length: ${lengthLabel}.\nInclude: ${includes.join(", ")}.`;
}
