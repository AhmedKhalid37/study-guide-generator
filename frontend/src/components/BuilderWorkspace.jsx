import React, { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
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
import {
  apiUrl,
  createLlmJob,
  createPasteJob,
  createUploadMarkdownJob,
  getJob,
  getOptions,
  getStyles,
  previewApiUrl
} from "../api/client";
import {
  BoltGlyph,
  DocGlyph,
  LeafGlyph,
  ListGlyph,
  PDFGlyph,
  SparkleGlyph,
  Tile,
  TrophyGlyph,
  UploadGlyph
} from "./ClaudeIcons";
import { JobDetailsDrawer } from "./RecentJobsPanel";
import { BUILTIN_STYLE_NAMES } from "../styleMeta";

const sourceTabs = [
  { id: "paste", label: "Paste text" },
  { id: "upload", label: "Upload .md" },
  { id: "llm", label: "AI prompt" },
  { id: "url", label: "URL", disabled: true }
];

const builderTabs = [
  { id: "builder", label: "Builder" },
  { id: "outline", label: "Outline" },
  { id: "style", label: "Style" },
  { id: "preview", label: "Preview" }
];

const builtinStyleMeta = {
  basic_study_guide: { label: "Basic", icon: FileText },
  baby_steps: { label: "Baby", icon: Leaf },
  exam_cram: { label: "Cram", icon: Zap },
  mcq_training: { label: "MCQ", icon: ListChecks },
  final_solution: { label: "Final", icon: Trophy },
  claude_study_guide: { label: "Editorial", icon: Sparkles },
  master_longform: { label: "Master", icon: Wand2 }
};

// Static fallback used until /api/styles resolves (and as the built-in icon source).
const styleChips = Object.entries(builtinStyleMeta).map(([promptName, meta]) => ({
  promptName,
  label: meta.label,
  name: BUILTIN_STYLE_NAMES[promptName] || meta.label,
  icon: meta.icon,
  custom: false
}));

function styleRecordToChip(style) {
  const meta = builtinStyleMeta[style.id];
  const isCustom = style.source === "custom";
  const name = style.name || BUILTIN_STYLE_NAMES[style.id] || style.id;
  let label = meta?.label || name;
  if (!meta && label.length > 12) {
    label = `${label.slice(0, 11)}…`;
  }
  return {
    promptName: style.id,
    label,
    name,
    icon: meta?.icon || (isCustom ? Sparkles : FileText),
    custom: isCustom
  };
}

const lengthOptions = [
  { id: "short", label: "Short", meta: "~10 pages" },
  { id: "medium", label: "Medium", meta: "~20 pages" },
  { id: "long", label: "Long", meta: "~30+ pages" }
];

const modeOptions = [
  { id: "exam", label: "Exam", meta: "test-ready guide", icon: Trophy },
  { id: "theory", label: "Theory", meta: "concepts + depth", icon: Sparkles },
  { id: "quick", label: "Quick", meta: "fast summary", icon: Zap },
  { id: "deep", label: "Deep", meta: "detailed explanation", icon: ListChecks }
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

const fallbackProviderDetails = [
  {
    id: "deepseek",
    display_name: "DeepSeek",
    configured: false,
    available_models: ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"],
    default_model: "deepseek-v4-flash",
    supports_thinking: false
  },
  {
    id: "qwen",
    display_name: "Qwen",
    configured: false,
    available_models: ["qwen3.7-max", "qwen3.6-plus", "qwen3-max", "qwen3.6-max-preview", "qwen-plus", "qwen-max"],
    default_model: "qwen3.7-max",
    supports_thinking: true
  },
  {
    id: "local",
    display_name: "Local llama.cpp",
    configured: false,
    available_models: [],
    default_model: "",
    supports_thinking: false
  }
];

const artifactLabels = {
  "final.pdf": { label: "PDF", icon: Download },
  "clean.md": { label: "Markdown", icon: FileText },
  "final.html": { label: "HTML", icon: FileCode2 },
  "validation.json": { label: "validation.json", icon: FileJson },
  "render.log": { label: "render.log", icon: FileText }
};

const outlineSections = [
  "Big picture",
  "Key definitions",
  "Core formulas",
  "Step-by-step explanation",
  "Worked examples",
  "Common mistakes",
  "Practice questions",
  "Final recap"
];

export default function BuilderWorkspace({
  initialSource = "paste",
  selectedStyle = "exam_cram",
  onSelectStyle,
  latestJob,
  onJobCreated
}) {
  const [activeBuilderTab, setActiveBuilderTab] = useState("builder");
  const [source, setSource] = useState(initialSource);
  const [title, setTitle] = useState("Generated Study Guide");
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [mode, setMode] = useState("exam");
  const [provider, setProvider] = useState("deepseek");
  const [model, setModel] = useState(fallbackProviderDetails[0].default_model);
  const [providerDetails, setProviderDetails] = useState(fallbackProviderDetails);
  const [qwenThinking, setQwenThinking] = useState(true);
  const [strictMath, setStrictMath] = useState(true);
  const [attachments, setAttachments] = useState([]);
  const [styleOptions, setStyleOptions] = useState(styleChips);
  const [length, setLength] = useState("medium");
  const [includes, setIncludes] = useState(["Key concepts", "Mnemonics", "Examples", "Diagrams"]);
  const [result, setResult] = useState(latestJob);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [previewFormat, setPreviewFormat] = useState("sample");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [jobDetails, setJobDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState(null);

  useEffect(() => {
    setSource(initialSource);
    setError(null);
    setActiveBuilderTab("builder");
  }, [initialSource]);

  useEffect(() => {
    if (latestJob) {
      setResult(latestJob);
    }
  }, [latestJob]);

  useEffect(() => {
    let cancelled = false;
    getOptions()
      .then((options) => {
        if (cancelled) return;
        const details = normalizeProviderDetails(options);
        setProviderDetails(details);
        const selected = chooseInitialProvider(details, provider);
        setProvider(selected.id);
        setModel(selectDefaultModel(selected, model));
      })
      .catch(() => {
        if (!cancelled) {
          setProviderDetails(fallbackProviderDetails);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    getStyles()
      .then((result) => {
        if (cancelled) return;
        const all = [...(result.builtin ?? []), ...(result.custom ?? [])];
        if (all.length > 0) {
          setStyleOptions(all.map(styleRecordToChip));
        }
      })
      .catch(() => {
        if (!cancelled) setStyleOptions(styleChips);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const artifactEntries = useMemo(() => {
    if (!result?.artifact_urls) {
      return [];
    }
    return Object.entries(result.artifact_urls).filter(([name]) => artifactLabels[name]);
  }, [result]);

  const artifactUrls = useMemo(() => result?.artifact_urls ?? {}, [result]);
  const selectedStyleOption =
    styleOptions.find((style) => style.promptName === selectedStyle) ||
    styleChips.find((style) => style.promptName === selectedStyle);
  const builderStyleLookup = useMemo(
    () =>
      Object.fromEntries(
        styleOptions.map((style) => [
          style.promptName,
          { name: style.name, source: style.custom ? "custom" : "builtin" }
        ])
      ),
    [styleOptions]
  );
  const selectedLengthOption = lengthOptions.find((option) => option.id === length);
  const selectedProvider = useMemo(
    () => providerDetails.find((item) => item.id === provider) ?? providerDetails[0],
    [providerDetails, provider]
  );
  const selectedProviderModels = selectedProvider?.available_models?.length
    ? selectedProvider.available_models
    : selectedProvider?.default_model
      ? [selectedProvider.default_model]
      : [];

  useEffect(() => {
    if (!result) {
      setPreviewFormat("sample");
      return;
    }
    if (artifactUrls["final.pdf"]) {
      setPreviewFormat("pdf");
    } else if (artifactUrls["final.html"]) {
      setPreviewFormat("html");
    } else {
      setPreviewFormat("pdf");
    }
  }, [result, artifactUrls]);

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
      const { kind, payload } = buildBuilderPayload({
        source,
        text,
        file,
        title,
        mode,
        selectedStyle,
        provider,
        model,
        strictMath,
        qwenThinking,
        attachments,
        length,
        includes
      });
      assertBuilderPayload(kind, payload, { text, title, length, includes });
      const job = await createJob(kind, payload);
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
      if (!selectedProvider?.configured) {
        return `${selectedProvider?.display_name || "Selected provider"} is not configured on the server.`;
      }
      if (!model) {
        return "No model selected.";
      }
    }
    return "";
  }

  function createJob(kind, payload) {
    if (kind === "upload") {
      return createUploadMarkdownJob(payload);
    }
    if (kind === "llm") {
      return createLlmJob(payload);
    }
    return createPasteJob(payload);
  }

  function handleProviderSelect(nextProvider) {
    setProvider(nextProvider);
    const detail = providerDetails.find((item) => item.id === nextProvider);
    setModel(selectDefaultModel(detail));
  }

  function toggleInclude(option) {
    setIncludes((current) =>
      current.includes(option)
        ? current.filter((item) => item !== option)
        : [...current, option]
    );
  }

  async function openJobDetails() {
    const jobId = result?.job_id || result?.id;
    if (!jobId) {
      return;
    }
    setDetailsOpen(true);
    setDetailsLoading(true);
    setDetailsError(null);
    try {
      setJobDetails(await getJob(jobId));
    } catch (requestError) {
      setDetailsError(requestError);
      setJobDetails(null);
    } finally {
      setDetailsLoading(false);
    }
  }

  return (
    <div className="sg-builder">
      <div className="sg-builder-tabs">
        {builderTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveBuilderTab(tab.id)}
            className={activeBuilderTab === tab.id ? "active" : ""}
          >
            <BuilderTabIcon id={tab.id} active={activeBuilderTab === tab.id} />
            {tab.label}
          </button>
        ))}
        <div className="flex-1" />
        <span className="sg-autosave">
          <i />
          Auto-saved · 2s ago
        </span>
      </div>

      <div className="sg-builder-body">
        <form
          onSubmit={handleSubmit}
          className="sg-builder-pane"
        >
          {activeBuilderTab === "builder" && (
            <BuilderComposer
              title={title}
              setTitle={setTitle}
              source={source}
              setSource={setSource}
              text={text}
              setText={setText}
              file={file}
              setFile={setFile}
              setError={setError}
              mode={mode}
              setMode={setMode}
              provider={provider}
              providerDetails={providerDetails}
              selectedProvider={selectedProvider}
              selectedProviderModels={selectedProviderModels}
              handleProviderSelect={handleProviderSelect}
              model={model}
              setModel={setModel}
              qwenThinking={qwenThinking}
              setQwenThinking={setQwenThinking}
              strictMath={strictMath}
              setStrictMath={setStrictMath}
              attachments={attachments}
              setAttachments={setAttachments}
              error={error}
              loading={loading}
            />
          )}

          {activeBuilderTab === "outline" && (
            <OutlinePanel
              title={title}
              source={source}
              selectedStyle={selectedStyleOption}
              selectedLength={selectedLengthOption}
              includes={includes}
              result={result}
            />
          )}

          {activeBuilderTab === "style" && (
            <StyleSettings
              selectedStyle={selectedStyle}
              onSelectStyle={onSelectStyle}
              styleOptions={styleOptions}
              length={length}
              setLength={setLength}
              includes={includes}
              toggleInclude={toggleInclude}
            />
          )}

          {activeBuilderTab === "preview" && (
            <PreviewWorkspacePanel
              result={result}
              artifacts={artifactEntries}
              artifactUrls={artifactUrls}
              previewFormat={previewFormat}
              setPreviewFormat={setPreviewFormat}
            />
          )}
        </form>

        <LivePreviewPanel
          result={result}
          artifacts={artifactEntries}
          selectedStyle={selectedStyle}
          styleOptions={styleOptions}
          length={length}
          previewFormat={previewFormat}
          setPreviewFormat={setPreviewFormat}
          onOpenDetails={openJobDetails}
        />
      </div>
      <JobDetailsDrawer
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        loading={detailsLoading}
        error={detailsError}
        details={jobDetails}
        styleLookup={builderStyleLookup}
      />
    </div>
  );
}

function BuilderComposer({
  title,
  setTitle,
  source,
  setSource,
  text,
  setText,
  file,
  setFile,
  setError,
  mode,
  setMode,
  provider,
  providerDetails,
  selectedProvider,
  selectedProviderModels,
  handleProviderSelect,
  model,
  setModel,
  qwenThinking,
  setQwenThinking,
  strictMath,
  setStrictMath,
  attachments,
  setAttachments,
  error,
  loading
}) {
  return (
    <>
      <div className="sg-field-block">
        <FieldLabel>Title</FieldLabel>
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Enter guide title..."
          className="sg-input sg-input-lg"
        />
      </div>

      <div className="sg-field-block">
        <FieldLabel>Source</FieldLabel>
        <SourceTabs source={source} setSource={setSource} setError={setError} />

        <SourceEditor
          source={source}
          text={text}
          setText={setText}
          file={file}
          setFile={setFile}
          setError={setError}
        />
      </div>

      {source === "llm" && (
        <div className="sg-llm-panel">
          <div>
            <FieldLabel>Mode</FieldLabel>
            <div className="sg-option-grid four">
              {modeOptions.map((option) => (
                <OptionCard
                  key={option.id}
                  option={option}
                  active={mode === option.id}
                  onClick={() => setMode(option.id)}
                />
              ))}
            </div>
          </div>
          <div>
            <FieldLabel>Provider</FieldLabel>
            <div className="sg-option-grid">
              {providerDetails.map((detail) => (
                <OptionCard
                  key={detail.id}
                  option={providerOptionFromDetail(detail)}
                  active={provider === detail.id}
                  disabled={!detail.configured}
                  onClick={() => handleProviderSelect(detail.id)}
                />
              ))}
            </div>
          </div>
          <label>
            <FieldLabel>Model</FieldLabel>
            <select
              value={model}
              disabled={!selectedProvider?.configured || selectedProviderModels.length === 0}
              onChange={(event) => setModel(event.target.value)}
              className="sg-select"
            >
              {selectedProviderModels.map((modelId) => (
                <option key={modelId} value={modelId}>
                  {modelId}
                </option>
              ))}
            </select>
          </label>
          {selectedProvider?.discovery_error && (
            <p className="text-[12px] leading-5 text-[#FCA5A5]">
              Local discovery: {selectedProvider.discovery_error}
            </p>
          )}
          {selectedProvider?.supports_thinking && (
            <Toggle label="Qwen thinking mode" checked={qwenThinking} onChange={setQwenThinking} />
          )}
          <AttachmentsPicker attachments={attachments} setAttachments={setAttachments} />
          <Toggle label="Strict math" checked={strictMath} onChange={setStrictMath} />
        </div>
      )}

      {source !== "llm" && <Toggle label="Strict math" checked={strictMath} onChange={setStrictMath} />}
      {error && <ErrorMessage error={error} />}

      <div className="sg-generate-bar">
        <div className="sg-model-chip">
          <i />
          <span>{source === "llm" ? `${selectedProvider?.display_name || provider} · ${model || "No model"}` : "Markdown pipeline"}</span>
          <ChevronRight className="h-3.5 w-3.5 text-[#9098A8]" />
        </div>
        <div className="flex-1" />
        <button
          type="button"
          className="sg-ghost-button"
        >
          <Save className="h-4 w-4" />
          Save draft
        </button>
        <button
          type="submit"
          disabled={loading}
          className="sg-cta sg-generate-button"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-[18px] w-[18px]" />}
          {loading ? "Generating..." : "Generate Guide"}
        </button>
      </div>
    </>
  );
}

function BuilderTabIcon({ id, active }) {
  const color = active ? "#F97316" : "#6B7185";
  if (id === "outline") return <ListGlyph size={14} color={color} />;
  if (id === "style") return <SparkleGlyph size={14} color={color} />;
  if (id === "preview") return <PDFGlyph size={14} color={color} />;
  return <DocGlyph size={14} color={color} />;
}

function SourceTabs({ source, setSource, setError }) {
  const activeIndex = Math.max(0, sourceTabs.findIndex((tab) => tab.id === source));
  const tabsRef = React.useRef(null);
  const [slider, setSlider] = useState({ x: 4, w: 0 });

  useEffect(() => {
    const root = tabsRef.current;
    if (!root) return;
    const button = root.querySelectorAll("button.sg-tab")[activeIndex];
    if (!button) return;
    setSlider({ x: button.offsetLeft, w: button.offsetWidth });
  }, [activeIndex]);

  return (
    <div ref={tabsRef} className="sg-tabs mt-1.5">
      <span className="sg-tab-slider" style={{ transform: `translateX(${slider.x}px)`, width: slider.w }} />
      {sourceTabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          disabled={tab.disabled}
          onClick={() => {
            setSource(tab.id);
            setError(null);
          }}
          className={`sg-tab ${source === tab.id ? "active" : ""}`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

function OutlinePanel({ title, source, selectedStyle, selectedLength, includes, result }) {
  const sourceLabel = sourceTabs.find((tab) => tab.id === source)?.label || "Paste text";
  return (
    <div className="grid gap-4">
      <SectionHeader
        eyebrow="Planning"
        title="Guide outline"
        description="A generation-ready plan based on the current builder settings."
      />
      <div className="grid gap-3 xl:grid-cols-4">
        <InfoCard label="Title" value={title || "Untitled guide"} />
        <InfoCard label="Source" value={sourceLabel} />
        <InfoCard label="Style" value={selectedStyle?.name || selectedStyle?.label || "Exam Cram"} />
        <InfoCard label="Length" value={`${selectedLength?.label || "Medium"} ${selectedLength?.meta || "~20 pages"}`} />
      </div>
      <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
        <FieldLabel>Suggested structure</FieldLabel>
        <div className="mt-2 grid gap-2">
          {outlineSections.map((section, index) => (
            <div
              key={section}
              className="flex items-center gap-3 rounded-[10px] border border-white/[0.06] bg-[#070B14] px-3 py-2.5"
            >
              <span className="grid h-7 w-7 place-items-center rounded-md bg-[rgba(249,115,22,0.12)] font-mono text-[11px] font-bold text-[#FB923C]">
                {index + 1}
              </span>
              <span className="text-[13px] font-semibold text-[#F4F4F5]">{section}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="grid gap-3 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
          <FieldLabel>Included sections</FieldLabel>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {includes.map((item) => (
              <span
                key={item}
                className="inline-flex h-7 items-center rounded-full border border-[rgba(249,115,22,0.3)] bg-[rgba(249,115,22,0.10)] px-3 text-xs font-medium text-[#FB923C]"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
          <FieldLabel>Latest job</FieldLabel>
          {result ? (
            <div className="mt-2 grid gap-2 text-[12.5px] text-[#D4D4D8]">
              <MetaRow label="Job ID" value={result.job_id || result.id || "unknown"} />
              <MetaRow label="Status" value={result.status || "unknown"} />
              <MetaRow label="Model" value={result.model || "pipeline"} />
            </div>
          ) : (
            <p className="mt-2 text-[12.5px] leading-5 text-[#9098A8]">
              Generate a guide to attach job status and export metadata to this outline.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function StyleSettings({ selectedStyle, onSelectStyle, styleOptions, length, setLength, includes, toggleInclude }) {
  return (
    <div className="grid gap-5">
      <SectionHeader
        eyebrow="Guide design"
        title="Style and depth"
        description="Tune the preset, target length, and included learning aids used by generation."
      />
      <StyleControls selectedStyle={selectedStyle} onSelectStyle={onSelectStyle} styleOptions={styleOptions} />
      <LengthControls length={length} setLength={setLength} />
      <IncludeControls includes={includes} toggleInclude={toggleInclude} />
    </div>
  );
}

function PreviewWorkspacePanel({ result, artifacts, artifactUrls, previewFormat, setPreviewFormat }) {
  return (
    <div className="grid gap-4">
      <SectionHeader
        eyebrow="Preview"
        title="Exports and artifacts"
        description="Inspect the latest generated job and choose what to preview or download."
      />
      <div className="grid gap-3 xl:grid-cols-3">
        <InfoCard label="Preview" value={previewFormat === "sample" ? "Sample" : previewFormat.toUpperCase()} />
        <InfoCard label="Status" value={result?.status || "No generated job"} />
        <InfoCard label="Artifacts" value={`${artifacts.length} available`} />
      </div>
      <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
        <FieldLabel>Preview format</FieldLabel>
        <div className="mt-2 flex gap-1.5">
          {["pdf", "html"].map((format) => (
            <button
              key={format}
              type="button"
              disabled={!result}
              onClick={() => setPreviewFormat(format)}
              className={`h-8 rounded-md border px-3 text-[12px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-45 ${
                previewFormat === format
                  ? "border-[rgba(249,115,22,0.45)] bg-[rgba(249,115,22,0.14)] text-[#F97316]"
                  : "border-white/[0.08] bg-white/[0.03] text-[#9098A8] hover:text-[#D4D4D8]"
              }`}
            >
              {format.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
        <FieldLabel>Artifact availability</FieldLabel>
        {result ? (
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {Object.entries(artifactLabels).map(([name, artifact]) => {
              const available = Boolean(artifactUrls[name]);
              const Icon = artifact.icon;
              return (
                <div
                  key={name}
                  className={`flex items-center justify-between rounded-[10px] border px-3 py-2 ${
                    available
                      ? "border-[rgba(249,115,22,0.25)] bg-[rgba(249,115,22,0.08)]"
                      : "border-white/[0.06] bg-[#070B14] opacity-70"
                  }`}
                >
                  <span className="inline-flex items-center gap-2 text-[12px] font-semibold text-[#D4D4D8]">
                    <Icon className="h-3.5 w-3.5 text-[#F97316]" />
                    {artifact.label}
                  </span>
                  <span className="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-[#9098A8]">
                    {available ? "Ready" : "Missing"}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="mt-2 rounded-[10px] border border-white/[0.06] bg-[#070B14] p-4 text-[12.5px] leading-5 text-[#9098A8]">
            Generate a guide first to enable PDF/HTML preview and artifact downloads.
          </div>
        )}
      </div>
      {result && (
        <AttachedSourcesSummary result={result} />
      )}
      {result && (
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
          <FieldLabel>Downloads</FieldLabel>
          <ArtifactDownloadGrid artifacts={artifacts} />
        </div>
      )}
    </div>
  );
}

function StyleControls({ selectedStyle, onSelectStyle, styleOptions = styleChips }) {
  const builtinStyles = styleOptions.filter((style) => !style.custom);
  const customStyles = styleOptions.filter((style) => style.custom);

  const renderGrid = (styles) => (
    <div className="mt-1.5 grid grid-cols-3 gap-1.5 sm:grid-cols-6">
      {styles.map((style) => (
        <MiniStyle
          key={style.promptName}
          style={style}
          active={selectedStyle === style.promptName}
          onClick={() => onSelectStyle?.(style.promptName)}
        />
      ))}
    </div>
  );

  return (
    <div>
      <FieldLabel>Style</FieldLabel>
      <StyleGroupLabel>Built-in</StyleGroupLabel>
      {renderGrid(builtinStyles)}
      {customStyles.length > 0 && (
        <>
          <StyleGroupLabel>Custom</StyleGroupLabel>
          {renderGrid(customStyles)}
        </>
      )}
    </div>
  );
}

function StyleGroupLabel({ children }) {
  return (
    <div className="mt-2.5 mb-0.5 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.16em] text-[#9098A8]">
      <span>{children}</span>
      <span className="h-px flex-1 bg-white/10" />
    </div>
  );
}

function LengthControls({ length, setLength }) {
  return (
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
  );
}

function IncludeControls({ includes, toggleInclude }) {
  return (
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
  );
}

function SourceEditor({ source, text, setText, file, setFile, setError }) {
  if (source === "upload") {
    return (
      <label className="sg-source-drop">
        <Tile size={46} radius={12}><UploadGlyph size={22} /></Tile>
        <span>
          {file ? file.name : "Choose a .md or .markdown file"}
        </span>
        <em>Upload Markdown and generate a PDF-ready guide.</em>
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
    <div className="sg-source-editor">
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        aria-label={source === "llm" ? "AI prompt and source material" : "Pasted source text"}
        placeholder={
          source === "llm"
            ? "Describe the guide you want and paste the real source material here."
            : "# Your notes\n\nPaste Markdown or plain text here."
        }
        className="sg-source-textarea"
      />
      <div className="sg-char-count">
        {text.length.toLocaleString()} / 50,000 chars
      </div>
    </div>
  );
}

function AttachmentsPicker({ attachments, setAttachments }) {
  function addFiles(fileList) {
    const nextFiles = Array.from(fileList || []);
    if (nextFiles.length === 0) return;
    setAttachments((current) => [...current, ...nextFiles].slice(0, 5));
  }

  function removeFile(index) {
    setAttachments((current) => current.filter((_, fileIndex) => fileIndex !== index));
  }

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-3">
      <FieldLabel>Attachments</FieldLabel>
      <label className="mt-2 flex cursor-pointer items-center gap-3 rounded-[10px] border border-dashed border-white/[0.12] bg-[#070B14] p-3 transition hover:border-[rgba(249,115,22,0.35)]">
        <span className="grid h-9 w-9 place-items-center rounded-[9px] border border-[rgba(255,180,120,0.16)] bg-[#111A2B] text-[#F97316]">
          <Upload className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12.5px] font-semibold text-[#F4F4F5]">Attach source files</span>
          <span className="block text-[11px] text-[#9098A8]">txt, md, csv, tsv, docx, pptx, pdf · max 5 files</span>
        </span>
        <input
          type="file"
          multiple
          accept=".txt,.md,.markdown,.csv,.tsv,.docx,.pptx,.pdf"
          onChange={(event) => {
            addFiles(event.target.files);
            event.target.value = "";
          }}
          className="sr-only"
        />
      </label>
      {attachments.length > 0 && (
        <div className="mt-2 grid gap-1.5">
          {attachments.map((file, index) => (
            <div
              key={`${file.name}-${file.size}-${index}`}
              className="flex items-center gap-2 rounded-[9px] border border-white/[0.06] bg-white/[0.03] px-2.5 py-2 text-[12px]"
            >
              <FileText className="h-3.5 w-3.5 text-[#F97316]" />
              <span className="min-w-0 flex-1 truncate text-[#D4D4D8]">{file.name}</span>
              <span className="text-[10.5px] text-[#9098A8]">{formatFileSize(file.size)}</span>
              <button
                type="button"
                onClick={() => removeFile(index)}
                className="rounded-md border border-white/[0.08] px-2 py-1 text-[10.5px] font-semibold text-[#9098A8] transition hover:text-[#F4F4F5]"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MiniStyle({ style, active, onClick }) {
  const Icon = style.icon;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`sg-mini-style ${active ? "active" : ""}`}
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

function OptionCard({ option, active, disabled = false, onClick }) {
  const Icon = option.icon;
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`sg-option-card ${active ? "active" : ""} ${disabled ? "opacity-55" : ""}`}
    >
      <span
        className={`grid h-8 w-8 shrink-0 place-items-center rounded-[8px] border ${
          active
            ? "border-[rgba(255,180,120,0.4)] bg-gradient-to-br from-[#FB923C] via-[#F97316] to-[#C2410C] text-[#1B0F03]"
            : "border-[rgba(255,180,120,0.16)] bg-[#111A2B] text-[#F97316]"
        }`}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0">
        <span className="block text-[12.5px] font-semibold text-[#F4F4F5]">{option.label}</span>
        <span className="block truncate text-[10.5px] text-[#9098A8]">{option.meta}</span>
      </span>
    </button>
  );
}

function SectionHeader({ eyebrow, title, description }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
      <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-[#F97316]">
        {eyebrow}
      </div>
      <h2 className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-[#F4F4F5]">{title}</h2>
      <p className="mt-1 max-w-2xl text-[12.5px] leading-5 text-[#9098A8]">{description}</p>
    </div>
  );
}

function InfoCard({ label, value }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-3">
      <div className="font-mono text-[9.5px] font-semibold uppercase tracking-[0.12em] text-[#6B7185]">
        {label}
      </div>
      <div className="mt-1 truncate text-[13px] font-semibold text-[#F4F4F5]">{value}</div>
    </div>
  );
}

function MetaRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[9px] border border-white/[0.06] bg-[#070B14] px-3 py-2">
      <span className="text-[#9098A8]">{label}</span>
      <span className="truncate font-mono text-[11px] font-semibold text-[#F4F4F5]">{value}</span>
    </div>
  );
}

function PreviewFormatTabs({ result, previewFormat, setPreviewFormat }) {
  return (
    <div className="flex gap-1">
      {["pdf", "html"].map((format) => (
        <button
          key={format}
          type="button"
          disabled={!result}
          onClick={() => setPreviewFormat(format)}
          className={`h-7 rounded-md border px-2.5 text-[11.5px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-45 ${
            previewFormat === format
              ? "border-[rgba(249,115,22,0.45)] bg-[rgba(249,115,22,0.14)] text-[#F97316]"
              : "border-white/[0.08] bg-white/[0.03] text-[#9098A8] hover:text-[#D4D4D8]"
          }`}
        >
          {format.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

function ArtifactDownloadGrid({ artifacts, compact = false }) {
  return (
    <div className={`grid gap-1.5 ${compact ? "" : "sm:grid-cols-2"}`}>
      {artifacts.length === 0 && (
        <div className="rounded-md border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-[12px] text-[#9098A8]">
          No artifacts available yet.
        </div>
      )}
      {artifacts.map(([name, url]) => {
        const artifact = artifactLabels[name];
        const Icon = artifact.icon;
        const label = name === "final.html" ? "View HTML" : name === "final.pdf" ? "Download PDF" : artifact.label;
        return (
          <a
            key={name}
            href={apiUrl(url)}
            className="flex items-center justify-between rounded-md border border-white/[0.08] bg-white/[0.035] px-3 py-2 text-[12px] font-semibold text-[#D4D4D8] transition hover:border-[rgba(249,115,22,0.45)] hover:text-white"
          >
            <span className="inline-flex items-center gap-2">
              <Icon className="h-3.5 w-3.5 text-[#F97316]" />
              {label}
            </span>
            <Download className="h-3.5 w-3.5 text-[#6B7185]" />
          </a>
        );
      })}
    </div>
  );
}

function AttachedSourcesSummary({ result, compact = false }) {
  const attachments = result?.attachments ?? [];
  if (attachments.length === 0) {
    return null;
  }

  const warnings = result?.extraction_warnings ?? attachments.flatMap((item) => item.warnings ?? []);
  return (
    <div className={`rounded-xl border border-white/[0.06] bg-white/[0.025] ${compact ? "mt-3 p-3" : "p-4"}`}>
      <div className="flex items-center justify-between gap-3">
        <FieldLabel>Attached sources</FieldLabel>
        <div className="flex flex-wrap justify-end gap-1.5">
          <span className="inline-flex h-6 items-center gap-1.5 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2 text-[10.5px] font-bold text-emerald-200">
            <FileText className="h-3 w-3" />
            {attachments.length} {attachments.length === 1 ? "source" : "sources"}
          </span>
          {warnings.length > 0 && (
            <span className="inline-flex h-6 items-center gap-1.5 rounded-full border border-amber-300/30 bg-amber-300/10 px-2 text-[10.5px] font-bold text-amber-100">
              <AlertCircle className="h-3 w-3" />
              {warnings.length} warning{warnings.length === 1 ? "" : "s"}
            </span>
          )}
        </div>
      </div>
      <div className={`mt-2 grid gap-2 ${compact ? "max-h-36 overflow-auto pr-1" : ""}`}>
        {attachments.map((attachment, index) => {
          const itemWarnings = attachment.warnings ?? [];
          const extracted = Number(attachment.extracted_chars || 0);
          return (
            <div key={`${attachment.filename}-${index}`} className="rounded-[10px] border border-white/[0.06] bg-[#070B14] p-2.5">
              <div className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate text-[12px] font-semibold text-[#F4F4F5]">{attachment.filename}</span>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${
                  attachment.status === "extracted"
                    ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
                    : "border-amber-300/30 bg-amber-300/10 text-amber-100"
                }`}>
                  {attachment.status || "unknown"}
                </span>
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10.5px] font-semibold text-[#9098A8]">
                <span>{attachment.mode || attachment.extension || "unsupported"}</span>
                <span>{extracted.toLocaleString()} chars</span>
                {attachment.truncated && <span>truncated</span>}
              </div>
              {itemWarnings.length > 0 && (
                <div className="mt-2 grid gap-1 text-[11px] leading-4 text-amber-100">
                  {itemWarnings.map((warning, warningIndex) => (
                    <p key={warningIndex}>{warning}</p>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function LivePreviewPanel({
  result,
  artifacts,
  selectedStyle,
  styleOptions = styleChips,
  length,
  previewFormat,
  setPreviewFormat,
  onOpenDetails
}) {
  const artifactUrls = result?.artifact_urls ?? {};
  const primaryPdf = artifactUrls["final.pdf"];
  const title = result?.title || "Sample Guide Preview";
  const matchedStyle = styleOptions.find((style) => style.promptName === selectedStyle);
  const styleLabel = (matchedStyle?.name || matchedStyle?.label || "Exam Cram").toUpperCase();
  const lengthLabel = lengthOptions.find((option) => option.id === length)?.label?.toUpperCase() || "MEDIUM";

  return (
    <aside className="sg-preview-pane">
      <div className="sg-preview-top">
        <div>
          <div className="sg-preview-title">Live preview</div>
          <PreviewFormatTabs
            result={result}
            previewFormat={previewFormat}
            setPreviewFormat={setPreviewFormat}
          />
        </div>
      </div>

      <div className="sg-paper-preview">
        {!result ? (
          <div className="relative h-full overflow-hidden p-[10px] font-serif">
            <div className="font-mono text-[9px] tracking-[0.15em] text-[#A78050]">
              {styleLabel} · {lengthLabel}
            </div>
            <div className="mt-1.5 text-[22px] font-bold leading-[1.1] tracking-[-0.02em]">
              {title}
            </div>
            <div className="mt-1 font-sans text-[10.5px] text-[#6B5A3F]">
              Sample preview · not sent to backend
            </div>
            <div className="mt-3.5 h-px bg-gradient-to-r from-[#C2410C] to-transparent" />
            <SamplePreview />
            <div className="absolute bottom-0 left-[10px] right-[10px] flex justify-between font-mono text-[9px] text-[#A78050]">
              <span>STUDY GUIDE</span>
              <span>03 / 20</span>
            </div>
          </div>
        ) : (
          <ArtifactPreview
            format={previewFormat}
            artifactUrls={artifactUrls}
          />
        )}
      </div>

      {result && (
        <div className="sg-download-panel">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[12.5px] font-semibold text-[#D4D4D8]">Downloads</span>
            <span className="font-mono text-[10px] text-[#6B7185]">{artifacts.length} files</span>
          </div>
          <ArtifactDownloadGrid artifacts={artifacts} compact />
        </div>
      )}

      {result && <AttachedSourcesSummary result={result} compact />}

      <div className="sg-preview-actions">
        <a
          href={primaryPdf ? apiUrl(primaryPdf) : undefined}
          className={`flex h-9 flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-[12.5px] font-medium text-[#D4D4D8] ${
            primaryPdf ? "" : "pointer-events-none opacity-55"
          }`}
        >
          <Download className="h-4 w-4" />
          <span className="ml-2">Export PDF</span>
        </a>
        <button
          type="button"
          onClick={onOpenDetails}
          className="flex h-9 flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-[12.5px] font-medium text-[#D4D4D8]"
        >
          <Share2 className="h-3.5 w-3.5" />
          <span className="ml-2">Details</span>
        </button>
      </div>
    </aside>
  );
}

function ArtifactPreview({ format, artifactUrls }) {
  if (format === "pdf") {
    if (!artifactUrls["final.pdf"]) {
      return <PreviewUnavailable />;
    }
    return (
      <iframe
        title="Generated PDF preview"
        src={previewApiUrl(artifactUrls["final.pdf"])}
        className="h-full w-full rounded-md border-0 bg-white"
      />
    );
  }

  if (format === "html") {
    if (!artifactUrls["final.html"]) {
      return <PreviewUnavailable />;
    }
    return (
      <iframe
        title="Generated HTML preview"
        src={previewApiUrl(artifactUrls["final.html"])}
        sandbox="allow-same-origin"
        className="h-full w-full rounded-md border-0 bg-white"
      />
    );
  }

  return <PreviewUnavailable />;
}

function PreviewUnavailable() {
  return (
    <div className="grid h-full place-items-center rounded-md bg-white p-6 text-center">
      <div>
        <FileText className="mx-auto h-8 w-8 text-[#C2410C]" />
        <p className="mt-3 text-sm font-bold text-slate-900">Preview not available yet.</p>
        <p className="mt-1 text-xs text-slate-500">Choose PDF or HTML after the artifact is generated.</p>
      </div>
    </div>
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

function FieldLabel({ children }) {
  return (
    <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-[#9098A8]">
      {children}
    </div>
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

function normalizeProviderDetails(options) {
  const details = options?.provider_details ?? options?.providers_v2;
  if (Array.isArray(details) && details.length > 0) {
    return details.map((detail) => ({
      id: detail.id,
      display_name: detail.display_name || detail.name || detail.id,
      configured: Boolean(detail.configured),
      available_models: Array.isArray(detail.available_models) ? detail.available_models : [],
      default_model: detail.default_model || "",
      base_url: detail.base_url || "",
      discovery_error: detail.discovery_error || "",
      supports_thinking: Boolean(detail.supports_thinking)
    }));
  }
  return fallbackProviderDetails;
}

function chooseInitialProvider(details, currentProvider) {
  return (
    details.find((detail) => detail.id === currentProvider && detail.configured) ||
    details.find((detail) => detail.configured) ||
    details.find((detail) => detail.id === currentProvider) ||
    details[0] ||
    fallbackProviderDetails[0]
  );
}

function selectDefaultModel(detail, currentModel = "") {
  if (!detail) {
    return currentModel || "";
  }
  const models = detail.available_models || [];
  if (currentModel && models.includes(currentModel)) {
    return currentModel;
  }
  return detail.default_model || models[0] || "";
}

function providerOptionFromDetail(detail) {
  const modelCount = detail.available_models?.length || 0;
  return {
    id: detail.id,
    label: detail.display_name || detail.id,
    meta: detail.configured
      ? `${modelCount || 1} model${modelCount === 1 ? "" : "s"} available`
      : detail.base_url
        ? "Configured, discovery needs a model"
        : "Not configured",
    icon: detail.id === "qwen" ? Sparkles : detail.id === "local" ? Zap : Wand2
  };
}

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

export function buildBuilderPayload({
  source,
  text,
  file,
  title,
  mode,
  selectedStyle,
  provider,
  model,
  strictMath,
  qwenThinking,
  attachments,
  length,
  includes
}) {
  if (source === "upload") {
    return {
      kind: "upload",
      payload: {
        file,
        theme: "claude_clean",
        strictMath
      }
    };
  }

  if (source === "llm") {
    return {
      kind: "llm",
      payload: buildLlmPayload({
        text,
        title,
        mode,
        selectedStyle,
        provider,
        model,
        strictMath,
        qwenThinking,
        attachments,
        length,
        includes
      })
    };
  }

  return {
    kind: "paste",
    payload: {
      text,
      theme: "claude_clean",
      strictMath
    }
  };
}

export function buildLlmPayload({
  text,
  title,
  mode,
  selectedStyle,
  provider,
  model,
  strictMath,
  qwenThinking,
  attachments = [],
  length,
  includes
}) {
  return {
    source_text: augmentSourceText(text, length, includes),
    title,
    mode,
    prompt_name: selectedStyle,
    provider,
    model,
    theme: "claude_clean",
    strict_math: strictMath,
    qwen_thinking: qwenThinking,
    attachments
  };
}

function formatFileSize(size) {
  if (!Number.isFinite(size)) {
    return "";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${Math.round(size / 1024)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function assertBuilderPayload(kind, payload, state) {
  if (kind === "paste" && payload.text !== state.text) {
    throw new Error("Builder payload mismatch: paste text does not match editor text.");
  }

  if (kind === "llm") {
    const expectedSource = augmentSourceText(state.text, state.length, state.includes);
    if (payload.title !== state.title) {
      throw new Error("Builder payload mismatch: title does not match title field.");
    }
    if (payload.source_text !== expectedSource) {
      throw new Error("Builder payload mismatch: source text does not match editor text.");
    }
  }
}

function augmentSourceText(text, length, includes) {
  const lengthLabel = lengthOptions.find((option) => option.id === length)?.meta || "~20 pages";
  return `${text.trim()}\n\nAdditional builder instructions:\nRequested length: ${lengthLabel}.\nInclude: ${includes.join(", ")}.`;
}
